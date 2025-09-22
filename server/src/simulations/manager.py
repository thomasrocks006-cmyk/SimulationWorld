from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

from .schema import SimulationLaunchRequest, SimulationRunStatus
from .service import run_simulation


logger = logging.getLogger(__name__)


@dataclass
class SimulationRun:
    run_id: str
    scenario: str
    payload: SimulationLaunchRequest
    status: str = "queued"
    submitted_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    message: Optional[str] = None
    result: Optional[dict] = None
    _future: Optional[Future] = field(default=None, repr=False, compare=False)

    def to_status(self) -> SimulationRunStatus:
        return SimulationRunStatus(
            run_id=self.run_id,
            scenario=self.scenario,
            status=self.status,  # type: ignore[arg-type]
            submitted_at=self.submitted_at,
            started_at=self.started_at,
            finished_at=self.finished_at,
            duration_seconds=self.duration_seconds,
            message=self.message,
            metadata=self.payload.metadata,
            parameters=self.payload,
            result=self.result,
        )


class SimulationRunManager:
    """Coordinates background simulation execution and exposes status lookups."""

    def __init__(self, *, max_workers: int = 1) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._runs: Dict[str, SimulationRun] = {}
        self._lock = threading.Lock()

    def start(self, payload: SimulationLaunchRequest) -> SimulationRun:
        run_id = uuid.uuid4().hex
        run = SimulationRun(run_id=run_id, scenario=payload.scenario, payload=payload)
        logger.info("simulation.run.queued", extra={"run_id": run_id, "scenario": payload.scenario})
        with self._lock:
            self._runs[run_id] = run

        future = self._executor.submit(self._execute_run, run_id, payload)
        run._future = future
        future.add_done_callback(lambda _: self._finalise_run(run_id))
        return run

    def get(self, run_id: str) -> Optional[SimulationRun]:
        with self._lock:
            return self._runs.get(run_id)

    def list(self) -> Dict[str, SimulationRunStatus]:
        with self._lock:
            return {run_id: run.to_status() for run_id, run in self._runs.items()}

    def _execute_run(self, run_id: str, payload: SimulationLaunchRequest) -> None:
        run = self.get(run_id)
        if not run:
            return

        run.started_at = datetime.utcnow()
        run.status = "running"
        with self._lock:
            self._runs[run_id] = run

        start_time = datetime.utcnow()
        try:
            result = run_simulation(payload)
            run.result = result
            run.status = "completed"
            run.message = result.get("message") if isinstance(result, dict) else None
            logger.info(
                "simulation.run.completed",
                extra={"run_id": run_id, "scenario": payload.scenario, "result": result},
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            run.status = "failed"
            run.message = str(exc)
            logger.exception(
                "simulation.run.failed",
                extra={"run_id": run_id, "scenario": payload.scenario},
            )
        finally:
            run.finished_at = datetime.utcnow()
            run.duration_seconds = (run.finished_at - start_time).total_seconds()
            with self._lock:
                self._runs[run_id] = run

    def _finalise_run(self, run_id: str) -> None:
        run = self.get(run_id)
        if not run:
            return
        # Eventual hook for cleanup; kept for symmetry/debug logging.
        logger.debug(
            "simulation.run.finalised",
            extra={
                "run_id": run_id,
                "status": run.status,
                "duration_seconds": run.duration_seconds,
            },
        )


__all__ = ["SimulationRunManager", "SimulationRun"]
