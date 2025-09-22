from __future__ import annotations

from fastapi import FastAPI

from .src.memory.config import load_memory_config
from .src.memory.routes import build_memory_router
from .src.simulations import build_simulation_router


def create_app() -> FastAPI:
    config = load_memory_config()
    app = FastAPI(title="Simulation Memory API", version="0.1.0")

    memory_router = build_memory_router(config=config, start_scheduler=False)
    app.include_router(memory_router)

    simulation_router = build_simulation_router()
    app.include_router(simulation_router)

    @app.get("/health", tags=["system"])
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()


__all__ = ["app", "create_app"]
