from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from .config import MemoryConfig, create_engine_from_config, load_memory_config
from .retriever import Retriever
from .schema import (
    DailyStateWrite,
    EntityStateWrite,
    EntityUpsert,
    EventCreate,
    EventResponse,
    MemoryStatus,
    PromptPack,
    RetrieveRequest,
    TickRunRequest,
)
from .store import MemoryStore, as_event_response
from .tick_pipeline import TickPipeline
from .jobs import MemoryJobManager


@dataclass
class MemoryContainer:
    config: MemoryConfig
    store: MemoryStore
    retriever: Retriever
    pipeline: TickPipeline
    jobs: MemoryJobManager


def build_memory_router(
    config: Optional[MemoryConfig] = None,
    *,
    start_scheduler: bool = False,
) -> APIRouter:
    cfg = config or load_memory_config()
    engine = create_engine_from_config(cfg)
    store = MemoryStore(engine, cfg)
    store.ensure_schema()
    pipeline = TickPipeline(store, cfg)
    retriever = Retriever(store, cfg)
    jobs = MemoryJobManager(pipeline)
    if start_scheduler and cfg.enabled:
        jobs.start()
    container = MemoryContainer(cfg, store, retriever, pipeline, jobs)

    router = APIRouter(prefix="/api/memory", tags=["memory"])

    def require_enabled() -> MemoryContainer:
        if not container.config.enabled:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Memory subsystem disabled")
        return container

    @router.get("/status", response_model=MemoryStatus)
    def status_endpoint(container: MemoryContainer = Depends(require_enabled)) -> MemoryStatus:
        counts = container.store.get_counts()
        vector_state = "enabled" if container.config.vector_dim else "disabled"
        last_tick = container.store.get_last_chunk_time()
        return MemoryStatus(db=container.config.db_vendor, vector=vector_state, last_tick=last_tick, counts=counts)

    @router.post("/entity", response_model=EntityUpsert)
    def upsert_entity(payload: EntityUpsert, container: MemoryContainer = Depends(require_enabled)) -> EntityUpsert:
        entity = container.store.upsert_entity(payload)
        return EntityUpsert(id=entity.id, kind=entity.kind, name=entity.name, meta=entity.meta or {})

    @router.post("/event", response_model=EventResponse)
    def create_event(payload: EventCreate, container: MemoryContainer = Depends(require_enabled)) -> EventResponse:
        record = container.store.append_event(payload)
        return as_event_response(record)

    @router.post("/tick/run")
    def run_tick(payload: TickRunRequest, container: MemoryContainer = Depends(require_enabled)) -> dict:
        return container.pipeline.run(payload)

    @router.post("/retrieve", response_model=PromptPack)
    def retrieve(payload: RetrieveRequest, container: MemoryContainer = Depends(require_enabled)) -> PromptPack:
        return container.retriever.retrieve(payload)

    @router.get("/entity/{entity_id}/state/latest", response_model=EntityStateWrite)
    def latest_state(entity_id: str, container: MemoryContainer = Depends(require_enabled)) -> EntityStateWrite:
        record = container.store.get_latest_entity_state(entity_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity state not found")
        return EntityStateWrite(date=record.date, entity_id=record.entity_id, state=record.state or {}, summary=record.summary)

    @router.get("/daily/{target_date}", response_model=DailyStateWrite)
    def daily_state(target_date: date, container: MemoryContainer = Depends(require_enabled)) -> DailyStateWrite:
        record = container.store.get_daily_state(target_date)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Daily state not found")
        return DailyStateWrite(date=record.date, global_state=record.global_state or {}, summary=record.summary)

    return router


__all__ = ["build_memory_router", "MemoryContainer"]
