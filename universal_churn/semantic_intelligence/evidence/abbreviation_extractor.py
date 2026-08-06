from __future__ import annotations
from ..domain.enums import EvidenceFamily
from ..domain.models import EvidenceItem
from .base import EvidenceExtractor, ExtractorContext
class AbbreviationExtractor(EvidenceExtractor):
    _MAP = {"amt": "amount", "cnt": "count", "qty": "quantity", "num": "number", "freq": "frequency", "mo": "month", "yr": "year"}
    def extract(self, context: ExtractorContext) -> tuple[EvidenceItem, ...]:
        tokens = context.column.raw_column.lower().replace("_", " ").split(); expanded = {self._MAP.get(t, t) for t in tokens}
        items = []
        for c in context.ontology.meanings():
            if expanded & set(" ".join(c.aliases).lower().split()): items.append(EvidenceItem(f"abbreviation:{context.column.raw_column}:{c.ontology_id.value}", EvidenceFamily.ABBREVIATION, c.ontology_id, .25, 1, "Expanded abbreviation overlaps ontology vocabulary.", "abbreviation_map"))
        return tuple(items)
