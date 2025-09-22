from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from .manager import SimulationRunManager
from .schema import SimulationLaunchRequest, SimulationRunStatus


def build_simulation_router(manager: SimulationRunManager | None = None) -> APIRouter:
    sim_manager = manager or SimulationRunManager()
    router = APIRouter(prefix="/api/simulations", tags=["simulations"])

    @router.post("/launch", response_model=SimulationRunStatus, status_code=status.HTTP_202_ACCEPTED)
    def launch_simulation(payload: SimulationLaunchRequest) -> SimulationRunStatus:
        run = sim_manager.start(payload)
        return run.to_status()

    @router.get("/{run_id}", response_model=SimulationRunStatus)
    def get_simulation(run_id: str) -> SimulationRunStatus:
        run = sim_manager.get(run_id)
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation run not found")
        return run.to_status()

    @router.get("/", response_model=list[SimulationRunStatus])
    def list_simulations() -> list[SimulationRunStatus]:
        return [run.to_status() for run in sim_manager.list().values()]

    return router


__all__ = ["build_simulation_router"]
