from __future__ import annotations
from ..domain.enums import EvidenceFamily
from ..domain.models import EvidenceItem
from .base import EvidenceExtractor, ExtractorContext

class IdentifierExtractor(EvidenceExtractor):
    def extract(self, context: ExtractorContext) -> tuple[EvidenceItem, ...]:
        target = next((c for c in context.ontology.meanings() if c.ontology_id.value.endswith("customer.identifier")), None)
        if target is None or context.column.identifier_likelihood < .5: return ()
        return (EvidenceItem(f"identifier:{context.column.raw_column}", EvidenceFamily.IDENTIFIER, target.ontology_id, context.column.identifier_likelihood, 1, "Uniqueness and identifier naming support identifier meaning.", "profile"),)
