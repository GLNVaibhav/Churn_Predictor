from __future__ import annotations
import json
from dataclasses import asdict
from ..domain.models import ResolvedSchema
class AuditExportService:
    def export(self, resolved_schema: ResolvedSchema, format: str = "json") -> str:
        if format != "json": raise ValueError("Only JSON audit export is supported.")
        return json.dumps(asdict(resolved_schema), default=lambda value: getattr(value, "value", str(value)), sort_keys=True)
