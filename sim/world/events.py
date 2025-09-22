from __future__ import annotations

from datetime import date
from typing import Iterable, Protocol

from events import special
from sim.engines.rng import RNG
from sim.world.state import WorldState
from sim.output.render import DailyRenderer


class EventCallable(Protocol):
    def __call__(self, renderer: DailyRenderer) -> None:
        ...


def run_scripted_events(
    day: date,
    *,
    state: WorldState,
    rng: RNG,
    renderer: DailyRenderer,
) -> None:
    for event in special.scripted_events(day, state=state, rng=rng):
        event(renderer)
