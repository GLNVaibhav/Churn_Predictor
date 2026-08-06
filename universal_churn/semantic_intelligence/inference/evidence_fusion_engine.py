from __future__ import annotations
from ..domain.models import EvidenceBundle

class EvidenceFusionEngine:
    """Hybrid fusion: evidence weights are probabilistic; blockers remain validation policy."""
    _WEIGHTS = {"LEXICAL": .35, "ABBREVIATION": .25, "NAMING": .15, "UNIT": .20, "DATATYPE": .10, "STATISTICAL": .15, "CARDINALITY": .15, "TEMPORAL": .20, "IDENTIFIER": .35, "RELATIONAL": .20, "DATASET_CONTEXT": .10, "SECTOR_CONTEXT": .15, "BUSINESS_RULE": .25}
    def score(self, bundle: EvidenceBundle) -> float:
        if not bundle.items: return 0.0
        weighted = sum(item.polarity * item.score * self._WEIGHTS.get(item.family.value, .1) for item in bundle.items)
        capacity = sum(self._WEIGHTS.get(item.family.value, .1) for item in bundle.items)
        return max(0.0, min(1.0, weighted / capacity if capacity else 0.0))
