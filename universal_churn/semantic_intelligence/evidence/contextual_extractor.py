from __future__ import annotations
from ..domain.enums import EvidenceFamily
from ..domain.models import EvidenceItem
from .base import EvidenceExtractor, ExtractorContext
class ContextualExtractor(EvidenceExtractor):
    def extract(self, context: ExtractorContext):
        if context.dataset.column_count < 2: return ()
        targets = [c for c in context.ontology.meanings() if "customer" in c.label.lower()]
        return tuple(EvidenceItem(f"context:{context.column.raw_column}:{c.ontology_id.value}", EvidenceFamily.DATASET_CONTEXT, c.ontology_id, .05, 1, "Multi-column dataset context weakly supports customer-domain meaning.", "dataset_profile") for c in targets)
