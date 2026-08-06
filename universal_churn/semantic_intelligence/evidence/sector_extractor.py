from __future__ import annotations
from ..domain.enums import EvidenceFamily
from ..domain.models import EvidenceItem
from .base import EvidenceExtractor, ExtractorContext
class SectorExtractor(EvidenceExtractor):
    def extract(self, context: ExtractorContext):
        sectors = {str(identifier).rsplit(".", 1)[-1] for identifier, score in context.dataset.candidate_sectors if score >= .25}
        if not sectors: return ()
        targets = [c for c in context.ontology.meanings() if any(s in c.label.lower() for s in sectors)]
        return tuple(EvidenceItem(f"sector:{context.column.raw_column}:{c.ontology_id.value}", EvidenceFamily.SECTOR_CONTEXT, c.ontology_id, .1, 1, "Dataset sector hypothesis supports sector-specific meaning.", "dataset_profile") for c in targets)
