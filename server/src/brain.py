from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Dict, List, Optional

import httpx

from .memory.chunker import Chunker
from .memory.config import MemoryConfig, create_engine_from_config, load_memory_config
from .memory.embeddings import embed_batch
from .memory.retriever import Retriever, RetrieverLimitsOverride
from .memory.schema import ChunkInput, PromptPack, RetrieveRequest
from .memory.store import MemoryStore
from .memory.summarizer import Summarizer
from .memory.tick_pipeline import TickPipeline

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """You are the Simworld App Brain.

CORE PRINCIPLES
1) Truth separation: All balances, positions, and numerics come from the database (“state”). You may summarize/reason about them, but never invent or infer missing numbers.
2) Memory architecture: Long-term facts live in entities/attributes/relations; events are the append-only timeline; daily/entity state are numeric roll-ups; summaries are compressed narratives; RAG chunks are searchable memory.
3) Mode-aware outputs: Behave differently for 'simulation', 'status', and 'narrative_long' modes.

INPUTS YOU WILL RECEIVE (examples):
- app_config: { mode, token_budget, date, locale }
- state_scope: { entity_ids[], date_range, neighbor_hops }
- retrieved:
  - states_recent[]           // entity_state rows (last 7–14 days or as provided)
  - events_recent[]           // last 30–60 days filtered by links
  - arc_chunks[]              // RAG chunks (summaries, policies, arcs), newest first
  - global_rules[]            // policies, constraints, style rules (stable)
- question? (optional)        // user’s question or task for this call

STRICT OUTPUT FORMAT
Always return a top-level JSON object followed by an optional markdown narrative (if requested by mode). First produce JSON, then (if requested) produce narrative starting with a line “--- NARRATIVE ---”.

JSON schema:
{
  "metadata": {
    "mode": "simulation" | "status" | "narrative_long",
    "date": "{{today}}",
    "token_budget_used": <int_estimate>,
    "warnings": [string]
  },
  "answers": {
    // for status/Q&A calls
    "summary": "plain text under ~500 words",
    "facts": [ { "entity_id": string, "key": string, "value": any, "source": "state|event|chunk", "ts": string } ]
  },
  "proposals": {
    // for simulation planning calls: decisions the sim could take
    "actions": [ { "id": string, "title": string, "rationale": string, "effects": [ { "entity_id": string, "key": string, "delta": number } ] } ]
  },
  "writebacks": {
    // never write numerics that you haven't been given; propose events/summaries only
    "events": [ { "ts": string, "actor_id": string|null, "type": string, "payload": object, "links": [string] } ],
    "entity_summaries": [ { "date": string, "entity_id": string, "summary": string } ],
    "daily_summary": { "date": string, "summary": string } | null,
    "arc_summaries": [ { "id": string, "title": string, "summary": string, "tags": [string] } ]
  }
}

MODE BEHAVIOR
- simulation:
  - Be concise. Prefer bullet facts & clear action proposals.
  - Output JSON heavily; narrative optional and brief (<800 words).
- status:
  - Direct Q&A. Cite sources via lightweight “facts[]” entries referencing 'state'/'event'/'chunk'.
  - Keep to <= 600 words narrative if any.
- narrative_long:
  - Produce rich story after JSON. Narrative may be 60k+ tokens if budget allows.
  - Maintain continuity using arc_chunks and recent states; keep numbers consistent with state.

TOKEN DISCIPLINE
- Stay within app_config.token_budget. If near limit:
  1) Shorten narrative; 2) Trim minor subplots; 3) Prefer per-entity daily summaries over raw events.
- Do not restate large inputs. Refer to them succinctly.
- If critical info is missing, add a warning in metadata.warnings and proceed conservatively.

REASONING RULES
- Numeric ground truth: Use latest entity_state/state values. If a number is absent, do not fabricate—explain uncertainty.
- Temporal consistency: Prefer newer data; when summarizing spans, note date ranges.
- Identity consistency: Use canonical entity_ids and names as provided; don’t alias without instruction.

STYLE RULES
- Plain, precise, audit-friendly language.
- For narrative_long, maintain character/setting consistency; weave in only verified facts.
- No hidden assumptions about finances, health, or legal matters.

FAIL-SAFE
- If instructions conflict with truth separation, follow truth separation and note the conflict in metadata.warnings.
"""


@dataclass(frozen=True)
class ModeProfile:
    name: str
    max_tokens: int
    max_output_tokens: int
    chunk_limit: int
    event_limit: int
    states_days: int


