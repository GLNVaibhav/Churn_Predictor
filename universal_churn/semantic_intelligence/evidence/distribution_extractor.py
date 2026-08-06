from __future__ import annotations
from ..domain.enums import EvidenceFamily
from ..domain.models import EvidenceItem
from .base import EvidenceExtractor, ExtractorContext
class DistributionExtractor(EvidenceExtractor):
    def extract(self, context: ExtractorContext) -> tuple[EvidenceItem, ...]:
        p = context.column.distribution
        if p.minimum is None: return ()
        out = []
        for c in context.ontology.meanings():
            if "count" in c.label.lower() and p.minimum >= 0 and (p.integer_ratio or 0) >= .8: out.append(EvidenceItem(f"distribution:{context.column.raw_column}:{c.ontology_id.value}", EvidenceFamily.STATISTICAL, c.ontology_id, .35, 1, "Non-negative integer-like distribution supports count semantics.", "profile"))
        return tuple(out)
