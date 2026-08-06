from __future__ import annotations
from ..domain.models import ResolvedSchema
def resolution_metrics(schema: ResolvedSchema) -> dict[str, float]:
    total = len(schema.resolutions) or 1
    accepted = sum(r.status.value.endswith("ACCEPTED") or r.status.value.startswith("DETERMINISTIC") for r in schema.resolutions)
    return {"accepted_coverage": accepted / total, "columns": float(len(schema.resolutions))}
