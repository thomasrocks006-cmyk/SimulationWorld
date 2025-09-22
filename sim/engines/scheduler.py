from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

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
from sim.world.choices import Choice, pick_choices


@dataclass
class SimulationScheduler:
    state: WorldState
    clock: SimClock
    renderer: DailyRenderer
    rng: RNG
    interactive: bool = False
    memory_bridge: Optional[object] = None

    def run(self) -> None:
        for index, day in enumerate(self.clock, start=1):
            self._run_single_day(day=day, index=index)

    def _run_single_day(self, *, day: date, index: int) -> None:
        calendar_week = ((index - 1) // 7) + 1
        moods = self.state.mood_snapshot()
        location = self.state.primary_location()
        self.renderer.start_day(
            day,
            index=index,
            location=location,
            moods=moods,
            calendar_week=calendar_week,
            rng_seed=self.rng.seed,
            clock_step=self.clock.step,
        )

        run_scripted_events(day, state=self.state, rng=self.rng, renderer=self.renderer)

        apply_finance_rules(day, state=self.state, renderer=self.renderer)
        apply_social_rules(day, state=self.state, rng=self.rng, renderer=self.renderer)
        apply_romance_rules(day, state=self.state, rng=self.rng, renderer=self.renderer)
        apply_legal_rules(day, state=self.state, rng=self.rng, renderer=self.renderer)

        choices: List[Choice] = []
        if self.interactive:
            choices = pick_choices(self.state, day.isoformat(), k=3)

        self.renderer.present_day(
            choices=[{"label": choice.label} for choice in choices] if choices else None
        )

        if self.interactive and choices:
            selection = self.renderer.read_choice_input(len(choices))
            if selection is not None:
                outcome_lines = choices[selection].effect(self.state, day.isoformat())
                self.state.append_journal(outcome_lines)
                self.renderer.present_choice_result(outcome_lines)

        self.renderer.maybe_render_weekly_summary()
        self.renderer.maybe_render_monthly_summary()
        self.renderer.finalise_day()

        self.state.save_snapshot(day)
        if self.memory_bridge:
            try:
                self.memory_bridge.on_day_complete(day, self.state)
            except Exception:  # pragma: no cover - memory bridge is optional
                pass
