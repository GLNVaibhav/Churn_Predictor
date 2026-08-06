from __future__ import annotations
from ..domain.enums import EvidenceFamily
from ..domain.models import EvidenceItem
from .base import EvidenceExtractor, ExtractorContext

class TemporalExtractor(EvidenceExtractor):
    def extract(self, context: ExtractorContext) -> tuple[EvidenceItem, ...]:
        if not context.column.temporal_indicators: return ()
        targets = [c for c in context.ontology.meanings() if any(w in c.label.lower() for w in ("tenure", "recency"))]
        return tuple(EvidenceItem(f"temporal:{context.column.raw_column}:{c.ontology_id.value}", EvidenceFamily.TEMPORAL, c.ontology_id, .45, 1, "Temporal naming indicators support temporal business meaning.", "column_name") for c in targets)
