from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Tuple

from dataclasses import dataclass

from .config import MemoryConfig
from .embeddings import embed_text
from .schema import (
    ChunkWithScore,
    DailyStateWrite,
    EntityStateWrite,
    EventResponse,
    PromptPack,
    RetrieveRequest,
)
from .store import MemoryStore, as_event_response


@dataclass
class RetrieverLimitsOverride:
    chunks: int
    events: int
    states_days: int


class Retriever:
    def __init__(self, store: MemoryStore, config: MemoryConfig) -> None:
        self.store = store
        self.config = config

    def retrieve(
        self,
        request: RetrieveRequest,
        *,
        limits_override: RetrieverLimitsOverride | None = None,
    ) -> PromptPack:
        entities = request.entity_scope
        limits_cfg = limits_override or RetrieverLimitsOverride(
            chunks=self.config.retriever_limits.chunks,
            events=self.config.retriever_limits.events,
            states_days=self.config.retriever_limits.states_days,
        )

        states_records = self.store.get_recent_entity_states(entities, limits_cfg.states_days)
        states = [
            EntityStateWrite(date=record.date, entity_id=record.entity_id, state=record.state or {}, summary=record.summary)
            for record in states_records
        ]

        daily = None
        if states:
            most_recent_date = max(record.date for record in states_records)
            daily_record = self.store.get_daily_state(most_recent_date)
            if daily_record:
                daily = DailyStateWrite(date=daily_record.date, global_state=daily_record.global_state or {}, summary=daily_record.summary)

        events_records = self.store.get_recent_events(entities, window_days=60, limit=limits_cfg.events)
        events = [as_event_response(record) for record in events_records]

        keywords = request.keywords or _extract_keywords(request.question)
        keyword_query = " & ".join(keywords) if self.store.config.is_postgres else " ".join(keywords)
        chunk_candidates = []
        if keyword_query:
            keyword_chunks = self.store.keyword_search_chunks(keyword_query, limits_cfg.chunks)
            chunk_candidates.extend((chunk, 0.25) for chunk in keyword_chunks)

        semantic_scores: List[Tuple[int, float]] = []
        if self.config.vector_dim and request.question.strip():
            try:
                vector = embed_text(request.question, self.config)
                semantic_chunks = self.store.vector_search_chunks(vector, limits_cfg.chunks)
                for chunk, score in semantic_chunks:
                    semantic_scores.append((chunk.id, score))
                    chunk_candidates.append((chunk, 0.45 * score))
            except Exception:
                pass

        combined: Dict[int, ChunkWithScore] = {}
        now = datetime.now(timezone.utc)
        for chunk, base_score in chunk_candidates:
            existing = combined.get(chunk.id)
            score = base_score
            if chunk.ts:
                chunk_ts = chunk.ts
                if chunk_ts.tzinfo is None:
                    chunk_ts = chunk_ts.replace(tzinfo=timezone.utc)
                age_days = max((now - chunk_ts).total_seconds() / 86400, 0.0)
                recency = max(0.0, 1.0 - age_days / 60.0)
                score += 0.20 * recency
            meta = chunk.meta or {}
            if entities and any(meta.get("entity_id") == e or e in meta.get("links", []) for e in entities):
                score += 0.10
            entry = ChunkWithScore(
                id=chunk.id,
                text=chunk.text,
                meta=meta,
                ts=chunk.ts,
                ref_type=chunk.ref_type,
                ref_id=chunk.ref_id,
                score=score,
            )
            if existing is None or entry.score > existing.score:
                combined[chunk.id] = entry

        ranked_chunks = sorted(combined.values(), key=lambda item: item.score, reverse=True)

        trimmed_chunks: List[ChunkWithScore] = []
        token_budget = self.config.max_tokens
        token_count = 0
        for chunk in ranked_chunks:
            approx_tokens = _approx_tokens(chunk.text)
            if token_count + approx_tokens > token_budget:
                break
            trimmed_chunks.append(chunk)
            token_count += approx_tokens

        return PromptPack(
            question=request.question,
            entities=list(entities),
            states=states,
            daily=daily,
            events=events,
            chunks=trimmed_chunks,
        )


def _extract_keywords(question: str) -> List[str]:
    tokens = [token for token in question.replace("?", "").split() if len(token) > 2]
    unique = list(dict.fromkeys(tokens))
    return unique[:8]


def _approx_tokens(text: str) -> int:
    words = text.split()
    return max(1, int(len(words) * 1.25))


__all__ = ["Retriever", "RetrieverLimitsOverride"]
