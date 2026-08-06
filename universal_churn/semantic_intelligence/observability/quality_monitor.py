from __future__ import annotations
from .metrics import resolution_metrics
class SemanticQualityMonitor:
    def evaluate(self, schema): return resolution_metrics(schema)
