from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler

from .schema import TickRunRequest
from .tick_pipeline import TickPipeline

logger = logging.getLogger(__name__)


TickRequestFactory = Callable[[], Optional[TickRunRequest]]


class MemoryJobManager:
    def __init__(self, pipeline: TickPipeline, fetch_tick: TickRequestFactory | None = None) -> None:
        self.pipeline = pipeline
        self.fetch_tick = fetch_tick
        self.scheduler = BackgroundScheduler(timezone="UTC")
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        logger.info("memory.jobs.start")
        self.scheduler.start()
        if self.fetch_tick:
            self.scheduler.add_job(self._run_daily_tick, "cron", hour=1, id="memory-daily-tick", replace_existing=True)
        self._started = True

    def shutdown(self) -> None:
        if not self._started:
            return
        logger.info("memory.jobs.shutdown")
        self.scheduler.shutdown(wait=False)
        self._started = False

    def trigger_tick(self, request: TickRunRequest | None = None, correlation_id: str | None = None) -> dict:
        payload = request or (self.fetch_tick() if self.fetch_tick else None)
        if not payload:
            logger.warning("memory.jobs.tick_skipped", extra={"correlation_id": correlation_id})
            return {"skipped": True}
        logger.info("memory.jobs.tick_run", extra={"correlation_id": correlation_id, "date": payload.date.isoformat()})
        return self.pipeline.run(payload, correlation_id=correlation_id or _now_correlation())

    def _run_daily_tick(self) -> None:
        try:
            self.trigger_tick()
        except Exception as exc:  # pragma: no cover - background path
            logger.exception("memory.jobs.tick_failed", exc_info=exc)


def _now_correlation() -> str:
    return datetime.now(timezone.utc).strftime("tick-%Y%m%d%H%M%S")


__all__ = ["MemoryJobManager", "TickRequestFactory"]
