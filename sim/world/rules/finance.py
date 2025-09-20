from __future__ import annotations

from datetime import date

from sim.world.state import WorldState
from sim.output.render import DailyRenderer


def apply_finance_rules(
    day: date,
    *,
    state: WorldState,
    renderer: DailyRenderer,
) -> None:
    price = state.price_for(day)
    symbol = state.coin_symbol
    for person in state.people.values():
        qty = person.token_quantity(symbol)
        if qty <= 0:
            continue
        value = qty * price
        renderer.log(
            f"{person.name}'s {symbol} position marks to ${value:,.2f} at ${price:,.2f}."
        )
