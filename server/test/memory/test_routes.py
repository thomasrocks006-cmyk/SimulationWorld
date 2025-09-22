from datetime import date, datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.src.memory.config import load_memory_config
from server.src.memory.routes import build_memory_router
from server.src.memory.schema import DailyStateWrite, EntityStateWrite, EventCreate, TickRunRequest


def build_app(memory_env):
    config = load_memory_config(memory_env)
    app = FastAPI()
    app.include_router(build_memory_router(config=config))
    return app


def test_memory_routes_flow(memory_env):
    app = build_app(memory_env)
    client = TestClient(app)

    # Ensure status works
    status_response = client.get("/api/memory/status")
    assert status_response.status_code == 200

    # Upsert entity
    entity_payload = {"kind": "person", "name": "Route Tester"}
    entity_response = client.post("/api/memory/entity", json=entity_payload)
    assert entity_response.status_code == 200
    entity_id = entity_response.json()["id"]

    # Append event
    event_payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "actor_id": entity_id,
        "type": "note",
        "links": [entity_id],
    }
    event_response = client.post("/api/memory/event", json=event_payload)
    assert event_response.status_code == 200
    event_id = event_response.json()["id"]

    today = date.today()
    tick_payload = {
        "date": today.isoformat(),
        "entities": [
            {
                "date": today.isoformat(),
                "entity_id": entity_id,
                "state": {"cash": 5000},
            }
        ],
        "global_state": {
            "date": today.isoformat(),
            "global_state": {"cash_total": 5000},
        },
        "events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "actor_id": entity_id,
                "type": "txn",
                "payload": {"amount": 5000},
                "links": [entity_id],
            }
        ],
    }
    tick_response = client.post("/api/memory/tick/run", json=tick_payload)
    assert tick_response.status_code == 200

    latest_state = client.get(f"/api/memory/entity/{entity_id}/state/latest")
    assert latest_state.status_code == 200
    assert latest_state.json()["entity_id"] == entity_id

    retrieve_payload = {"question": "What happened?", "entity_scope": [entity_id]}
    retrieve_response = client.post("/api/memory/retrieve", json=retrieve_payload)
    assert retrieve_response.status_code == 200
    data = retrieve_response.json()
    assert data["entities"]
    assert data["chunks"]

    daily_response = client.get(f"/api/memory/daily/{today.isoformat()}")
    assert daily_response.status_code == 200
