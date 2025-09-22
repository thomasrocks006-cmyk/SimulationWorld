from datetime import date, datetime, timedelta, timezone

from server.src.memory.embeddings import embed_text
from server.src.memory.retriever import Retriever
from server.src.memory.schema import ChunkInput, DailyStateWrite, EntityStateWrite, EntityUpsert, EventCreate, RetrieveRequest


def test_retriever_scores_recent_chunks(memory_store, memory_config):
    retriever = Retriever(memory_store, memory_config)
    entity = memory_store.upsert_entity(EntityUpsert(kind="person", name="Historian"))

    today = date.today()
    memory_store.write_entity_state(
        EntityStateWrite(date=today, entity_id=entity.id, state={"balance": 1234}, summary="Historian balance steady")
    )
    memory_store.write_daily_state(
        DailyStateWrite(date=today, global_state={"mood": "calm"}, summary="Calm day")
    )
    memory_store.append_event(
        EventCreate(
            ts=datetime.now(timezone.utc),
            actor_id=entity.id,
            type="decision",
            payload={"note": "researched"},
            links=[entity.id],
        )
    )

    recent_chunk = memory_store.add_chunks(
        [
            ChunkInput(
                ref_type="entity_state",
                ref_id=entity.id,
                ts=datetime.now(timezone.utc),
                text="Historian recent chunk",
                meta={"entity_id": entity.id},
            )
        ]
    )[0]
    old_chunk = memory_store.add_chunks(
        [
            ChunkInput(
                ref_type="entity_state",
                ref_id=entity.id,
                ts=datetime.now(timezone.utc) - timedelta(days=90),
                text="Historian old chunk",
                meta={"entity_id": entity.id},
            )
        ]
    )[0]

    vector_recent = embed_text("historian recent", memory_config)
    vector_old = embed_text("historian old", memory_config)
    memory_store.add_embeddings(
        [
            (recent_chunk.id, vector_recent),
            (old_chunk.id, vector_old),
        ]
    )

    pack = retriever.retrieve(
        RetrieveRequest(question="What happened to the historian?", entity_scope=[entity.id], keywords=["historian"])
    )

    assert any(state.entity_id == entity.id for state in pack.states)
    assert pack.chunks, "Expected chunks in prompt pack"
    assert pack.chunks[0].id == recent_chunk.id
    assert pack.chunks[0].score >= pack.chunks[-1].score
