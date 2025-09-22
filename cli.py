from __future__ import annotations

import argparse
import logging
from datetime import datetime, date
from typing import Optional

from sim.engines.rng import RNG
from sim.engines.scheduler import SimulationScheduler
from sim.output.render import DailyRenderer
from sim.time import SimClock
from sim.world.state import WorldState

logger = logging.getLogger(__name__)


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date format '{value}'. Use YYYY-MM-DD.") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Living World Simulation Engine",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser(
        "run",
        help="Run the simulation over a date range",
    )
    run_parser.add_argument("--start", required=True, type=_parse_date, help="Start date (YYYY-MM-DD)")
    run_parser.add_argument(
        "--until",
        required=True,
        type=_parse_date,
        help="Inclusive end date (YYYY-MM-DD)",
    )
    run_parser.add_argument(
        "--step",
        choices=("day", "week"),
        default="day",
        help="Advance clock by day or week increments (default: day)",
    )
    run_parser.add_argument(
        "--seed",
        type=int,
        default=1337,
        help="Seed for deterministic RNG (default: 1337)",
    )
    run_parser.add_argument(
        "--view",
        choices=("narrative", "concise", "mixed"),
        default="narrative",
        help="Presentation mode for daily output (default: narrative)",
    )
    run_parser.add_argument(
        "--verbosity",
        choices=("quiet", "normal", "detailed"),
        default="normal",
        help="Controls richness of each day's sections (default: normal)",
    )
    run_parser.add_argument(
        "--max-lines",
        type=int,
        default=80,
        help="Maximum lines to render per day (default: 80)",
    )
    run_parser.add_argument(
        "--fast",
        action="store_true",
        help="Fast mode (print headers only to stdout while still logging to disk)",
    )
    run_parser.add_argument(
        "--interactive",
        action="store_true",
        help="Enable interactive branching choices at the end of each day",
    )
    run_parser.add_argument(
        "--story-length",
        choices=("short", "medium", "long", "adaptive"),
        default="adaptive",
        help="Controls story paragraph count per day (default: adaptive)",
    )
    run_parser.add_argument(
        "--story-tone",
        choices=("neutral", "drama", "casual", "journalistic"),
        default="neutral",
        help="Adjusts narrative tone (default: neutral)",
    )

    return parser


def _handle_run(args: argparse.Namespace) -> None:
    if args.until < args.start:
        raise ValueError("End date must be on or after start date.")

    memory_bridge = None
    try:  # optional memory integration
        from server.src.memory.config import load_memory_config
        from server.src.memory.integration import MemoryBridge

        memory_config = load_memory_config()
        if memory_config.enabled:
            memory_bridge = MemoryBridge.from_config(memory_config)
            logger.info("memory.bridge.enabled", extra={"db": memory_config.db_vendor})
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning("memory.bridge.unavailable", exc_info=exc)

    clock = SimClock(args.start, args.until, step=args.step)
    state = WorldState.from_files(seed=args.seed)
    rng = RNG(args.seed)
    renderer = DailyRenderer(
        fast=args.fast,
        view=args.view,
        verbosity=args.verbosity,
        max_lines=args.max_lines,
        interactive=args.interactive,
        seed=args.seed,
        start=args.start,
        story_length=args.story_length,
        story_tone=args.story_tone,
    )

    scheduler = SimulationScheduler(
        state=state,
        clock=clock,
        renderer=renderer,
        rng=rng,
        interactive=args.interactive,
        memory_bridge=memory_bridge,
    )
    scheduler.run()


def main(argv: Optional[list[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        _handle_run(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
