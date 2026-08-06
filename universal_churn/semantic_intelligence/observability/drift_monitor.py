from __future__ import annotations
from dataclasses import dataclass
from ..domain.models import ResolvedSchema
@dataclass(frozen=True)
class DriftResult: changed_columns: tuple[str, ...]; changed: bool
class SemanticDriftMonitor:
    def evaluate(self, baseline: ResolvedSchema, current: ResolvedSchema) -> DriftResult:
        before = {r.raw_column: r.assignment.canonical_id for r in baseline.resolutions}; after = {r.raw_column: r.assignment.canonical_id for r in current.resolutions}
        changed = tuple(sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k)))
        return DriftResult(changed, bool(changed))
