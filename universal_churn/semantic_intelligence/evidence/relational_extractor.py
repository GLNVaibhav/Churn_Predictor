from __future__ import annotations
from ..domain.enums import EvidenceFamily
from ..domain.models import EvidenceItem
from .base import EvidenceExtractor, ExtractorContext
class RelationalExtractor(EvidenceExtractor):
    def extract(self, context: ExtractorContext):
        if context.dataset.candidate_grain != "entity_snapshot" or context.column.identifier_likelihood >= .5: return ()
        targets = [c for c in context.ontology.meanings() if any(word in c.label.lower() for word in ("tenure", "charge", "satisfaction", "recency"))]
        return tuple(EvidenceItem(f"relational:{context.column.raw_column}:{c.ontology_id.value}", EvidenceFamily.RELATIONAL, c.ontology_id, .1, 1, "Entity-snapshot dataset grain supports customer attribute interpretation.", "dataset_profile") for c in targets)
