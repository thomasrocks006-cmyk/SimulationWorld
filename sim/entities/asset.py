from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RealEstate:
    owner_id: str
    address: str
    value_aud: float
    mortgage_aud: float


@dataclass
class Vehicle:
    owner_id: str
    make_model: str
    value_aud: float
