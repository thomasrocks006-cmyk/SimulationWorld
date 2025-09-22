from __future__ import annotations

from datetime import date

from datetime import timedelta

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
    prev_day = day - timedelta(days=1)
    try:
        prev_price = state.price_for(prev_day)
    except KeyError:
        prev_price = price
    change_pct = 0.0 if prev_price == 0 else ((price - prev_price) / prev_price) * 100
    renderer.add_highlight(
        f"Finance: {symbol} {change_pct:+.1f}% -> ${price:.2f} (mark-to-market completed).",
        priority=2,
    )

    for person in state.people.values():
        qty = person.token_quantity(symbol)
        if qty <= 0:
            continue
        value = qty * price
        renderer.add_finance_line(
            text=(
                f"{symbol} price: ${price:.2f} | {person.name}: {qty:,.0f} -> ${value:,.2f} | "
                f"Cash: ${person.holdings.cash_usd:,.2f}"
            ),
            holder=person.name,
            value=value,
            price=price,
            token_quantity=qty,
            cash=person.holdings.cash_usd,
            priority=2,
        )
