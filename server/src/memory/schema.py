from __future__ import annotations

import json
from array import array
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import LargeBinary, TypeDecorator

try:  # Optional dependency - only needed for Postgres
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - fallback when pgvector not installed
    Vector = None  # type: ignore


metadata_obj = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


class Base(DeclarativeBase):
    metadata = metadata_obj


class JSONType(TypeDecorator):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):  # type: ignore[override]
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB

            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):  # type: ignore[override]
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            return json.loads(value)
        raise TypeError(f"Unsupported JSON value type: {type(value)!r}")

    def process_result_value(self, value, dialect):  # type: ignore[override]
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        return json.loads(value)


class StringArray(TypeDecorator):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):  # type: ignore[override]
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import ARRAY

            return dialect.type_descriptor(ARRAY(String()))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):  # type: ignore[override]
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return list(value)
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                raise ValueError("Expected JSON encoded array") from exc
        raise TypeError("links must be list or JSON string")

    def process_result_value(self, value, dialect):  # type: ignore[override]
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return list(value)
        return json.loads(value)


class VectorType(TypeDecorator):
    impl = LargeBinary
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):  # type: ignore[override]
        if dialect.name == "postgresql" and Vector is not None:
            return dialect.type_descriptor(Vector(self.dimensions))
        return dialect.type_descriptor(LargeBinary())

    def process_bind_param(self, value, dialect):  # type: ignore[override]
        if value is None:
            return None
        if dialect.name == "postgresql" and Vector is not None:
            return value
        arr = array("f", (float(x) for x in value))
        return arr.tobytes()

    def process_result_value(self, value, dialect):  # type: ignore[override]
        if value is None:
            return None
        if dialect.name == "postgresql" and Vector is not None:
            return list(value)
        arr = array("f")
        arr.frombytes(value)
        return list(arr)


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String)
    meta: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Attribute(Base):
    __tablename__ = "attributes"
    __table_args__ = (UniqueConstraint("entity_id", "key", "valid_from", name="uq_attribute_version"),)

    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    key: Mapped[str] = mapped_column(String, primary_key=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    value: Mapped[Dict[str, Any]] = mapped_column(JSONType)


class Relation(Base):
    __tablename__ = "relations"
    __table_args__ = (UniqueConstraint("src_id", "rel", "dst_id", "valid_from", name="uq_relation_version"),)

    src_id: Mapped[str] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    rel: Mapped[str] = mapped_column(String, primary_key=True)
    dst_id: Mapped[str] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    weight: Mapped[float] = mapped_column(Float, default=1.0)


class EventRecord(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(ForeignKey("entities.id"))
    type: Mapped[Optional[str]] = mapped_column(String)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict)
    links: Mapped[List[str]] = mapped_column(StringArray, default=list)


class DailyStateRecord(Base):
    __tablename__ = "daily_state"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    global_state: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict)
    summary: Mapped[Optional[str]] = mapped_column(Text)


class EntityStateRecord(Base):
    __tablename__ = "entity_state"
    __table_args__ = (UniqueConstraint("date", "entity_id", name="uq_entity_state_date"),)

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    state: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict)
    summary: Mapped[Optional[str]] = mapped_column(Text)


class ChunkRecord(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ref_type: Mapped[Optional[str]] = mapped_column(String)
    ref_id: Mapped[Optional[str]] = mapped_column(String)
    ts: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict)


class EmbeddingRecord(Base):
    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("chunks.id", ondelete="CASCADE"))
    embedding: Mapped[Optional[List[float]]] = mapped_column(VectorType(1536))


EntityKind = Literal["person", "wallet", "property", "business", "security"]


class EntityUpsert(BaseModel):
    id: Optional[str] = None
    kind: EntityKind
    name: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class AttributeSet(BaseModel):
    entity_id: str
    key: str
    value: Dict[str, Any]
    valid_from: datetime
    valid_to: Optional[datetime] = None


class RelationSet(BaseModel):
    src_id: str
    rel: str
    dst_id: str
    valid_from: datetime
    valid_to: Optional[datetime] = None
    weight: float = 1.0


class EventCreate(BaseModel):
    ts: datetime
    actor_id: Optional[str] = None
    type: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    links: List[str] = Field(default_factory=list)


class EventResponse(EventCreate):
    id: int


class EntityStateWrite(BaseModel):
    date: date
    entity_id: str
    state: Dict[str, Any]
    summary: Optional[str] = None


class DailyStateWrite(BaseModel):
    date: date
    global_state: Dict[str, Any]
    summary: Optional[str] = None


class ChunkInput(BaseModel):
    ref_type: Optional[str] = None
    ref_id: Optional[str] = None
    ts: Optional[datetime] = None
    text: str
    meta: Dict[str, Any] = Field(default_factory=dict)


class ChunkWithScore(BaseModel):
    id: int
    text: str
    meta: Dict[str, Any]
    ts: Optional[datetime]
    ref_type: Optional[str]
    ref_id: Optional[str]
    score: float = 0.0


class PromptPack(BaseModel):
    question: str
    entities: List[str]
    states: List[EntityStateWrite]
    daily: Optional[DailyStateWrite] = None
    events: List[EventResponse] = Field(default_factory=list)
    chunks: List[ChunkWithScore] = Field(default_factory=list)


class RetrieveRequest(BaseModel):
    question: str
    entity_scope: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)


class TickRunRequest(BaseModel):
    date: date
    entities: List[EntityStateWrite]
    global_state: DailyStateWrite
    events: List[EventCreate] = Field(default_factory=list)


class MemoryStatus(BaseModel):
    db: str
    vector: str
    last_tick: Optional[datetime]
    counts: Dict[str, int]


def _migration_root(vendor: str) -> Path:
    base = Path(__file__).resolve().parents[2] / "db" / "migrations"
    if vendor == "sqlite":
        base = base / "sqlite"
    return base


def _apply_sql(engine: Engine, vendor: str, sql: str) -> None:
    if vendor == "sqlite":
        raw = engine.raw_connection()
        try:
            raw.executescript(sql)
            raw.commit()
        finally:
            raw.close()
        return

    statements = [stmt.strip() for stmt in sql.split(";") if stmt.strip()]
    with engine.begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)


def run_migrations(engine: Engine, vendor: str) -> None:
    root = _migration_root(vendor)
    if not root.exists():
        raise HTTPException(status_code=500, detail=f"Missing migrations for vendor {vendor}")

    for path in sorted(root.glob("*.sql")):
        sql = path.read_text()
        try:
            _apply_sql(engine, vendor, sql)
        except SQLAlchemyError as exc:  # pragma: no cover - surfaces migration issues
            raise HTTPException(status_code=500, detail=f"Migration {path.name} failed: {exc}") from exc


@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):  # pragma: no cover - sqlite only
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        pass


__all__ = [
    "EntityKind",
    "EntityUpsert",
    "AttributeSet",
    "RelationSet",
    "EventCreate",
    "EventResponse",
    "EntityStateWrite",
    "DailyStateWrite",
    "ChunkInput",
    "ChunkWithScore",
    "PromptPack",
    "RetrieveRequest",
    "TickRunRequest",
    "MemoryStatus",
    "run_migrations",
    "Entity",
    "Attribute",
    "Relation",
    "EventRecord",
    "DailyStateRecord",
    "EntityStateRecord",
    "ChunkRecord",
    "EmbeddingRecord",
    "Base",
]
