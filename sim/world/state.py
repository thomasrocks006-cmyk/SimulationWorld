from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

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

    def __post_init__(self) -> None:
        self.coin_symbol = config.COIN_SYMBOL
        self._known_price_days = sorted(self.coin_prices.keys())

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

    def total_token_quantity(self, symbol: Optional[str] = None) -> float:
        symbol = symbol or self.coin_symbol
        return sum(person.token_quantity(symbol) for person in self.people.values())

    def reset_price_cache(self) -> None:
        self._known_price_days = sorted(self.coin_prices.keys())
