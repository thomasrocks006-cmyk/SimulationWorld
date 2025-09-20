from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sim.engines.rng import RNG
from sim.output.render import DailyRenderer
from sim.time import SimClock
from sim.world.events import run_scripted_events
from sim.world.rules import (
    apply_finance_rules,
    apply_legal_rules,
    apply_romance_rules,
    apply_social_rules,
)
from sim.world.state import WorldState


@dataclass
class SimulationScheduler:
    state: WorldState
    clock: SimClock
    renderer: DailyRenderer
    rng: RNG

    def run(self) -> None:
        for index, day in enumerate(self.clock, start=1):
            self._run_single_day(day=day, index=index)

    def _run_single_day(self, *, day: date, index: int) -> None:
        self.renderer.start_day(day, index=index)

        run_scripted_events(day, state=self.state, rng=self.rng, renderer=self.renderer)

        apply_finance_rules(day, state=self.state, renderer=self.renderer)
        apply_social_rules(day, state=self.state, rng=self.rng, renderer=self.renderer)
        apply_romance_rules(day, state=self.state, rng=self.rng, renderer=self.renderer)
        apply_legal_rules(day, state=self.state, rng=self.rng, renderer=self.renderer)

        self.renderer.ensure_quiet()
        self.renderer.end_day()
