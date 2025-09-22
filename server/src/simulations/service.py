from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from sim.engines.rng import RNG
from sim.engines.scheduler import SimulationScheduler
from sim.output.render import DailyRenderer
from sim.time import SimClock
from sim.world.state import WorldState

from .schema import SimulationLaunchRequest


logger = logging.getLogger(__name__)


def _resolve_memory_bridge() -> Any | None:
    try:
        from server.src.memory.config import load_memory_config
        from server.src.memory.integration import MemoryBridge

        memory_config = load_memory_config()
        if memory_config.enabled:
            logger.info(
                "simulation.memory.enabled",
                extra={"db": memory_config.db_vendor},
            )
            return MemoryBridge.from_config(memory_config)
    except Exception:  # pragma: no cover - optional dependency
        logger.exception("simulation.memory.load_failed")
    return None


def run_simulation(payload: SimulationLaunchRequest) -> Dict[str, Any]:
    """Run the world simulation synchronously based on the supplied payload."""

    logger.info(
        "simulation.run.start",
        extra={
            "scenario": payload.scenario,
            "start": payload.start.isoformat(),
            "until": payload.until.isoformat(),
            "step": payload.step,
            "seed": payload.seed,
        },
    )

    memory_bridge = _resolve_memory_bridge()
    clock = SimClock(payload.start, payload.until, step=payload.step)
    state = WorldState.from_files(seed=payload.seed)
    rng = RNG(payload.seed)
    renderer = DailyRenderer(
        fast=payload.fast,
        view=payload.view,
        verbosity=payload.verbosity,
        max_lines=payload.max_lines,
        interactive=payload.interactive,
        seed=payload.seed,
        start=payload.start,
        story_length=payload.story_length,
        story_tone=payload.story_tone,
    )

    scheduler = SimulationScheduler(
        state=state,
        clock=clock,
        renderer=renderer,
        rng=rng,
        interactive=payload.interactive,
        memory_bridge=memory_bridge,
    )
    scheduler.run()

    output_dir = Path("output").resolve()
    saves_dir = Path(".sim_saves").resolve()
    message = (
        "Simulation completed successfully."
        if payload.fast
        else "Simulation completed (full narrative emitted)."
    )
    logger.info("simulation.run.finished", extra={"output": str(output_dir)})

    return {
        "message": message,
        "output_dir": str(output_dir),
        "saves_dir": str(saves_dir),
        "fast": payload.fast,
    }


__all__ = ["run_simulation"]
