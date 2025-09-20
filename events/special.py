from __future__ import annotations

from datetime import date
from typing import Callable, List

from sim import config
from sim.world.state import WorldState


def scripted_events(
    day: date,
    *,
    state: WorldState,
    rng,
) -> List[Callable[[], str | None]]:
    events: List[Callable[[], str | None]] = []

    if day == config.INVESTMENT_DATE:
        events.append(lambda: _origin_buy_in(day, state=state))

    # TODO: Add hand-authored beats (ATO verdict day, group dinners, ex run-ins).
    _ = rng
    return events


def _origin_buy_in(day: date, *, state: WorldState) -> str:
    price = state.price_for(day)
    symbol = config.COIN_SYMBOL
    quantity = config.INVESTMENT_AMOUNT_USD / price
    for person_id in ("thomas", "jordy"):
        person = state.people.get(person_id)
        if not person:
            continue
        person.adjust_cash(-config.INVESTMENT_AMOUNT_USD)
        person.add_tokens(symbol, quantity)
    return (
        f"On {day.isoformat()}, both Thomas & Jordan buy {symbol} at ${price:.2f} "
        "and holdings are marked to market."
    )
