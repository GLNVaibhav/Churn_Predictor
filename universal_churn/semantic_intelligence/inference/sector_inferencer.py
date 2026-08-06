from __future__ import annotations
from ..domain.models import SectorHypothesis, SectorInferenceResult

class SectorInferencer:
    def infer(self, dataset_profile) -> SectorInferenceResult:
        hypotheses = tuple(SectorHypothesis(oid, score, "Dataset profile sector markers.") for oid, score in dataset_profile.candidate_sectors)
        selected = hypotheses[0].sector_id if hypotheses and hypotheses[0].probability >= .25 else None
        return SectorInferenceResult(hypotheses, selected, 1.0 - (hypotheses[0].probability if hypotheses else 0.0))
