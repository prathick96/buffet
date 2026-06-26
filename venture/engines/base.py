"""venture/engines/base.py — common engine base."""
from __future__ import annotations

from abc import ABC, abstractmethod


class Engine(ABC):
    """A single-responsibility engine. Keep `run` as close to a pure function of
    its typed inputs as the job allows — it makes each engine independently
    testable and safe to drive from a LangGraph node later."""

    name: str = "engine"

    @abstractmethod
    def run(self, *args, **kwargs):
        ...

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r}>"
