from __future__ import annotations
from ..domain.models import CanonicalCandidate
class CanonicalRanker:
    def rank(self, candidates: tuple[CanonicalCandidate, ...]) -> tuple[CanonicalCandidate, ...]: return tuple(sorted(candidates, key=lambda c: (-c.score, c.canonical_id.value)))
