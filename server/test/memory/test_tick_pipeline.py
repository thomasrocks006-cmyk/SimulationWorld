from datetime import date, datetime, timezone

from server.src.memory.schema import DailyStateWrite, EntityStateWrite, EntityUpsert, EventCreate, TickRunRequest
from server.src.memory.tick_pipeline import TickPipeline


def test_tick_pipeline_creates_summaries(memory_store, memory_config):
    pipeline = TickPipeline(memory_store, memory_config)
    today = date.today()
    memory_store.upsert_entity(EntityUpsert(id="entity:tester", kind="person", name="Tester"))
    request = TickRunRequest(
        date=today,
        entities=[
            EntityStateWrite(date=today, entity_id="entity:tester", state={"cash": 1000}),
        ],
        global_state=DailyStateWrite(date=today, global_state={"cash_total": 1000}),
        events=[
            EventCreate(
                ts=datetime.now(timezone.utc),
                actor_id="entity:tester",
                type="txn",
                payload={"amount": 1000},
                links=["entity:tester"],
            )
        ],
    )

    result = pipeline.run(request)
    assert result["entity_states"] == 1
    state = memory_store.get_latest_entity_state("entity:tester")
    assert state is not None and state.summary
    chunks = memory_store.keyword_search_chunks("tester", 10)
    assert chunks
