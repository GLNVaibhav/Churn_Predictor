from __future__ import annotations

from ..models import BusinessEvidence, ExecutionContext
from ..provider import BusinessContextProvider


class GenericProvider(BusinessContextProvider):
    """Fallback adapter that turns validated user-supplied events into typed evidence."""
    provider_name = "generic_context"

    def supports(self, sector: str) -> bool:
        return True

    def evaluate(self, execution_context: ExecutionContext) -> list[BusinessEvidence]:
        return [
            BusinessEvidence(
                evidence_id=f"ABIL-{execution_context.execution_id}-{index + 1}",
                category=str(event["category"]), description=str(event["description"]),
                source=str(event.get("source", self.provider_name)), severity=str(event["severity"]),
                confidence=float(event["confidence"]),
                affected_segments=tuple(map(str, event.get("affected_segments", []))),
                recommendation=str(event.get("recommendation", "Review this business signal alongside the customer prediction.")),
                timestamp=str(event.get("timestamp", "")),
            )
            for index, event in enumerate(execution_context.events)
        ]
