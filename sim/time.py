from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Generator, Iterable


@dataclass
class SimClock:
    """Deterministic simulation clock supporting day/week steps."""

    start: date
    end: date
    step: str = "day"

    def __post_init__(self) -> None:
        if self.step not in {"day", "week"}:
            raise ValueError("step must be 'day' or 'week'")
        if self.end < self.start:
            raise ValueError("end date must not precede start date")
        self.current: date = self.start
        self._index: int = 1

    def tick_day(self) -> date:
        self.current = self.current + timedelta(days=1)
        self._index += 1
        return self.current

    def tick_week(self) -> date:
        self.current = self.current + timedelta(weeks=1)
        self._index += 1
        return self.current

    def advance(self) -> date:
        if self.step == "day":
            return self.tick_day()
        return self.tick_week()

    @property
    def day_index(self) -> int:
        return self._index

    def iter(self) -> Generator[date, None, None]:
        """Yield each timestep inclusive of the end date."""
        self.current = self.start
        self._index = 1
        while self.current <= self.end:
            yield self.current
            if self.current == self.end:
                break
            self.advance()

    def __iter__(self) -> Iterable[date]:
        return self.iter()
