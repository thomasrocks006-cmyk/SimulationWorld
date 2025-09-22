from __future__ import annotations

import random
from typing import Iterable, Sequence, TypeVar

T = TypeVar("T")


class RNG:
    """Thin wrapper around random.Random for deterministic runs."""

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self._random = random.Random(seed)

    def random(self) -> float:
        return self._random.random()

    def choice(self, items: Sequence[T]) -> T:
        return self._random.choice(list(items))

    def shuffle(self, items: list[T]) -> None:
        self._random.shuffle(items)

    def sample(self, population: Iterable[T], k: int) -> list[T]:
        population_list = list(population)
        return self._random.sample(population_list, k)
