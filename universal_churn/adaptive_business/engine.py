"""Read-only ABIL orchestration; it never changes predictions or routing."""
from __future__ import annotations

from .models import BusinessEvidenceBundle, BusinessImpactAssessment, ExecutionContext
from .provider import BusinessContextProvider
from .providers import BankingProvider, GenericProvider, RetailProvider, TelecomProvider


_IMPACT_RANK = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


class AdaptiveBusinessEngine:
    def __init__(self, providers: tuple[BusinessContextProvider, ...] | None = None) -> None:
        self.providers = providers or (TelecomProvider(), BankingProvider(), RetailProvider(), GenericProvider())

    def evaluate(self, context: ExecutionContext) -> BusinessEvidenceBundle:
        provider = next(item for item in self.providers if item.supports(context.sector))
        evidences = tuple(provider.evaluate(context))
        if not evidences:
            return BusinessEvidenceBundle()
        impact = max((item.severity for item in evidences), key=lambda value: _IMPACT_RANK[value])
        confidence = sum(item.confidence for item in evidences) / len(evidences)
        dominant = max(evidences, key=lambda item: (_IMPACT_RANK[item.severity], item.confidence))
        segments = tuple(sorted({segment for item in evidences for segment in item.affected_segments}))
        assessment = BusinessImpactAssessment(
            signals_evaluated=len(evidences), dominant_driver=dominant.category,
            affected_segments=segments, operational_impact=impact, priority=impact,
            recommended_action=dominant.recommendation,
            supporting_evidence=tuple(item.evidence_id for item in evidences),
        )
        summary = f"{len(evidences)} external business signal(s) evaluated; dominant driver: {dominant.category}; highest operational impact: {impact}."
        return BusinessEvidenceBundle(evidences, impact, confidence, summary, assessment)
