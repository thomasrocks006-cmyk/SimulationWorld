from __future__ import annotations

import argparse
from datetime import datetime, date
from typing import Optional

from sim.engines.rng import RNG
from sim.engines.scheduler import SimulationScheduler
from sim.output.render import DailyRenderer
from sim.time import SimClock
from sim.world.state import WorldState


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
        "--fast",
        action="store_true",
        help="Fast mode (suppress non-critical console output)",
    )

    return parser


def _handle_run(args: argparse.Namespace) -> None:
    if args.until < args.start:
        raise ValueError("End date must be on or after start date.")

    clock = SimClock(args.start, args.until, step=args.step)
    state = WorldState.from_files(seed=args.seed)
    rng = RNG(args.seed)
    renderer = DailyRenderer(fast=args.fast)

    scheduler = SimulationScheduler(
        state=state,
        clock=clock,
        renderer=renderer,
        rng=rng,
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
