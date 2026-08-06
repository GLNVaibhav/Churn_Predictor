from __future__ import annotations
from ..domain.models import AssignmentDecision, CanonicalCandidate
class AssignmentResolver:
    def resolve(self, candidates: tuple[CanonicalCandidate, ...], occupied: set[str] | None = None) -> AssignmentDecision:
        occupied = occupied or set()
        eligible = [c for c in candidates if c.eligible and c.canonical_id.value not in occupied]
        return AssignmentDecision(eligible[0].canonical_id, "Highest-ranked eligible canonical candidate.") if eligible else AssignmentDecision(None, "No eligible canonical candidate.")