DEFAULT_MODES: Dict[str, ModeProfile] = {
    "simulation": ModeProfile(name="simulation", max_tokens=20_000, max_output_tokens=2_000, chunk_limit=30, event_limit=500, states_days=14),
    "status": ModeProfile(name="status", max_tokens=15_000, max_output_tokens=1_500, chunk_limit=20, event_limit=400, states_days=10),
    "narrative_long": ModeProfile(name="narrative_long", max_tokens=60_000, max_output_tokens=60_000, chunk_limit=60, event_limit=800, states_days=28),
}


@dataclass
class BrainResponse:
    narrative: str
    analysis: Dict[str, object]
    prompt_tokens: int
    mode: str


class AppBrain:
    def __init__(self, *, config: Optional[MemoryConfig] = None) -> None:
        self.config = config or load_memory_config()
        engine = create_engine_from_config(self.config)
        self.store = MemoryStore(engine, self.config)
        self.store.ensure_schema()
        self.retriever = Retriever(self.store, self.config)
        self.summarizer = Summarizer(self.config)
        self.chunker = Chunker(self.config)
        self.pipeline = TickPipeline(self.store, self.config)

    # ------------------------------------------------------------------
    def reason(
        self,
        question: str,
        *,
        entity_scope: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        mode: str = "simulation",
    ) -> BrainResponse:
        profile = DEFAULT_MODES.get(mode, DEFAULT_MODES["simulation"])
        retrieve_request = RetrieveRequest(question=question, entity_scope=entity_scope or [], keywords=keywords or [])
        limits = RetrieverLimitsOverride(
            chunks=profile.chunk_limit,
            events=profile.event_limit,
            states_days=profile.states_days,
        )
        prompt_pack = self.retriever.retrieve(retrieve_request, limits_override=limits)
        trimmed_pack, token_estimate = self._enforce_budget(prompt_pack, profile)
        response = self._call_llm(
            trimmed_pack,
            question=question,
            mode=profile,
            max_tokens=profile.max_output_tokens,
            token_estimate=token_estimate,
        )
        self._persist_brain_output(response, question, mode)
        return response

    def narrate_daily_tick(self, day: date) -> BrainResponse:
        question = f"Provide a narrative recap for {day.isoformat()} incorporating key events and outcomes."
        return self.reason(question, mode="narrative_long")

    def summarize_entity_day(self, entity_id: str, state: dict, events: List[dict], day: date) -> str:
        return self.summarizer.summarize_entity_day(entity_id, state, events, day)

    def summarize_global_day(self, global_state: dict, headlines: List[str], day: date) -> str:
        return self.summarizer.summarize_daily(global_state, headlines, day)

    # ------------------------------------------------------------------
    def _enforce_budget(self, pack: PromptPack, profile: ModeProfile) -> tuple[PromptPack, int]:
        working_pack = PromptPack(**pack.model_dump())
        estimate = _estimate_tokens(working_pack)
        if estimate <= profile.max_tokens:
            return working_pack, estimate

        # Shrink plan: drop older events, halve chunks, reduce states window
        if working_pack.events:
            working_pack.events = working_pack.events[: profile.event_limit // 2]
        if working_pack.chunks:
            working_pack.chunks = working_pack.chunks[: max(10, profile.chunk_limit // 2)]
        if working_pack.states:
            working_pack.states = working_pack.states[: min(len(working_pack.states), profile.states_days)]
        estimate = _estimate_tokens(working_pack)
        if estimate > profile.max_tokens:
            working_pack.chunks = working_pack.chunks[:10]
            working_pack.events = working_pack.events[:200]
            estimate = _estimate_tokens(working_pack)
        return working_pack, estimate

    def _call_llm(
        self,
        pack: PromptPack,
        *,
        question: str,
        mode: ModeProfile,
        max_tokens: int,
        token_estimate: int,
    ) -> BrainResponse:
        today_iso = date.today().isoformat()
        system_prompt = SYSTEM_PROMPT_TEMPLATE.replace("{{today}}", today_iso)
        payload = pack.model_dump()
        app_config = {
            "mode": mode.name,
            "token_budget": mode.max_tokens,
            "date": today_iso,
            "locale": "en-AU",
        }
        state_scope = {
            "entity_ids": pack.entities,
            "date_range": sorted({state.date.isoformat() for state in pack.states}) if pack.states else [],
            "neighbor_hops": 1,
        }
        retrieved = {
            "states_recent": payload.get("states", []),
            "events_recent": payload.get("events", []),
            "arc_chunks": payload.get("chunks", []),
            "global_rules": [],
        }
        user_prompt = {
            "mode": mode.name,
            "question": question,
            "app_config": app_config,
            "state_scope": state_scope,
            "retrieved": retrieved,
            "prompt_pack": payload,
        }
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False, default=_json_default)},
        ]
        if self.config.llm_enabled:
            try:
                result = _invoke_llm(messages, self.config, max_tokens)
                return self._parse_brain_response(result, mode, payload)
            except Exception as exc:  # pragma: no cover
                logger.warning("brain.llm_failed", exc_info=exc)
        # Fallback deterministic response
        narrative = _fallback_narrative(question, payload)
        analysis = {"summary": "deterministic-fallback", "question": question, "entities": payload.get("entities", [])}
        response = BrainResponse(narrative=narrative, analysis=analysis, prompt_tokens=token_estimate, mode=mode.name)
        return response

    def _parse_brain_response(self, raw: Dict[str, object], mode: ModeProfile, payload: Dict[str, object]) -> BrainResponse:
        try:
            choices = raw["choices"][0]
            message = choices["message"]["content"]
            json_text = message
            narrative = ""
            if "--- NARRATIVE ---" in message:
                json_text, narrative_part = message.split("--- NARRATIVE ---", 1)
                narrative = narrative_part.strip()
            parsed = json.loads(json_text.strip())
            analysis = parsed
            if not narrative:
                narrative_field = parsed.get("narrative")
                if isinstance(narrative_field, str):
                    narrative = narrative_field
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            logger.warning("brain.parse_fallback", exc_info=exc)
            analysis = {"raw": raw}
            narrative = str(raw)
        prompt_tokens = raw.get("usage", {}).get("prompt_tokens", _estimate_tokens(PromptPack(**payload)))
        response = BrainResponse(narrative=narrative, analysis=analysis, prompt_tokens=prompt_tokens, mode=mode.name)
        return response

    def _persist_brain_output(self, response: BrainResponse, question: str, mode: str) -> None:
        if not response.narrative:
            return
        chunk_inputs = self.chunker.chunk_text(
            response.narrative,
            ref_type="brain_output",
            ref_id=mode,
            meta={"mode": mode, "question": question, "analysis": response.analysis},
        )
        if not chunk_inputs:
            return
        records = self.store.add_chunks(chunk_inputs)
        if self.config.vector_dim and records:
            vectors = embed_batch((record.text for record in records), self.config)
            pairs = list(zip([record.id for record in records], vectors))
            self.store.add_embeddings(pairs)


