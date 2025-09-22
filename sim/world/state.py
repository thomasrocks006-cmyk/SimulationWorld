from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from sim import config
from sim.entities import Business, Person, Relationship, RealEstate, Vehicle
from sim.world import loaders


@dataclass
class WorldState:
    """Container for all mutable world data."""

    people: Dict[str, Person]
    relationships: List[Relationship]
    real_estate: List[RealEstate]
    vehicles: List[Vehicle]
    businesses: List[Business]
    coin_prices: Dict[date, float]
    seed: int
    metrics: Dict[str, float] = field(default_factory=dict)
    journal: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.coin_symbol = config.COIN_SYMBOL
        self._known_price_days = sorted(self.coin_prices.keys())
        self.metrics = dict(self.metrics)
        self.journal = list(self.journal)

    @classmethod
    def from_files(
        cls,
        base_path: Optional[Path] = None,
        *,
        seed: int = 1337,
    ) -> "WorldState":
        data_root = base_path or Path(__file__).resolve().parents[1] / "data"
        people = loaders.load_people(data_root / "people.yaml")
        relationships = loaders.load_relationships(data_root / "relationships.yaml")
        estates, vehicles, businesses = loaders.load_households(data_root / "households.yaml")
        coin_prices = loaders.load_coin_prices(data_root / "coin_prices.csv")
        return cls(
            people=people,
            relationships=relationships,
            real_estate=estates,
            vehicles=vehicles,
            businesses=businesses,
            coin_prices=coin_prices,
            seed=seed,
        )

    def price_for(self, day: date) -> float:
        if day in self.coin_prices:
            return self.coin_prices[day]
        previous_days = [known for known in self._known_price_days if known < day]
        if previous_days:
            return self.coin_prices[previous_days[-1]]
        raise KeyError(f"No coin price available for {day.isoformat()}")

    def price_for_str(self, ymd: str) -> float:
        return self.price_for(date.fromisoformat(ymd))

    def total_token_quantity(self, symbol: Optional[str] = None) -> float:
        symbol = symbol or self.coin_symbol
        return sum(person.token_quantity(symbol) for person in self.people.values())

    def reset_price_cache(self) -> None:
        self._known_price_days = sorted(self.coin_prices.keys())

    def primary_location(self) -> str:
        candidate = self.people.get("thomas")
        if candidate and candidate.base_city:
            return candidate.base_city
        if self.people:
            fallback = next(iter(self.people.values()))
            return fallback.base_city or "South Yarra, Melbourne"
        return "South Yarra, Melbourne"

    def mood_snapshot(self) -> Dict[str, int]:
        snapshot: Dict[str, int] = {}
        tracked = [pid for pid in ("thomas", "jordy") if pid in self.people]
        if not tracked:
            tracked = list(self.people.keys())[:2]
        for pid in tracked:
            person = self.people[pid]
            base = 55 + (person.traits.get("self_awareness", 5) - 5) * 2
            base += (person.traits.get("loyalty_mates", 5) - 5)
            base += (person.traits.get("money_focus", 5) - 5) * 0.5
            mood = int(max(30, min(90, round(base))))
            label = pid.replace("_", " ").title()
            snapshot[label] = mood
        return snapshot

    def append_journal(self, lines: Iterable[str]) -> None:
        for line in lines:
            if line:
                self.journal.append(line)

    def adjust_metric(self, key: str, delta: float) -> None:
        self.metrics[key] = self.metrics.get(key, 0.0) + delta

    def save_snapshot(self, day: date, directory: Optional[Path] = None) -> None:
        save_dir = directory or Path(".sim_saves")
        save_dir.mkdir(parents=True, exist_ok=True)

        people_payload = {
            pid: {
                "name": person.name,
                "age": person.age,
                "occupation": person.occupation,
                "base_city": person.base_city,
                "holdings": {
                    "cash_usd": person.holdings.cash_usd,
                    "tokens": person.holdings.tokens,
                    "equities_usd": person.holdings.equities_usd,
                },
            }
            for pid, person in self.people.items()
        }

        relationships_payload = [
            {
                "src_id": rel.src_id,
                "dst_id": rel.dst_id,
                "weight": rel.weight,
                "tags": rel.tags,
            }
            for rel in self.relationships
        ]

        snapshot = {
            "date": day.isoformat(),
            "people": people_payload,
            "relationships": relationships_payload,
            "metrics": self.metrics,
            "journal_tail": self.journal[-10:],
        }

        path = save_dir / f"{day.isoformat()}.json"
        path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
