from __future__ import annotations

from datetime import date

from sim.engines.rng import RNG
from sim.world.state import WorldState
from sim.output.render import DailyRenderer


def apply_legal_rules(
    day: date,
    *,
    state: WorldState,
    rng: RNG,
    renderer: DailyRenderer,
) -> None:
    """Placeholder for legal milestones."""
    # TODO: Surface ATO milestones that influence Jordy's stress and public reputation.
    _ = (day, state, rng, renderer)
