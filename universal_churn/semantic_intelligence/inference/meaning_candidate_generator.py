from __future__ import annotations
from ..domain.enums import AbstentionStatus
from ..domain.models import BusinessMeaningCandidate, BusinessMeaningResolution, EvidenceBundle, SemanticInterpretation
from ..evidence.base import ExtractorContext, EvidenceExtractor
from .evidence_fusion_engine import EvidenceFusionEngine

class MeaningCandidateGenerator:
    def __init__(self, extractors: tuple[EvidenceExtractor, ...], fusion: EvidenceFusionEngine | None = None) -> None:
        self._extractors, self._fusion = extractors, fusion or EvidenceFusionEngine()
    def generate(self, context: ExtractorContext) -> BusinessMeaningResolution:
        all_items = tuple(item for extractor in self._extractors for item in extractor.extract(context))
        candidates = []
        for concept in context.ontology.meanings():
            bundle = EvidenceBundle(tuple(i for i in all_items if i.target == concept.ontology_id))
            if bundle.items:
                score = self._fusion.score(bundle)
                candidates.append(BusinessMeaningCandidate(SemanticInterpretation(concept.ontology_id), score, bundle, 1.0 - score))
        ranked = tuple(sorted(candidates, key=lambda c: (-c.raw_score, c.interpretation.meaning_id.value)))
        if not ranked: return BusinessMeaningResolution(None, (), AbstentionStatus.ABSTAINED, "No evidence supports a business meaning.")
        top = ranked[0]
        status = AbstentionStatus.ACCEPTED if top.raw_score >= .45 else AbstentionStatus.REVIEW_REQUIRED
        return BusinessMeaningResolution(top if status == AbstentionStatus.ACCEPTED else None, ranked, status, "Meaning selected from fused lexical, profile, and contextual evidence." if status == AbstentionStatus.ACCEPTED else "Evidence is insufficient for automatic meaning acceptance.")
