from __future__ import annotations

import os
from datetime import date, datetime, timezone

from server.src.memory.config import MemoryConfig, create_engine_from_config, load_memory_config
from server.src.memory.ids import person_id, wallet_id
from server.src.memory.schema import DailyStateWrite, EntityStateWrite, EntityUpsert, EventCreate, TickRunRequest
from server.src.memory.store import MemoryStore
from server.src.memory.tick_pipeline import TickPipeline


def build_config() -> MemoryConfig:
    env = dict(os.environ)
    env.setdefault("MEMORY_ENABLED", "true")
    env.setdefault("MEMORY_DB_URL", env.get("MEMORY_DB_URL", "sqlite:///./memory_seed.db"))
    env.setdefault("MEMORY_DB_VENDOR", env.get("MEMORY_DB_VENDOR", "sqlite"))
    return load_memory_config(env)


def seed() -> None:
    config = build_config()
    engine = create_engine_from_config(config)
    store = MemoryStore(engine, config)
    store.ensure_schema()

    thomas_id = person_id("Thomas Francis")
    jordan_id = person_id("Jordan Shreeve")
    origin_wallet = wallet_id("thomas_francis", "origin")

    store.upsert_entity(EntityUpsert(id=thomas_id, kind="person", name="Thomas Francis", meta={"role": "lead"}))
    store.upsert_entity(EntityUpsert(id=jordan_id, kind="person", name="Jordan Shreeve", meta={"role": "lead"}))
    store.upsert_entity(
        EntityUpsert(id=origin_wallet, kind="wallet", name="Origin Wallet", meta={"currency": "ORIGIN"})
    )

    today = date.today()
    pipeline = TickPipeline(store, config)

    tick_request = TickRunRequest(
        date=today,
        entities=[
            EntityStateWrite(
                date=today,
                entity_id=thomas_id,
                state={"cash_usd": 120000, "origin_holdings": 100_000},
            ),
            EntityStateWrite(
                date=today,
                entity_id=jordan_id,
                state={"cash_usd": 95000, "origin_holdings": 100_000},
            ),
            EntityStateWrite(
                date=today,
                entity_id=origin_wallet,
                state={"token": "ORIGIN", "units": 200_000, "price_usd": 0.27},
            ),
        ],
        global_state=DailyStateWrite(
            date=today,
            global_state={"origin_price_usd": 0.27, "narrative": "Calm markets"},
        ),
        events=[
            EventCreate(
                ts=datetime.now(timezone.utc),
                actor_id=origin_wallet,
                type="txn",
                payload={"action": "buy", "amount": 5000},
                links=[thomas_id, jordan_id, origin_wallet],
            )
        ],
    )

    pipeline.run(tick_request)
    print("Seeded memory store with sample entities, events, and states.")


if __name__ == "__main__":
    seed()
