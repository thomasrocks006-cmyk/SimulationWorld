from __future__ import annotations

from datetime import date
from typing import Callable, List

from sim import config
from sim.world.state import WorldState
from sim.output.render import DailyRenderer


def scripted_events(
    day: date,
    *,
    state: WorldState,
    rng,
) -> List[Callable[[DailyRenderer], None]]:
    events: List[Callable[[DailyRenderer], None]] = []

    if day == config.INVESTMENT_DATE:
        events.append(lambda renderer: _origin_buy_in(day, state=state, renderer=renderer))

    # TODO: Add hand-authored beats (ATO verdict day, group dinners, ex run-ins).
    _ = rng
    return events


def _origin_buy_in(day: date, *, state: WorldState, renderer: DailyRenderer) -> None:
    price = state.price_for(day)
    symbol = config.COIN_SYMBOL
    quantity = config.INVESTMENT_AMOUNT_USD / price
    for person_id in ("thomas", "jordy"):
        person = state.people.get(person_id)
        if not person:
            continue
        person.adjust_cash(-config.INVESTMENT_AMOUNT_USD)
        person.add_tokens(symbol, quantity)
    renderer.add_story_sentence(
        "Morning haze over Toorak Road. Thomas leans on a half-cold long black, rehearsing his pitch.",
        priority=1,
    )
    renderer.add_story_sentence(
        "By lunch, Jordy's heard it all: supply-chain provenance, zk rollups, small cap, big upside.",
        priority=1,
    )
    renderer.add_story_sentence(
        "They wire 100k each. No victory lap; just quiet nods, and a text from Ella: \"Dinner tonight?\"",
        priority=1,
    )
    renderer.add_highlight(
        "Finance: Bought ORIGIN @ $0.05 - 2,000,000 units each.", priority=1
    )
    renderer.add_highlight(
        "Social: Ben D jokes, \"Don't forget capital gains, lads.\"", priority=3
    )
    renderer.add_highlight(
        "Romance: Ella appreciates the invite; trust +1.", priority=3
    )
    renderer.add_romance_line("Thomas & Ella: trust +1 (shared plans).", priority=2)
    renderer.add_social_line(
        "Lunch with Ben D; light ribbing about \"crypto bros.\"", pair="thomas|ben_d", delta=1
    )
