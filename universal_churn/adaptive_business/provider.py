"""Provider abstraction for pluggable, sector-independent business context."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .models import BusinessEvidence, ExecutionContext


class BusinessContextProvider(ABC):
    """Read-only provider interface; implementations must never mutate UCIF state."""

    @abstractmethod
    def supports(self, sector: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def evaluate(self, execution_context: ExecutionContext) -> list[BusinessEvidence]:
        raise NotImplementedError
