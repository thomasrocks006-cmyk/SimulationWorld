from __future__ import annotations

import csv
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import yaml

from sim.entities import Business, Holdings, Person, Relationship, RealEstate, Vehicle


def _read_yaml(path: Path) -> List[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Expected YAML data file at {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or []
        if not isinstance(payload, list):
            raise ValueError(f"Expected list at {path}, got {type(payload).__name__}")
        return payload


def load_people(path: Path) -> Dict[str, Person]:
    people: Dict[str, Person] = {}
    for row in _read_yaml(path):
        holdings = Holdings.from_mapping(row.get("holdings", {}))
        person = Person(
            id=row["id"],
            name=row.get("name", row["id"]),
            age=int(row.get("age", 0)),
            occupation=row.get("occupation", ""),
            base_city=row.get("base_city", ""),
            traits={str(k): int(v) for k, v in (row.get("traits") or {}).items()},
            drives=[str(drive) for drive in row.get("drives", [])],
            holdings=holdings,
        )
        people[person.id] = person
    return people


def load_relationships(path: Path) -> List[Relationship]:
    relationships: List[Relationship] = []
    for row in _read_yaml(path):
        relationships.append(
            Relationship(
                src_id=row["src_id"],
                dst_id=row["dst_id"],
                weight=int(row.get("weight", 0)),
                tags=[str(tag) for tag in row.get("tags", [])],
            )
        )
    return relationships


def load_households(path: Path) -> Tuple[List[RealEstate], List[Vehicle], List[Business]]:
    if not path.exists():
        raise FileNotFoundError(f"Expected YAML data file at {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    real_estate_data = payload.get("real_estate", [])
    vehicle_data = payload.get("vehicles", [])
    business_data = payload.get("businesses", [])

    estates = [
        RealEstate(
            owner_id=item["owner_id"],
            address=item.get("address", ""),
            value_aud=float(item.get("value_aud", 0.0)),
            mortgage_aud=float(item.get("mortgage_aud", 0.0)),
        )
        for item in real_estate_data
    ]

    vehicles = [
        Vehicle(
            owner_id=item["owner_id"],
            make_model=item.get("make_model", ""),
            value_aud=float(item.get("value_aud", 0.0)),
        )
        for item in vehicle_data
    ]

    businesses = [
        Business(
            id=item["id"],
            name=item.get("name", item["id"]),
            sector=item.get("sector", ""),
            valuation_aud=float(item.get("valuation_aud", 0.0)),
            owner_id=item.get("owner_id", ""),
            stress_factor=float(item.get("stress_factor", 0.0)),
        )
        for item in business_data
    ]

    return estates, vehicles, businesses


def load_coin_prices(path: Path) -> Dict[date, float]:
    if not path.exists():
        raise FileNotFoundError(f"Expected CSV data file at {path}")
    prices: Dict[date, float] = {}
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            day = datetime.strptime(row["date"], "%Y-%m-%d").date()
            prices[day] = float(row["price_usd"])
    return prices
