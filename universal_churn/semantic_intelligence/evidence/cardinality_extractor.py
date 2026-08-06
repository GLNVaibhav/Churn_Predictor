from __future__ import annotations
from ..domain.enums import EvidenceFamily
from ..domain.models import EvidenceItem
from .base import EvidenceExtractor, ExtractorContext
class CardinalityExtractor(EvidenceExtractor):
    def extract(self, context: ExtractorContext) -> tuple[EvidenceItem, ...]:
        if context.column.cardinality.uniqueness_ratio < .85: return ()
        target = next((c for c in context.ontology.meanings() if c.ontology_id.value.endswith("customer.identifier")), None)
        return (EvidenceItem(f"cardinality:{context.column.raw_column}", EvidenceFamily.CARDINALITY, target.ontology_id, .5, 1, "High cardinality supports identifier semantics.", "profile"),) if target else ()
