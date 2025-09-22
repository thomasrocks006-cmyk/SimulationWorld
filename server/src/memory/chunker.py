from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List, Optional

from .config import MemoryConfig
from .schema import ChunkInput


class Chunker:
    def __init__(self, config: MemoryConfig, chunk_size: int | None = None, overlap: int | None = None) -> None:
        self.config = config
        self.chunk_size = chunk_size or 900
        self.chunk_overlap = overlap or 120

    def chunk_text(
        self,
        text: str,
        *,
        ref_type: Optional[str] = None,
        ref_id: Optional[str] = None,
        ts: Optional[datetime] = None,
        meta: Optional[Dict[str, object]] = None,
    ) -> List[ChunkInput]:
        meta = dict(meta or {})
        if not text.strip():
            return []
        words = text.split()
        if len(words) <= self.chunk_size:
            return [ChunkInput(ref_type=ref_type, ref_id=ref_id, ts=ts, text=text, meta=meta)]
        chunks: List[ChunkInput] = []
        start = 0
        while start < len(words):
            end = min(start + self.chunk_size, len(words))
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words)
            meta_chunk = dict(meta)
            meta_chunk.setdefault("span", {"start_word": start, "end_word": end})
            chunks.append(
                ChunkInput(ref_type=ref_type, ref_id=ref_id, ts=ts, text=chunk_text, meta=meta_chunk)
            )
            if end == len(words):
                break
            start = max(end - self.chunk_overlap, start + 1)
        return chunks

    def chunk_entity_summary(
        self,
        entity_id: str,
        summary: str,
        summary_date: datetime,
        extra_meta: Optional[Dict[str, object]] = None,
    ) -> List[ChunkInput]:
        meta = {"entity_id": entity_id, "date": summary_date.isoformat(), "source": "entity_summary"}
        if extra_meta:
            meta.update(extra_meta)
        return self.chunk_text(summary, ref_type="entity_state", ref_id=entity_id, ts=summary_date, meta=meta)

    def chunk_event(
        self,
        event_id: int,
        text: str,
        ts: datetime,
        links: Iterable[str],
        extra_meta: Optional[Dict[str, object]] = None,
    ) -> List[ChunkInput]:
        meta = {"event_id": event_id, "links": list(links), "source": "event"}
        if extra_meta:
            meta.update(extra_meta)
        return self.chunk_text(text, ref_type="event", ref_id=str(event_id), ts=ts, meta=meta)


__all__ = ["Chunker"]
