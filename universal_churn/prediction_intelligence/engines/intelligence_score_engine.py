"""
universal_churn/prediction_intelligence/engines/intelligence_score_engine.py
══════════════════════════════════════════════════════════════════════
Module 6 — Intelligence Score Engine.

The last engine in the pipeline. Combines every prior module
(Confidence, Evidence, Signal, Stability, Consistency) into ONE
headline Prediction Intelligence Score + band + a short, deterministic
headline sentence — the number and verdict that
PredictionIntelligenceReport (report.py) leads with.

This is intentionally the ONLY module that produces a single top-line
number — every module before it stays legible and inspectable on its
own axis. Mirrors decision_intelligence.py's own "one overall_confidence
at the end, everything else stays a named component" convention,
applied independently within this package (see evidence_engine.py's
docstring for why PIE does not import decision_intelligence.py despite
the conceptual similarity).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..interfaces import PredictionIntelligenceContext, PredictionIntelligenceEngine
from .prediction_confidence import PredictionConfidenceResult
from .evidence_engine import EvidenceResult
from .signal_intelligence import SignalIntelligenceResult
from .stability_engine import StabilityResult
from .consistency_engine import ConsistencyResult


@dataclass(frozen=True)
class IntelligenceScoreResult:
    intelligence_score: float           # in [0, 1]
    intelligence_band: str               # 'Excellent' | 'Good' | 'Fair' | 'Poor' | 'Untrustworthy'
    headline: str
    component_scores: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            'intelligence_score': self.intelligence_score,
            'intelligence_band': self.intelligence_band,
            'headline': self.headline,
            'component_scores': dict(self.component_scores),
        }


def _band_for(score: float) -> str:
    if score >= 0.85:
        return "Excellent"
    if score >= 0.65:
        return "Good"
    if score >= 0.45:
        return "Fair"
    if score >= 0.25:
        return "Poor"
    return "Untrustworthy"


class IntelligenceScoreEngine(PredictionIntelligenceEngine[IntelligenceScoreResult]):
    """Module 6. Requires every prior module — the final convergence
    point feeding PredictionIntelligenceReport."""

    name = "intelligence_score_engine"
    requires: tuple[str, ...] = (
        "prediction_confidence", "evidence", "signal", "stability", "consistency",
    )

    #: Consistency and Stability matter most (they already summarize
    #: agreement across everything else); raw Confidence matters least
    #: on its own, since Stability already penalizes it when
    #: unsupported.
    WEIGHTS = {
        'confidence': 0.15,
        'evidence': 0.20,
        'signal': 0.10,
        'stability': 0.25,
        'consistency': 0.30,
    }

    def analyze(
        self,
        context: PredictionIntelligenceContext,
        **prior_results,
    ) -> IntelligenceScoreResult:
        confidence: PredictionConfidenceResult = prior_results["prediction_confidence"]
        evidence: EvidenceResult = prior_results["evidence"]
        signal: SignalIntelligenceResult = prior_results["signal"]
        stability: StabilityResult = prior_results["stability"]
        consistency: ConsistencyResult = prior_results["consistency"]

        # Signal contributes 0.5 (neutral) rather than 0 when degraded
        # — absence of business reasoning is not evidence of a bad
        # prediction, matching the "missing optional input is not a
        # failure" rule from the integration contract.
        signal_component = signal.signal_strength if not signal.degraded else 0.5

        components = {
            'confidence': confidence.decisiveness,
            'evidence': evidence.evidence_strength,
            'signal': signal_component,
            'stability': stability.stability_score,
            'consistency': consistency.consistency_score,
        }

        weighted_sum = sum(components[k] * self.WEIGHTS[k] for k in self.WEIGHTS)
        intelligence_score = round(weighted_sum, 4)
        band = _band_for(intelligence_score)

        headline = self._build_headline(
            band, confidence, evidence, signal, stability, consistency,
        )

        return IntelligenceScoreResult(
            intelligence_score=intelligence_score,
            intelligence_band=band,
            headline=headline,
            component_scores={k: round(v, 4) for k, v in components.items()},
        )

    @staticmethod
    def _build_headline(
        band: str,
        confidence: PredictionConfidenceResult,
        evidence: EvidenceResult,
        signal: SignalIntelligenceResult,
        stability: StabilityResult,
        consistency: ConsistencyResult,
    ) -> str:
        if band in ("Excellent", "Good"):
            return (
                f"This prediction is well-supported: {confidence.confidence_band.lower()} "
                f"model confidence, {evidence.evidence_band.lower()} evidence, and a "
                f"{consistency.consistency_band.lower()} overall picture."
            )
        if band == "Fair":
            return (
                f"This prediction is usable but not airtight: "
                f"{stability.stability_band.lower()} stability and a "
                f"{consistency.consistency_band.lower()} picture across signals."
            )
        if stability.overconfidence_flag:
            return (
                "This prediction looks more certain than its evidence "
                "actually supports — treat the probability with caution."
            )
        if consistency.conflicts:
            return "This prediction's underlying signals disagree with each other — review before acting."
        return "This prediction rests on weak or incomplete evidence."
