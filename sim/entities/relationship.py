from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class Relationship:
    src_id: str
    dst_id: str
    weight: int
    tags: List[str] = field(default_factory=list)
