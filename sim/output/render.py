from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import List


class DailyRenderer:
    """Mirrors daily messages to stdout and disk."""

    def __init__(self, *, fast: bool = False, logs_dir: str = ".sim_logs") -> None:
        self.fast = fast
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._day_lines: List[str] = []
        self._activity_count = 0
        self._current_path: Path | None = None

    def start_day(self, day: date, *, index: int) -> None:
        header = f"=== {day.isoformat()} (Day {index}) ==="
        self._day_lines = [header]
        self._activity_count = 0
        self._current_path = self.logs_dir / f"{day.isoformat()}.log"
        print(header)

    def log(self, message: str | None) -> None:
        if not message:
            return
        self._day_lines.append(message)
        self._activity_count += 1
        if not self.fast:
            print(message)

    def ensure_quiet(self) -> None:
        if self._activity_count == 0:
            self.log("(quiet day)")

    def end_day(self) -> None:
        if not self._current_path:
            raise RuntimeError("Renderer end_day called before start_day")
        self._current_path.write_text("\n".join(self._day_lines) + "\n", encoding="utf-8")
        self._day_lines = []
        self._current_path = None
