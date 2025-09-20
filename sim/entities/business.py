from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Business:
    id: str
    name: str
    sector: str
    valuation_aud: float
    owner_id: str
    stress_factor: float
