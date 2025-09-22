from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Dict, List

from sim import config as sim_config
from sim.world.state import WorldState

from .config import MemoryConfig, create_engine_from_config
from .ids import business_id, person_id, security_id
from .schema import DailyStateWrite, EntityStateWrite, EntityUpsert, EventCreate, TickRunRequest
from .store import MemoryStore
from .tick_pipeline import TickPipeline


@dataclass
class MemoryBridge:
    """Synchronises simulation days into the memory store."""

    store: MemoryStore
    pipeline: TickPipeline
    config: MemoryConfig
    person_ids: Dict[str, str] = field(default_factory=dict)
    global_entity_id: str = field(default_factory=lambda: business_id("simulation_world"))
    security_entity_id: str = field(default_factory=lambda: security_id(sim_config.COIN_SYMBOL))

    @classmethod
    def from_config(cls, config: MemoryConfig) -> "MemoryBridge":
        engine = create_engine_from_config(config)
        store = MemoryStore(engine, config)
        store.ensure_schema()
        pipeline = TickPipeline(store, config)
        bridge = cls(store=store, pipeline=pipeline, config=config)
        bridge._ensure_static_entities()
        return bridge

    def on_day_complete(self, day: date, world_state: WorldState) -> None:
        self._sync_people(world_state)
        request = self._build_tick_request(day, world_state)
        correlation = f"sim-{day.isoformat()}"
        self.pipeline.run(request, correlation_id=correlation)

    # ------------------------------------------------------------------

    def _ensure_static_entities(self) -> None:
        self.store.upsert_entity(
            EntityUpsert(id=self.global_entity_id, kind="business", name="Simulation World")
        )
        self.store.upsert_entity(
            EntityUpsert(id=self.security_entity_id, kind="security", name=sim_config.COIN_SYMBOL)
        )

    def _sync_people(self, world_state: WorldState) -> None:
        for person_key, person in world_state.people.items():
            memory_id = self.person_ids.get(person_key)
            if not memory_id:
                memory_id = person_id(person.name or person_key)
                self.person_ids[person_key] = memory_id
            self.store.upsert_entity(
                EntityUpsert(
                    id=memory_id,
                    kind="person",
                    name=person.name,
                    meta={
                        "base_city": person.base_city,
                        "traits": person.traits,
                        "occupation": person.occupation,
                    },
                )
            )

    def _build_tick_request(self, day: date, world_state: WorldState) -> TickRunRequest:
        entities: List[EntityStateWrite] = []
        total_cash = 0.0
        total_equities = 0.0
        total_tokens = 0.0

        for person_key, person in world_state.people.items():
            memory_id = self.person_ids[person_key]
            holdings = person.holdings
            state_payload: Dict[str, float] = {
                "cash_usd": round(holdings.cash_usd, 2),
                "equities_usd": round(holdings.equities_usd, 2),
            }
            total_cash += holdings.cash_usd
            total_equities += holdings.equities_usd
            for symbol, units in holdings.tokens.items():
                state_payload[f"token_{symbol}_units"] = round(units, 4)
                if symbol == sim_config.COIN_SYMBOL:
                    total_tokens += units
            entities.append(
                EntityStateWrite(date=day, entity_id=memory_id, state=state_payload)
            )

        coin_price = None
        try:
            coin_price = world_state.price_for(day)
        except Exception:
            pass

        security_state = {
            "symbol": sim_config.COIN_SYMBOL,
        }
        if coin_price is not None:
            security_state["price_usd"] = round(coin_price, 6)
        security_state["circulating_units"] = round(total_tokens, 4)
        entities.append(
            EntityStateWrite(date=day, entity_id=self.security_entity_id, state=security_state)
        )

        global_state_payload: Dict[str, float] = {
            "people_count": len(world_state.people),
            "total_cash_usd": round(total_cash, 2),
            "total_equities_usd": round(total_equities, 2),
            "total_token_units": round(total_tokens, 4),
        }
        if coin_price is not None:
            global_state_payload[f"{sim_config.COIN_SYMBOL.lower()}_price_usd"] = round(coin_price, 6)
        for key, value in world_state.metrics.items():
            if isinstance(value, (int, float)):
                global_state_payload[f"metric_{key}"] = float(value)

        headlines = world_state.journal[-3:]
        daily_summary = DailyStateWrite(date=day, global_state=global_state_payload)
        events = self._build_events(day, headlines)

        return TickRunRequest(
            date=day,
            entities=entities,
            global_state=daily_summary,
            events=events,
        )

    def _build_events(self, day: date, journal_tail: List[str]) -> List[EventCreate]:
        events: List[EventCreate] = []
        base_ts = datetime.combine(day, time(hour=21, minute=0))
        for index, line in enumerate(journal_tail):
            if not line:
                continue
            events.append(
                EventCreate(
                    ts=base_ts.replace(minute=base_ts.minute + index * 5),
                    actor_id=self.global_entity_id,
                    type="journal",
                    payload={"entry": line},
                    links=[self.global_entity_id],
                )
            )
        return events


__all__ = ["MemoryBridge"]
