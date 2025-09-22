from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from sqlalchemy import Select, and_, delete, desc, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from .config import MemoryConfig
from .ids import entity_id
from .schema import (
    Attribute,
    AttributeSet,
    ChunkInput,
    ChunkRecord,
    DailyStateRecord,
    DailyStateWrite,
    EmbeddingRecord,
    Entity,
    EntityStateRecord,
    EntityStateWrite,
    EntityUpsert,
    EventCreate,
    EventRecord,
    EventResponse,
    PromptPack,
    Relation,
    RelationSet,
    RetrieveRequest,
    run_migrations,
)

logger = logging.getLogger(__name__)


class MemoryStore:
    def __init__(self, engine: Engine, config: MemoryConfig) -> None:
        self.engine = engine
        self.config = config
        self.Session = sessionmaker(bind=engine, future=True, expire_on_commit=False)
        self._migrated = False

    def ensure_schema(self) -> None:
        if self._migrated:
            return
        run_migrations(self.engine, self.config.db_vendor)
        self._migrated = True

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # --- Write operations -------------------------------------------------

    def upsert_entity(self, payload: EntityUpsert, correlation_id: Optional[str] = None) -> Entity:
        self.ensure_schema()
        entity_id_value = payload.id or entity_id(payload.kind, payload.name or payload.kind)
        log_extra = {"correlation_id": correlation_id, "entity_id": entity_id_value}
        logger.info("memory.upsert_entity", extra=log_extra)
        with self.session() as session:
            existing = session.get(Entity, entity_id_value)
            if existing:
                existing.kind = payload.kind
                existing.name = payload.name
                existing.meta = payload.meta or {}
                session.add(existing)
                return existing
            entity = Entity(id=entity_id_value, kind=payload.kind, name=payload.name, meta=payload.meta or {})
            session.add(entity)
            return entity

    def set_attribute(self, payload: AttributeSet, correlation_id: Optional[str] = None) -> None:
        self.ensure_schema()
        log_extra = {"correlation_id": correlation_id, "entity_id": payload.entity_id, "key": payload.key}
        logger.info("memory.set_attribute", extra=log_extra)
        with self.session() as session:
            record = Attribute(
                entity_id=payload.entity_id,
                key=payload.key,
                value=payload.value,
                valid_from=payload.valid_from,
                valid_to=payload.valid_to,
            )
            session.merge(record)

    def add_relation(self, payload: RelationSet, correlation_id: Optional[str] = None) -> None:
        self.ensure_schema()
        log_extra = {
            "correlation_id": correlation_id,
            "src": payload.src_id,
            "dst": payload.dst_id,
            "rel": payload.rel,
        }
        logger.info("memory.add_relation", extra=log_extra)
        with self.session() as session:
            record = Relation(
                src_id=payload.src_id,
                dst_id=payload.dst_id,
                rel=payload.rel,
                valid_from=payload.valid_from,
                valid_to=payload.valid_to,
                weight=payload.weight,
            )
            session.merge(record)

    def append_event(self, payload: EventCreate, correlation_id: Optional[str] = None) -> EventRecord:
        self.ensure_schema()
        log_extra = {"correlation_id": correlation_id, "ts": payload.ts.isoformat(), "type": payload.type}
        logger.info("memory.append_event", extra=log_extra)
        links = list(dict.fromkeys(payload.links))
        with self.session() as session:
            record = EventRecord(
                ts=payload.ts,
                actor_id=payload.actor_id,
                type=payload.type,
                payload=payload.payload,
                links=links,
            )
            session.add(record)
            session.flush()
            return record

    def write_entity_state(self, payload: EntityStateWrite, correlation_id: Optional[str] = None) -> EntityStateRecord:
        self.ensure_schema()
        log_extra = {"correlation_id": correlation_id, "entity_id": payload.entity_id, "date": payload.date.isoformat()}
        logger.info("memory.write_entity_state", extra=log_extra)
        with self.session() as session:
            record = session.get(EntityStateRecord, {"date": payload.date, "entity_id": payload.entity_id})
            if record:
                record.state = payload.state
                record.summary = payload.summary
                session.add(record)
                return record
            record = EntityStateRecord(
                date=payload.date,
                entity_id=payload.entity_id,
                state=payload.state,
                summary=payload.summary,
            )
            session.add(record)
            return record

    def write_daily_state(self, payload: DailyStateWrite, correlation_id: Optional[str] = None) -> DailyStateRecord:
        self.ensure_schema()
        log_extra = {"correlation_id": correlation_id, "date": payload.date.isoformat()}
        logger.info("memory.write_daily_state", extra=log_extra)
        with self.session() as session:
            record = session.get(DailyStateRecord, payload.date)
            if record:
                record.global_state = payload.global_state
                record.summary = payload.summary
                session.add(record)
                return record
            record = DailyStateRecord(
                date=payload.date,
                global_state=payload.global_state,
                summary=payload.summary,
            )
            session.add(record)
            return record

    def add_chunks(self, chunks: Sequence[ChunkInput], correlation_id: Optional[str] = None) -> List[ChunkRecord]:
        self.ensure_schema()
        if not chunks:
            return []
        log_extra = {"correlation_id": correlation_id, "count": len(chunks)}
        logger.info("memory.add_chunks", extra=log_extra)
        with self.session() as session:
            records: List[ChunkRecord] = []
            for chunk in chunks:
                record = ChunkRecord(
                    ref_type=chunk.ref_type,
                    ref_id=chunk.ref_id,
                    ts=chunk.ts,
                    text=chunk.text,
                    meta=chunk.meta,
                )
                session.add(record)
                session.flush([record])
                records.append(record)
            return records

    def add_embeddings(
        self,
        vectors: Sequence[Tuple[int, Sequence[float]]],
        correlation_id: Optional[str] = None,
    ) -> List[EmbeddingRecord]:
        self.ensure_schema()
        if not vectors:
            return []
        log_extra = {"correlation_id": correlation_id, "count": len(vectors)}
        logger.info("memory.add_embeddings", extra=log_extra)
        target_dim = self.config.vector_dim
        with self.session() as session:
            records: List[EmbeddingRecord] = []
            for chunk_id, vector in vectors:
                normalized = self._normalize_vector(vector, target_dim)
                record = EmbeddingRecord(chunk_id=chunk_id, embedding=normalized)
                session.add(record)
                session.flush([record])
                records.append(record)
            return records

    # --- Retrieval helpers -----------------------------------------------

    def get_entity(self, entity_id_value: str) -> Optional[Entity]:
        self.ensure_schema()
        with self.session() as session:
            return session.get(Entity, entity_id_value)

    def get_latest_entity_state(self, entity_id_value: str) -> Optional[EntityStateRecord]:
        self.ensure_schema()
        with self.session() as session:
            stmt = (
                select(EntityStateRecord)
                .where(EntityStateRecord.entity_id == entity_id_value)
                .order_by(EntityStateRecord.date.desc())
                .limit(1)
            )
            return session.execute(stmt).scalars().first()

    def get_daily_state(self, target_date: date) -> Optional[DailyStateRecord]:
        self.ensure_schema()
        with self.session() as session:
            return session.get(DailyStateRecord, target_date)

    def get_recent_entity_states(self, entity_ids: Sequence[str], days: int) -> List[EntityStateRecord]:
        if not entity_ids:
            return []
        self.ensure_schema()
        cutoff = date.today() - timedelta(days=days)
        with self.session() as session:
            stmt = (
                select(EntityStateRecord)
                .where(EntityStateRecord.entity_id.in_(entity_ids))
                .where(EntityStateRecord.date >= cutoff)
                .order_by(EntityStateRecord.date.desc())
            )
            return list(session.execute(stmt).scalars())

    def get_recent_events(self, entity_ids: Sequence[str], window_days: int, limit: int) -> List[EventRecord]:
        if not entity_ids:
            return []
        self.ensure_schema()
        since_ts = datetime.now(timezone.utc) - timedelta(days=window_days)
        with self.session() as session:
            if self.config.is_postgres:
                stmt = (
                    select(EventRecord)
                    .where(EventRecord.ts >= since_ts)
                    .where(EventRecord.links.op("&&")(list(entity_ids)))
                    .order_by(EventRecord.ts.desc())
                    .limit(limit)
                )
                return list(session.execute(stmt).scalars())

            stmt = (
                select(EventRecord)
                .where(EventRecord.ts >= since_ts)
                .order_by(EventRecord.ts.desc())
                .limit(limit)
            )
            rows = list(session.execute(stmt).scalars())
            return [row for row in rows if any(link in entity_ids for link in (row.links or []))]

    def keyword_search_chunks(self, query: str, limit: int) -> List[ChunkRecord]:
        if not query.strip():
            return []
        self.ensure_schema()
        with self.session() as session:
            if self.config.is_postgres:
                stmt = (
                    select(ChunkRecord)
                    .where(func.to_tsvector("english", ChunkRecord.text).match(query))
                    .order_by(ChunkRecord.ts.desc())
                    .limit(limit)
                )
                return list(session.execute(stmt).scalars())
            # SQLite uses FTS virtual table
            stmt = select(ChunkRecord).where(ChunkRecord.text.like(f"%{query}%")).order_by(ChunkRecord.ts.desc()).limit(limit)
            return list(session.execute(stmt).scalars())

    def vector_search_chunks(self, vector: Sequence[float], limit: int) -> List[Tuple[ChunkRecord, float]]:
        if not vector:
            return []
        self.ensure_schema()
        target_dim = self.config.vector_dim
        normalized = self._normalize_vector(vector, target_dim)
        with self.session() as session:
            if self.config.is_postgres and hasattr(EmbeddingRecord.embedding, "cosine_distance"):
                score_expr = 1 - EmbeddingRecord.embedding.cosine_distance(normalized)
                stmt = (
                    select(ChunkRecord, score_expr.label("score"))
                    .join(EmbeddingRecord, EmbeddingRecord.chunk_id == ChunkRecord.id)
                    .order_by(desc(score_expr))
                    .limit(limit)
                )
                rows = session.execute(stmt).all()
                return [(row[0], float(row.score)) for row in rows]
            # SQLite fallback: no vector index, return empty
            rows = (
                session.query(ChunkRecord)
                .join(EmbeddingRecord, EmbeddingRecord.chunk_id == ChunkRecord.id)
                .limit(limit)
                .all()
            )
            return [(row, 0.0) for row in rows]

    def get_counts(self) -> Dict[str, int]:
        self.ensure_schema()
        entities = self._count(Entity)
        events = self._count(EventRecord)
        chunks = self._count(ChunkRecord)
        embeddings = self._count(EmbeddingRecord)
        return {
            "entities": entities,
            "events": events,
            "chunks": chunks,
            "embeddings": embeddings,
        }

    def get_last_chunk_time(self) -> Optional[datetime]:
        self.ensure_schema()
        with self.session() as session:
            stmt = select(func.max(ChunkRecord.ts)).scalar_subquery()
            return session.execute(select(stmt)).scalar_one_or_none()

    def prune_chunk_embeddings(self, chunk_ids: Sequence[int]) -> None:
        if not chunk_ids:
            return
        self.ensure_schema()
        with self.session() as session:
            session.execute(delete(EmbeddingRecord).where(EmbeddingRecord.chunk_id.in_(chunk_ids)))

    # --- Helpers ----------------------------------------------------------

    def _normalize_vector(self, vector: Sequence[float], dim: int) -> List[float]:
        values = list(float(x) for x in vector)
        if len(values) == dim:
            return values
        if len(values) > dim:
            return values[:dim]
        padding = [0.0] * (dim - len(values))
        return values + padding

    def _count(self, model) -> int:
        with self.session() as session:
            return session.query(func.count()).select_from(model).scalar() or 0


def as_event_response(record: EventRecord) -> EventResponse:
    return EventResponse(
        id=record.id,
        ts=record.ts,
        actor_id=record.actor_id,
        type=record.type,
        payload=record.payload or {},
        links=record.links or [],
    )


__all__ = ["MemoryStore", "as_event_response"]
