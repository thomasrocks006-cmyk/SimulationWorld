from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping


@dataclass
class Holdings:
    cash_usd: float = 0.0
    tokens: Dict[str, float] = field(default_factory=dict)
    equities_usd: float = 0.0

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "Holdings":
        cash = float(payload.get("cash_usd", 0.0))
        equities = float(payload.get("equities_usd", 0.0))
        tokens_raw = payload.get("tokens", {})
        if isinstance(tokens_raw, Mapping):
            tokens = {str(symbol): float(qty) for symbol, qty in tokens_raw.items()}
        else:
            tokens = {}
        return cls(cash_usd=cash, tokens=tokens, equities_usd=equities)


@dataclass
class Person:
    id: str
    name: str
    age: int
    occupation: str
    base_city: str
    traits: Dict[str, int]
    drives: List[str]
    holdings: Holdings

    def adjust_cash(self, delta: float) -> None:
        self.holdings.cash_usd = round(self.holdings.cash_usd + float(delta), 2)

    def add_tokens(self, symbol: str, quantity: float) -> None:
        current = self.holdings.tokens.get(symbol, 0.0)
        self.holdings.tokens[symbol] = current + quantity

    def token_quantity(self, symbol: str) -> float:
        return self.holdings.tokens.get(symbol, 0.0)
