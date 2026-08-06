from __future__ import annotations
from ..domain.enums import EvidenceFamily
from ..domain.models import EvidenceItem
from .base import EvidenceExtractor, ExtractorContext
class NamingConventionExtractor(EvidenceExtractor):
    def extract(self, context: ExtractorContext) -> tuple[EvidenceItem, ...]:
        name = context.column.raw_column.lower(); out = []
        if name.endswith(("_id", "id")):
            target = next((c for c in context.ontology.meanings() if c.ontology_id.value.endswith("customer.identifier")), None)
            if target: out.append(EvidenceItem(f"naming:{name}:identifier", EvidenceFamily.NAMING, target.ontology_id, .4, 1, "Identifier suffix follows source naming convention.", "column_name"))
        return tuple(out)
