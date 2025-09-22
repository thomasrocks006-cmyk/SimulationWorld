from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence


@dataclass
class SectionLine:
    text: str
    priority: int


class DailyRenderer:
    """Structured renderer that produces narrative, concise, or mixed day views."""

    def __init__(
        self,
        *,
        fast: bool = False,
        view: str = "narrative",
        verbosity: str = "normal",
        max_lines: int = 80,
        interactive: bool = False,
        seed: int = 0,
        start: Optional[date] = None,
        story_length: str = "adaptive",
        story_tone: str = "neutral",
    ) -> None:
        self.fast = fast
        self.view = view
        self.verbosity = verbosity
        self.max_lines = max_lines
        self.interactive = interactive
        self.seed = seed
        self.start = start
        self._detail_mode = verbosity == "detailed"
        self._quiet_mode = verbosity == "quiet"
        self.story_length = story_length
        self.story_tone = story_tone
        if self._detail_mode and self.max_lines < 120:
            self.max_lines = 120

        base_run = f"{seed}_{start.isoformat()}" if start else str(seed)
        self.run_id = f"run_{base_run}"

        self.logs_dir = Path(".sim_logs")
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.saves_dir = Path(".sim_saves")
        self.saves_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = Path("output")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.finance_csv_path = self.output_dir / f"finance_{self.run_id}.csv"
        self.social_csv_path = self.output_dir / f"social_{self.run_id}.csv"
        self._ensure_csv_headers()

        self._history: List[Dict[str, object]] = []
        self._last_finance_values: Dict[str, float] = {}

        self._reset_day_state()

    # ------------------------------------------------------------------
    # Public API used by scheduler/rules/events
    # ------------------------------------------------------------------
    def start_day(
        self,
        day: date,
        *,
        index: int,
        location: str,
        moods: Dict[str, int],
        calendar_week: int,
        rng_seed: int,
        clock_step: str,
    ) -> None:
        self._reset_day_state()
        self._day = day
        self._index = index
        self._location = location
        self._moods = moods
        self._calendar_week = calendar_week
        self._rng_seed = rng_seed
        self._clock_step = clock_step

    def add_story_sentence(self, text: str, *, priority: int = 1) -> None:
        self._sections.setdefault("story", []).append(
            SectionLine(text=self._stylize_story(text), priority=priority)
        )

    def add_highlight(self, text: str, *, priority: int = 1) -> None:
        self._sections.setdefault("highlights", []).append(SectionLine(text=text, priority=priority))

    def add_finance_line(
        self,
        text: str,
        *,
        holder: Optional[str] = None,
        value: Optional[float] = None,
        price: Optional[float] = None,
        token_quantity: Optional[float] = None,
        cash: Optional[float] = None,
        priority: int = 2,
    ) -> None:
        self._sections.setdefault("finance", []).append(SectionLine(text=text, priority=priority))
        if holder is not None and value is not None and price is not None:
            entry = {
                "date": self._day.isoformat(),
                "holder": holder,
                "value": value,
                "price": price,
                "token_quantity": token_quantity,
                "cash": cash,
            }
            self._finance_entries.append(entry)

    def add_social_line(self, text: str, *, pair: Optional[str] = None, delta: Optional[float] = None, priority: int = 4) -> None:
        self._sections.setdefault("social", []).append(SectionLine(text=text, priority=priority))
        if pair:
            self._social_records.append(
                {
                    "date": self._day.isoformat(),
                    "pair": pair,
                    "delta": delta,
                    "text": text,
                }
            )

    def add_romance_line(self, text: str, *, priority: int = 4) -> None:
        self._sections.setdefault("romance", []).append(SectionLine(text=text, priority=priority))

    def add_legal_line(self, text: str, *, priority: int = 4) -> None:
        self._sections.setdefault("legal", []).append(SectionLine(text=text, priority=priority))

    def ensure_story_presence(self) -> None:
        if not self._sections.get("story"):
            default = (
                f"A quiet day rolls by in {self._location}. Everyone keeps their heads down,"
                " letting routines do the talking."
            )
            self.add_story_sentence(default, priority=6)
            self.add_highlight("Finance: Portfolios hold steady; no major moves recorded.", priority=5)

    def present_day(self, *, choices: Sequence[dict] | None = None) -> List[str]:
        if not self._quiet_mode:
            self.ensure_story_presence()
        elif not self._sections.get("highlights"):
            self.add_highlight(
                "Finance: Day closes quietly; no new catalysts registered.", priority=2
            )
        self._apply_story_length_policy()
        layout = self._build_layout(choices=choices)
        self._day_lines = layout.copy()
        if not self.fast:
            for line in layout:
                print(line)
        else:
            # Always echo header even in fast mode for traceability.
            print(layout[0])
        return layout

    def read_choice_input(self, count: int) -> Optional[int]:
        try:
            choice = input().strip()
        except EOFError:
            return None
        if choice.lower() == "skip":
            return None
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < count:
                return idx
        print("Invalid choice. Skipping.")
        return None

    def present_choice_result(self, lines: Iterable[str]) -> None:
        for line in lines:
            formatted = f"[CHOICE RESULT] {line}"
            self._day_lines.append(formatted)
            self._choice_payload.append(formatted)
            if not self.fast:
                print(formatted)

    def maybe_render_weekly_summary(self) -> None:
        if self._clock_step == "week" or self._day.weekday() == 6:
            summary = self._summarise_recent(days=7, label="WEEKLY ROLLUP")
            if summary:
                self._day_lines.extend(summary)
                if not self.fast:
                    for line in summary:
                        print(line)

    def maybe_render_monthly_summary(self) -> None:
        if self._day.day == 1:
            summary = self._summarise_recent(days=30, label="MONTHLY SNAPSHOT")
            if summary:
                self._day_lines.extend(summary)
                if not self.fast:
                    for line in summary:
                        print(line)

    def finalise_day(self) -> None:
        if not self._day:
            raise RuntimeError("start_day must be called before finalise_day")
        log_path = self.logs_dir / f"{self._day.isoformat()}.log"
        log_path.write_text("\n".join(self._day_lines) + "\n", encoding="utf-8")

        json_path = self.output_dir / f"day_{self._day.isoformat()}.json"
        payload = {
            "date": self._day.isoformat(),
            "view": self.view,
            "verbosity": self.verbosity,
            "location": self._location,
            "moods": self._moods,
            "sections": self._current_sections_payload,
            "choices": self._choice_payload,
        }
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        self._append_finance_csv()
        self._append_social_csv()

        self._history.append(
            {
                "date": self._day,
                "highlights": [entry.text for entry in self._sections.get("highlights", [])],
                "romance": [entry.text for entry in self._sections.get("romance", [])],
                "legal": [entry.text for entry in self._sections.get("legal", [])],
                "finance_delta": self._compute_finance_delta(),
            }
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _reset_day_state(self) -> None:
        self._day: Optional[date] = None
        self._index: int = 0
        self._calendar_week: int = 0
        self._rng_seed: int = self.seed
        self._clock_step: str = "day"
        self._location: str = ""
        self._moods: Dict[str, int] = {}
        self._sections: Dict[str, List[SectionLine]] = {}
        self._day_lines: List[str] = []
        self._choice_payload: List[str] = []
        self._finance_entries: List[Dict[str, object]] = []
        self._social_records: List[Dict[str, object]] = []
        self._current_sections_payload: Dict[str, List[str]] = {}

    def _ensure_csv_headers(self) -> None:
        if not self.finance_csv_path.exists():
            with self.finance_csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["date", "holder", "price", "token_quantity", "value", "cash"])
        if not self.social_csv_path.exists():
            with self.social_csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["date", "pair", "delta", "note"])

    def _append_finance_csv(self) -> None:
        if not self._finance_entries:
            return
        with self.finance_csv_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            for entry in self._finance_entries:
                writer.writerow(
                    [
                        entry["date"],
                        entry["holder"],
                        f"{entry['price']:.2f}" if entry["price"] is not None else "",
                        f"{entry['token_quantity']:.6f}" if entry["token_quantity"] is not None else "",
                        f"{entry['value']:.2f}" if entry["value"] is not None else "",
                        f"{entry['cash']:.2f}" if entry["cash"] is not None else "",
                    ]
                )

    def _append_social_csv(self) -> None:
        if not self._social_records:
            return
        with self.social_csv_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            for entry in self._social_records:
                writer.writerow(
                    [
                        entry["date"],
                        entry["pair"],
                        entry["delta"] if entry["delta"] is not None else "",
                        entry["text"],
                    ]
                )

    def _build_layout(self, choices: Sequence[dict] | None = None) -> List[str]:
        lines: List[SectionLine] = []
        header = self._build_header_line()
        secondary = self._build_secondary_header()
        lines.append(SectionLine(text=header, priority=0))
        if secondary:
            lines.append(SectionLine(text=secondary, priority=0))

        sections_payload: Dict[str, List[str]] = {}
        order = self._section_order()
        for section in order:
            entries = self._sections.get(section, [])
            rendered = self._render_section(section, entries)
            if rendered:
                sections_payload[section] = [line.text for line in rendered if line.text.strip()]
                lines.extend(rendered)

        rendered_choices: List[SectionLine] = []
        if self.interactive and choices:
            rendered_choices = self._render_choices(choices)
            lines.extend(rendered_choices)
            self._choice_payload = [entry.text for entry in rendered_choices]
        else:
            self._choice_payload = []

        trimmed = self._apply_trimming(lines)

        final_sections: Dict[str, List[str]] = {}
        current_section: Optional[str] = None
        for entry in trimmed:
            text = entry.text
            if text.startswith("[") and text.endswith("]"):
                current_section = text.strip("[]").lower()
                final_sections.setdefault(current_section, [])
            elif current_section is not None:
                final_sections.setdefault(current_section, []).append(text)

        self._current_sections_payload = final_sections
        return [entry.text for entry in trimmed]

    def _build_header_line(self) -> str:
        day_name = self._day.strftime("%a") if self._day else ""
        return f"=== {self._day.isoformat()} ({day_name}) - {self._location} ==="

    def _build_secondary_header(self) -> str:
        if not self._moods:
            return f"Time: Week {self._calendar_week}  |  RNG: {self._rng_seed}"
        mood_tokens = [f"{name} {score}/100" for name, score in self._moods.items()]
        mood_segment = "  ".join(mood_tokens)
        return f"Time: Week {self._calendar_week}  |  RNG: {self._rng_seed}  |  Mood: {mood_segment}"

    def _section_order(self) -> List[str]:
        base_order = ["story", "highlights", "finance", "social", "romance", "legal"]
        if self._quiet_mode:
            base_order = ["highlights", "finance"]
        if self.view == "concise":
            return [section for section in ["highlights", "finance", "story"] if section in base_order]
        if self.view == "mixed":
            return [section for section in base_order]
        return base_order

    def _render_section(self, section: str, entries: List[SectionLine]) -> List[SectionLine]:
        if not entries:
            return []
        heading_map = {
            "story": "[STORY]",
            "highlights": "[HIGHLIGHTS]",
            "finance": "[FINANCE SNAPSHOT]",
            "social": "[SOCIAL & WORK]",
            "romance": "[ROMANCE]",
            "legal": "[LEGAL/EXTERNAL]",
        }
        heading = heading_map.get(section, f"[{section.upper()}]")
        output = [SectionLine(text=heading, priority=0)]
        if section == "highlights":
            for entry in entries:
                output.append(SectionLine(text=f"* {entry.text}", priority=entry.priority))
        elif section == "finance":
            for entry in entries:
                output.append(SectionLine(text=f"- {entry.text}", priority=entry.priority))
        elif section in {"social", "romance", "legal"}:
            for entry in entries:
                output.append(SectionLine(text=f"- {entry.text}", priority=entry.priority))
        else:  # story or other
            for entry in entries:
                output.append(SectionLine(text=entry.text, priority=entry.priority))
        return output

    def _render_choices(self, choices: Sequence[dict]) -> List[SectionLine]:
        lines = [SectionLine(text="[CHOICES] (pick 1 now)", priority=1)]
        for idx, choice in enumerate(choices, start=1):
            lines.append(SectionLine(text=f"{idx}) {choice['label']}", priority=2))
        lines.append(SectionLine(text="Enter choice (1-3) or `skip`:", priority=1))
        return lines

    def _apply_trimming(self, lines: List[SectionLine]) -> List[SectionLine]:
        if len(lines) <= self.max_lines:
            return lines
        # Sort by priority descending (remove higher number first), keeping original order for ties
        indexed = list(enumerate(lines))
        removable = [item for item in indexed if item[1].priority > 0]
        removable.sort(key=lambda item: (-item[1].priority, item[0]))
        to_remove = len(lines) - self.max_lines
        remove_set = {index for index, _ in removable[:to_remove]}
        trimmed = [entry for idx, entry in indexed if idx not in remove_set]
        return trimmed

    def _summarise_recent(self, *, days: int, label: str) -> List[str]:
        if not self._history:
            return []
        cutoff = self._day.toordinal() - days + 1
        window = [entry for entry in self._history if entry["date"].toordinal() >= cutoff]
        if not window:
            return []
        highlights = [text for entry in window for text in entry["highlights"]][:3]
        romance = [text for entry in window for text in entry["romance"]][:2]
        legal = [text for entry in window for text in entry["legal"]][:2]
        pnl = sum(entry["finance_delta"] for entry in window)
        summary = [f"[{label}]"]
        summary.append(f"P&L delta: ${pnl:,.2f}")
        if highlights:
            summary.append("Top interactions: " + "; ".join(highlights))
        if romance:
            summary.append("Romance beats: " + "; ".join(romance))
        if legal:
            summary.append("Legal beats: " + "; ".join(legal))
        summary.append(f"Window: {window[0]['date'].isoformat()} -> {window[-1]['date'].isoformat()}")
        return summary

    def _compute_finance_delta(self) -> float:
        delta = 0.0
        for entry in self._finance_entries:
            holder = entry["holder"]
            value = float(entry["value"]) if entry["value"] is not None else 0.0
            previous = self._last_finance_values.get(holder)
            if previous is not None:
                delta += value - previous
            self._last_finance_values[holder] = value
        return delta

    @property
    def sections_payload(self) -> Dict[str, List[str]]:
        return self._current_sections_payload

    # ------------------------------------------------------------------
    # Story helpers
    # ------------------------------------------------------------------
    def _stylize_story(self, text: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            return cleaned
        tone = self.story_tone
        if tone == "neutral":
            return cleaned
        if tone == "journalistic":
            prefix = "Report: "
            return cleaned if cleaned.lower().startswith(prefix.lower()) else f"{prefix}{cleaned}"
        if tone == "drama":
            return self._append_clause(cleaned, "The pressure is palpable.")
        if tone == "casual":
            return self._append_clause(cleaned, "too right, feels like a proper Melbourne vibe.")
        return cleaned

    def _append_clause(self, base: str, clause: str) -> str:
        trimmed = base.rstrip()
        suffix = clause.strip()
        if not suffix:
            return trimmed
        if not suffix.endswith("."):
            suffix = f"{suffix}."
        if trimmed.endswith(("!", "?", ".")):
            trimmed = trimmed.rstrip("!.?")
        suffix = suffix[0].upper() + suffix[1:]
        return f"{trimmed} - {suffix}"

    def _apply_story_length_policy(self) -> None:
        entries = self._sections.get("story")
        if not entries:
            return
        policy = self.story_length
        if policy == "short":
            allowance = 1
        elif policy == "medium":
            allowance = 3
        elif policy == "long":
            allowance = 6
        else:  # adaptive
            highlight_count = len(self._sections.get("highlights", []))
            finance_count = len(self._sections.get("finance", []))
            activity = highlight_count + finance_count
            if activity >= 6:
                allowance = 5
            elif activity >= 3:
                allowance = 4
            elif activity >= 1:
                allowance = 3
            else:
                allowance = 2
        allowance = max(1, allowance)
        if len(entries) <= allowance:
            return
        tail_text = " ".join(entry.text.strip() for entry in entries[allowance - 1 :] if entry.text.strip())
        trimmed = entries[: allowance - 1] if allowance > 1 else []
        if tail_text:
            trimmed.append(SectionLine(text=tail_text, priority=entries[allowance - 1].priority))
        elif entries:
            trimmed.append(entries[min(len(entries) - 1, allowance - 1)])
        self._sections["story"] = trimmed
