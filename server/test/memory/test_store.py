from datetime import date, datetime, timezone

from server.src.memory.ids import person_id
from server.src.memory.schema import AttributeSet, ChunkInput, DailyStateWrite, EntityStateWrite, EntityUpsert, EventCreate, RelationSet
from server.src.memory.store import MemoryStore


def test_store_round_trip(memory_store: MemoryStore):
    entity = memory_store.upsert_entity(EntityUpsert(kind="person", name="Tester"))
    memory_store.set_attribute(
        AttributeSet(
            entity_id=entity.id,
            key="title",
            value={"value": "Lead"},
            valid_from=datetime.now(timezone.utc),
        )
    )
    other = memory_store.upsert_entity(EntityUpsert(id=person_id("Partner"), kind="person", name="Partner"))
    memory_store.add_relation(
        RelationSet(
            src_id=entity.id,
            dst_id=other.id,
            rel="ally",
            valid_from=datetime.now(timezone.utc),
            weight=0.8,
        )
    )

    event = memory_store.append_event(
        EventCreate(
            ts=datetime.now(timezone.utc),
            actor_id=entity.id,
            type="note",
            payload={"mood": "positive"},
            links=[entity.id, other.id],
        )
    )
    assert event.id is not None

    state_record = memory_store.write_entity_state(
        EntityStateWrite(
            date=date.today(),
            entity_id=entity.id,
            state={"cash": 1000},
            summary="Tester has $1000",
        )
    )
    assert state_record.summary == "Tester has $1000"

    memory_store.write_daily_state(
        DailyStateWrite(date=date.today(), global_state={"entities": 2}, summary="All steady")
    )

    chunks = memory_store.add_chunks(
        [
            ChunkInput(ref_type="entity_state", ref_id=entity.id, ts=datetime.now(timezone.utc), text="Tester chunk", meta={"entity_id": entity.id})
        ]
    )
    assert len(chunks) == 1

    vector = [0.1] * memory_store.config.vector_dim
    embeddings = memory_store.add_embeddings([(chunks[0].id, vector)])
    assert len(embeddings) == 1

    latest_state = memory_store.get_latest_entity_state(entity.id)
    assert latest_state is not None
    assert latest_state.summary == "Tester has $1000"
