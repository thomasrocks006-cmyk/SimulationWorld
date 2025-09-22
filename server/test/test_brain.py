from datetime import date

import os

from server.src.brain import AppBrain, DEFAULT_MODES
from server.src.memory.schema import DailyStateWrite, EntityStateWrite, EntityUpsert, TickRunRequest


def _configure_env(tmp_path):
    os.environ.setdefault("MEMORY_ENABLED", "true")
    os.environ.setdefault("MEMORY_DB_VENDOR", "sqlite")
    os.environ.setdefault("MEMORY_DB_URL", f"sqlite:///{tmp_path / 'brain.db'}")
    os.environ.setdefault("VECTOR_DIM", "16")


def test_brain_reason_fallback(tmp_path):
    _configure_env(tmp_path)
    brain = AppBrain()

    today = date(2025, 9, 21)
    brain.store.upsert_entity(EntityUpsert(id="entity:tester", kind="person", name="Tester"))
    tick = TickRunRequest(
        date=today,
        entities=[
            EntityStateWrite(
                date=today,
                entity_id="entity:tester",
                state={"cash_usd": 1000, "token_origin_units": 5000},
                summary="Tester holds 1000 USD and 5000 ORIGIN tokens.",
            )
        ],
        global_state=DailyStateWrite(date=today, global_state={"total_cash": 1000}),
        events=[],
    )
    brain.pipeline.run(tick)

    response = brain.reason("How is tester doing?", entity_scope=["entity:tester"], mode="simulation")

    assert response.mode == "simulation"
    assert "tester" in response.narrative.lower()

    chunks = brain.store.keyword_search_chunks("tester", 5)
    assert any(chunk.ref_type == "brain_output" for chunk in chunks)


def test_brain_mode_profiles(tmp_path):
    _configure_env(tmp_path)
    brain = AppBrain()
    response = brain.narrate_daily_tick(date(2025, 9, 22))
    assert response.mode == "narrative_long"
    assert response.prompt_tokens <= DEFAULT_MODES["narrative_long"].max_tokens
