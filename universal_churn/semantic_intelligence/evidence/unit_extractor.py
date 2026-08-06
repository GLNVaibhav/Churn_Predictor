from __future__ import annotations
from ..domain.enums import EvidenceFamily
from ..domain.models import EvidenceItem
from .base import EvidenceExtractor, ExtractorContext
class UnitExtractor(EvidenceExtractor):
    def extract(self, context: ExtractorContext) -> tuple[EvidenceItem, ...]:
        units = set(context.column.units); out = []
        for c in context.ontology.meanings():
            label = c.label.lower()
            compatible = (bool(units & {"usd", "inr", "eur", "gbp", "rs"}) and any(x in label for x in ("charge", "spend"))) or (bool(units & {"day", "days", "month", "months", "year", "years"}) and any(x in label for x in ("tenure", "recency")))
            if compatible: out.append(EvidenceItem(f"unit:{context.column.raw_column}:{c.ontology_id.value}", EvidenceFamily.UNIT, c.ontology_id, .5, 1, "Detected source unit is compatible with meaning.", "column_name"))
        return tuple(out)
