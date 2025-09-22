from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from .chunker import Chunker
from .config import MemoryConfig
from .embeddings import embed_batch
from .schema import (
    ChunkInput,
    DailyStateWrite,
    EntityStateWrite,
    EventCreate,
    EventResponse,
    TickRunRequest,
)
from .store import MemoryStore, as_event_response
from .summarizer import Summarizer


class TickPipeline:
    def __init__(self, store: MemoryStore, config: MemoryConfig) -> None:
        self.store = store
        self.config = config
        self.chunker = Chunker(config)
        self.summarizer = Summarizer(config)

    def run(self, request: TickRunRequest, correlation_id: Optional[str] = None) -> Dict[str, object]:
        self.store.ensure_schema()
        recorded_events: List[EventResponse] = []
        for event_payload in request.events:
            record = self.store.append_event(event_payload, correlation_id)
            recorded_events.append(as_event_response(record))

        entity_states_written: List[EntityStateWrite] = []
        for entity_state in request.entities:
            summary = entity_state.summary
            if not summary:
                recent_events = [ev for ev in recorded_events if entity_state.entity_id in ev.links]
                summary = self.summarizer.summarize_entity_day(
                    entity_state.entity_id,
                    entity_state.state,
                    recent_events,
                    entity_state.date,
                )
            payload = EntityStateWrite(
                date=entity_state.date,
                entity_id=entity_state.entity_id,
                state=entity_state.state,
                summary=summary,
            )
            self.store.write_entity_state(payload, correlation_id)
            entity_states_written.append(payload)

        daily_payload = request.global_state
        if not daily_payload.summary:
            headlines = [event.type or "event" for event in recorded_events]
            daily_payload = DailyStateWrite(
                date=daily_payload.date,
                global_state=daily_payload.global_state,
                summary=self.summarizer.summarize_daily(
                    daily_payload.global_state,
                    headlines,
                    daily_payload.date,
                ),
            )
        self.store.write_daily_state(daily_payload, correlation_id)

        chunk_inputs: List[ChunkInput] = []
        for state in entity_states_written:
            ts = datetime.combine(state.date, datetime.min.time())
            chunk_inputs.extend(
                self.chunker.chunk_entity_summary(state.entity_id, state.summary or "", ts)
            )

        for event in recorded_events:
            ts = event.ts
            payload_text = ", ".join(f"{k}={v}" for k, v in (event.payload or {}).items())
            event_text = f"Event {event.id} ({event.type or 'event'}): {payload_text}".strip()
            chunk_inputs.extend(
                self.chunker.chunk_event(event.id, event_text, ts, event.links)
            )

        chunk_inputs = _deduplicate_chunks(chunk_inputs)
        chunk_records = self.store.add_chunks(chunk_inputs, correlation_id)

        if request.date.weekday() == 6:
            arc_chunks: List[ChunkInput] = []
            for state in entity_states_written:
                history = self.store.get_recent_entity_states([state.entity_id], days=28)
                summaries = [record.summary for record in history if record.summary]
                arc_text = self.summarizer.summarize_arc(
                    state.entity_id,
                    summaries,
                    label=f"Weekly arc ending {request.date.isoformat()}",
                )
                ts = datetime.combine(request.date, datetime.min.time())
                arc_chunks.extend(
                    self.chunker.chunk_text(
                        arc_text,
                        ref_type="arc",
                        ref_id=state.entity_id,
                        ts=ts,
                        meta={"entity_id": state.entity_id, "date": request.date.isoformat()},
                    )
                )
            if arc_chunks:
                arc_chunks = _deduplicate_chunks(arc_chunks)
                arc_records = self.store.add_chunks(arc_chunks, correlation_id)
                chunk_records.extend(arc_records)

        embeddings_created = 0
        if chunk_records and self.config.vector_dim:
            vectors = embed_batch((record.text for record in chunk_records), self.config)
            vector_pairs = list(zip([record.id for record in chunk_records], vectors))
            self.store.prune_chunk_embeddings([record.id for record in chunk_records])
            self.store.add_embeddings(vector_pairs, correlation_id)
            embeddings_created = len(vector_pairs)

        return {
            "events": len(recorded_events),
            "entity_states": len(entity_states_written),
            "chunks": len(chunk_records),
            "embeddings": embeddings_created,
        }


def _deduplicate_chunks(chunks: List[ChunkInput]) -> List[ChunkInput]:
    seen = set()
    deduped: List[ChunkInput] = []
    for chunk in chunks:
        fingerprint = (chunk.ref_type, chunk.ref_id, chunk.text)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        deduped.append(chunk)
    return deduped


__all__ = ["TickPipeline"]
