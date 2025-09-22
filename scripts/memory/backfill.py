from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List

from server.src.memory.config import MemoryConfig, create_engine_from_config, load_memory_config
from server.src.memory.schema import DailyStateWrite, EntityStateWrite, EventCreate, TickRunRequest
from server.src.memory.store import MemoryStore
from server.src.memory.tick_pipeline import TickPipeline


def build_config() -> MemoryConfig:
    env = dict(os.environ)
    env.setdefault("MEMORY_ENABLED", "true")
    env.setdefault("MEMORY_DB_URL", env.get("MEMORY_DB_URL", "sqlite:///./memory_backfill.db"))
    env.setdefault("MEMORY_DB_VENDOR", env.get("MEMORY_DB_VENDOR", "sqlite"))
    return load_memory_config(env)


def parse_csv(path: Path) -> List[TickRunRequest]:
    per_day_entities: Dict[date, Dict[str, Dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    per_day_events: Dict[date, List[EventCreate]] = defaultdict(list)

    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row_date = date.fromisoformat(row["date"])
            entity_id = row["entity_id"]
            metric = row.get("metric") or "value"
            value = float(row.get("value") or 0)
            per_day_entities[row_date][entity_id][metric] = value
            per_day_events[row_date].append(
                EventCreate(
                    ts=datetime.fromisoformat(row.get("ts") or f"{row['date']}T00:00:00"),
                    actor_id=row.get("actor_id"),
                    type=row.get("type") or "txn",
                    payload={"metric": metric, "value": value},
                    links=[entity_id],
                )
            )

    requests: List[TickRunRequest] = []
    for day in sorted(per_day_entities.keys()):
        entities_states = [
            EntityStateWrite(date=day, entity_id=eid, state=state)
            for eid, state in per_day_entities[day].items()
        ]
        global_state = {"entities": len(entities_states), "total_events": len(per_day_events[day])}
        requests.append(
            TickRunRequest(
                date=day,
                entities=entities_states,
                global_state=DailyStateWrite(date=day, global_state=global_state),
                events=per_day_events[day],
            )
        )
    return requests


def backfill(path: Path) -> None:
    config = build_config()
    engine = create_engine_from_config(config)
    store = MemoryStore(engine, config)
    store.ensure_schema()
    pipeline = TickPipeline(store, config)

    requests = parse_csv(path)
    for request in requests:
        pipeline.run(request)
    print(f"Backfilled {len(requests)} tick(s) from {path}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill memory events and states from CSV")
    parser.add_argument("path", type=Path, help="CSV file with date,entity_id,metric,value columns")
    args = parser.parse_args()
    backfill(args.path)


if __name__ == "__main__":
    main()
