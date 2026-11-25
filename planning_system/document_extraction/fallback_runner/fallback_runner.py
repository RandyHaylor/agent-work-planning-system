"""Generic fallback runner: tries interchangeable strategies in order, reports which one was used.

Knows nothing about documents. A strategy is any callable taking the item; its name is its `name`
attribute if present, else its `__name__`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Generic, Sequence, TypeVar

I = TypeVar("I")
O = TypeVar("O")

Strategy = Callable[[I], O]


@dataclass(frozen=True)
class Attempt:
    strategy: str
    error: str | None  # None = this one succeeded


@dataclass(frozen=True)
class FallbackOutcome(Generic[O]):
    output: O
    used_name: str
    attempts: tuple[Attempt, ...]


class AllStrategiesFailed(Exception):
    def __init__(self, attempts: tuple[Attempt, ...]) -> None:
        self.attempts = tuple(attempts)
        super().__init__("; ".join(f"{a.strategy}: {a.error}" for a in self.attempts) or "no strategies")


def strategy_name(strategy: Callable) -> str:
    return getattr(strategy, "name", None) or getattr(strategy, "__name__", type(strategy).__name__)


class FallbackRunnerInterface(ABC, Generic[I, O]):
    @abstractmethod
    def run(self, item: I, strategies: Sequence[Strategy]) -> FallbackOutcome[O]:
        """Try in order; a failure of the configured type is recorded and the next runs.
        Returns the first success; raises AllStrategiesFailed(attempts)."""


class FallbackRunner(FallbackRunnerInterface[I, O]):
    def __init__(self, failure_type: type[BaseException] | tuple[type[BaseException], ...] = Exception) -> None:
        self.failure_type = failure_type

    def run(self, item: I, strategies: Sequence[Strategy]) -> FallbackOutcome[O]:
        raise NotImplementedError("level 7")
