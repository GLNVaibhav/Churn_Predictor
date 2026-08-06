from __future__ import annotations
from dataclasses import dataclass
from ..domain.models import SemanticResolution
@dataclass(frozen=True)
class ResolutionTrace: trace_id: str; raw_column: str; status: str; reasoning: str; evidence_count: int
class TraceBuilder:
    def build(self, resolution: SemanticResolution) -> ResolutionTrace:
        candidates = resolution.business_meaning.candidates
        evidence_count = sum(len(c.evidence.items) for c in candidates)
        return ResolutionTrace(resolution.trace_id, resolution.raw_column, resolution.status.value, resolution.abstention.rationale, evidence_count)
