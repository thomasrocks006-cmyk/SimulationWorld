from __future__ import annotations

import json
import logging
from datetime import date
from typing import Iterable, List

import httpx

from .config import MemoryConfig
from .schema import EventResponse

logger = logging.getLogger(__name__)

MAX_WORDS = 550
SYSTEM_PROMPT = (
    "You summarise simulation state. Keep numbers factual, avoid inventing data. "
    "Return concise prose (<= 120 words) highlighting key changes, referencing provided metrics."  # noqa: E501
)


class Summarizer:
    def __init__(self, config: MemoryConfig) -> None:
        self.config = config

    def summarize_entity_day(
        self,
        entity_id: str,
        state: dict,
        recent_events: Iterable[EventResponse],
        day: date,
    ) -> str:
        events_list = list(recent_events)
        if self.config.llm_enabled:
            try:
                return _llm_summarise(
                    config=self.config,
                    subject=f"Entity {entity_id}",
                    day=day,
                    payload={"state": state, "events": [_event_payload(ev) for ev in events_list]},
                )
            except Exception as exc:  # pragma: no cover - network failures
                logger.warning("memory.summarizer.remote_failed", exc_info=exc)
        return _local_entity_summary(entity_id, state, events_list, day)

    def summarize_daily(self, global_state: dict, headlines: Iterable[str], day: date) -> str:
        headlines_list = [h for h in headlines if h]
        if self.config.llm_enabled:
            try:
                return _llm_summarise(
                    config=self.config,
                    subject="Daily overview",
                    day=day,
                    payload={"global_state": global_state, "headlines": headlines_list},
                )
            except Exception as exc:  # pragma: no cover - network failures
                logger.warning("memory.summarizer.remote_failed", exc_info=exc)
        return _local_daily_summary(global_state, headlines_list, day)

    def summarize_arc(self, entity_id: str, summaries: Iterable[str], *, label: str | None = None) -> str:
        collected = [s for s in summaries if s]
        if not collected:
            return f"No arc activity recorded for {entity_id}."
        intro = label or f"Arc summary for {entity_id}"
        body = " ".join(collected[-5:])
        return _truncate_words(f"{intro}: {body}", 750)


def _llm_summarise(*, config: MemoryConfig, subject: str, day: date, payload: dict) -> str:
    base = config.llm_api_base.rstrip("/")
    endpoint = f"{base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.llm_api_key}",
        "Content-Type": "application/json",
    }
    user_prompt = (
        f"Summarise {subject} for {day.isoformat()} using the provided JSON data. "
        "Call out material changes, balances, and any notable events."
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    request_body = {
        "model": config.llm_model,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 600,
    }
    with httpx.Client(timeout=config.http_timeout) as client:
        response = client.post(endpoint, headers=headers, json=request_body)
        response.raise_for_status()
        data = response.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as exc:  # pragma: no cover - defensive
        raise ValueError(f"Unexpected LLM response: {json.dumps(data)[:200]}") from exc


def _local_entity_summary(
    entity_id: str,
    state: dict,
    events_list: List[EventResponse],
    day: date,
) -> str:
    lines: List[str] = [f"Entity {entity_id} snapshot for {day.isoformat()}."]
    if state:
        numeric_lines = []
        for key, value in sorted(state.items()):
            if isinstance(value, (int, float)):
                numeric_lines.append(f"{key.replace('_', ' ').title()}: {value}")
            else:
                numeric_lines.append(f"{key.replace('_', ' ')}: {value}")
        lines.append("State metrics: " + "; ".join(numeric_lines))
    else:
        lines.append("No quantitative changes recorded.")

    if events_list:
        parts = []
        for event in events_list[:5]:
            summary_piece = event.type or "event"
            if event.payload:
                detail = ", ".join(f"{k}={v}" for k, v in list(event.payload.items())[:4])
                summary_piece += f" ({detail})"
            parts.append(f"{event.ts.date().isoformat()}: {summary_piece}")
        lines.append("Recent events: " + " | ".join(parts))
    else:
        lines.append("No linked events in the recent window.")

    return _truncate_words(" ".join(lines), MAX_WORDS)


def _local_daily_summary(global_state: dict, headlines: List[str], day: date) -> str:
    lines: List[str] = [f"Daily overview for {day.isoformat()}."]
    if global_state:
        stats = "; ".join(f"{k}: {v}" for k, v in list(global_state.items())[:8])
        lines.append(f"Global metrics: {stats}.")
    if headlines:
        lines.append("Headlines: " + " | ".join(headlines[:6]))
    return _truncate_words(" ".join(lines), MAX_WORDS)


def _event_payload(event: EventResponse) -> dict:
    return {
        "id": event.id,
        "ts": event.ts.isoformat(),
        "type": event.type,
        "payload": event.payload,
        "links": event.links,
    }


def _truncate_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " …"


__all__ = ["Summarizer"]