def _invoke_llm(messages: List[Dict[str, object]], config: MemoryConfig, max_tokens: int) -> Dict[str, object]:
    base = config.llm_api_base.rstrip("/")
    endpoint = f"{base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.llm_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.llm_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    with httpx.Client(timeout=config.http_timeout) as client:
        response = client.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


def _fallback_narrative(question: str, payload: Dict[str, object]) -> str:
    states = payload.get("states", [])
    entities = [state.get("entity_id") for state in states[:5]]
    summary_parts = [f"Entities in scope: {', '.join(e for e in entities if e)}."]
    events = payload.get("events", [])
    if events:
        summary_parts.append(f"Recent events considered: {len(events)}")
    chunks = payload.get("chunks", [])
    if chunks:
        summary_parts.append(f"Knowledge snippets: {len(chunks)}")
    summary_parts.append(f"Question: {question}")
    return " ".join(summary_parts)


def _estimate_tokens(pack: PromptPack) -> int:
    total = 0
    total += sum(_approx_tokens(chunk.text) for chunk in pack.chunks)
    total += sum(_approx_tokens(json.dumps(state.state)) for state in pack.states)
    total += sum(_approx_tokens(json.dumps(event.payload or {})) for event in pack.events)
    if pack.daily and pack.daily.summary:
        total += _approx_tokens(pack.daily.summary)
    total += 500  # system overhead
    return total


def _approx_tokens(text: str) -> int:
    words = text.split()
    return max(1, int(len(words) * 1.2))


def _json_default(value):
    if isinstance(value, (date,)):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


__all__ = ["AppBrain", "BrainResponse", "ModeProfile", "DEFAULT_MODES"]
