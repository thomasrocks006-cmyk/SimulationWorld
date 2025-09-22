from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List
from sim.world.state import WorldState


@dataclass
class Choice:
    id: str
    label: str
    applies: Callable[[WorldState, str], bool]
    effect: Callable[[WorldState, str], List[str]]
    priority: int = 0


def _tell_ella_applies(state: WorldState, _: str) -> bool:
    return "thomas" in state.people and state.metrics.get("told_ella_origin", 0) == 0


def _tell_ella_effect(state: WorldState, date_str: str) -> List[str]:
    state.adjust_metric("thomas_romance_trust", 2.0)
    state.adjust_metric("told_ella_origin", 1.0)
    return [
        "Thomas loops Ella in on the ORIGIN position; trust climbs, though volatility nerves linger.",
        "Ella notes the date " + date_str + " in her planner - just in case.",
    ]


def _keep_quiet_applies(state: WorldState, _: str) -> bool:
    return "thomas" in state.people


def _keep_quiet_effect(state: WorldState, _: str) -> List[str]:
    state.adjust_metric("thomas_romance_trust", -0.5)
    return [
        "Thomas keeps the ORIGIN buy between himself and Jordy; the secret buys breathing room but risks distance.",
    ]


def _trim_origin_applies(state: WorldState, date_str: str) -> bool:
    if "thomas" not in state.people:
        return False
    thomas = state.people["thomas"]
    return thomas.token_quantity(state.coin_symbol) > 0 and state.price_for_str(date_str) > 0


def _trim_origin_effect(state: WorldState, date_str: str) -> List[str]:
    thomas = state.people["thomas"]
    price = state.price_for_str(date_str)
    quantity = thomas.token_quantity(state.coin_symbol)
    sell_units = quantity * 0.03
    thomas.holdings.tokens[state.coin_symbol] = max(quantity - sell_units, 0.0)
    proceeds = sell_units * price
    thomas.adjust_cash(proceeds)
    state.adjust_metric("thomas_cash_realised", proceeds)
    return [
        f"Thomas trims 3% of ORIGIN, selling {sell_units:,.0f} units at ${price:.2f} for ${proceeds:,.0f} cash.",
        "The move chips away at upside but steadies nerves ahead of the next swing.",
    ]


def _jordy_take_profit_applies(state: WorldState, date_str: str) -> bool:
    if "jordy" not in state.people:
        return False
    return state.people["jordy"].token_quantity(state.coin_symbol) > 0 and state.price_for_str(date_str) > 0


def _jordy_take_profit_effect(state: WorldState, date_str: str) -> List[str]:
    jordy = state.people["jordy"]
    price = state.price_for_str(date_str)
    quantity = jordy.token_quantity(state.coin_symbol)
    sell_units = quantity * 0.02
    jordy.holdings.tokens[state.coin_symbol] = max(quantity - sell_units, 0.0)
    proceeds = sell_units * price
    jordy.adjust_cash(proceeds)
    state.adjust_metric("jordy_cash_realised", proceeds)
    return [
        f"Jordy quietly slices 2% of ORIGIN ({sell_units:,.0f} units) at ${price:.2f}, banking ${proceeds:,.0f} for ops.",
    ]


def _prep_ato_applies(state: WorldState, _: str) -> bool:
    return "jordy" in state.people


def _prep_ato_effect(state: WorldState, _: str) -> List[str]:
    state.adjust_metric("jordy_stress", -1.5)
    return [
        "Jordy spends the evening prepping briefs with counsel for the looming ATO review; stress eases slightly.",
    ]


CHOICES: List[Choice] = [
    Choice(
        id="tell_ella",
        label="Thomas: Tell Ella about the ORIGIN investment (trust +2; volatility nerves +1).",
        applies=_tell_ella_applies,
        effect=_tell_ella_effect,
        priority=100,
    ),
    Choice(
        id="keep_quiet",
        label="Thomas: Keep the investment quiet for now (trust -0.5, lower anxiety).",
        applies=_keep_quiet_applies,
        effect=_keep_quiet_effect,
        priority=80,
    ),
    Choice(
        id="trim_origin",
        label="Thomas: Trim 3% of ORIGIN to bank some USD liquidity.",
        applies=_trim_origin_applies,
        effect=_trim_origin_effect,
        priority=70,
    ),
    Choice(
        id="jordy_take_profit",
        label="Jordy: Sell 2% ORIGIN to pad business reserves.",
        applies=_jordy_take_profit_applies,
        effect=_jordy_take_profit_effect,
        priority=60,
    ),
    Choice(
        id="prep_ato",
        label="Jordy: Block two hours for ATO prep (stress -1.5).",
        applies=_prep_ato_applies,
        effect=_prep_ato_effect,
        priority=50,
    ),
]


def pick_choices(state: WorldState, date_str: str, k: int = 3) -> List[Choice]:
    applicable = [choice for choice in CHOICES if choice.applies(state, date_str)]
    applicable.sort(key=lambda choice: choice.priority, reverse=True)
    return applicable[:k]
