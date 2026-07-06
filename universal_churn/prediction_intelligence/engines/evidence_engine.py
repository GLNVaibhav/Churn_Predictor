"""
universal_churn/prediction_intelligence/engines/evidence_engine.py
══════════════════════════════════════════════════════════════════════
Module 2 — Evidence Engine.

Answers: "how much trustworthy INPUT evidence does this prediction
rest on?" — Coverage (is the schema populated), Concept Confidence (can
the business ideas be reconstructed), and Quality (is any of it
tainted by leakage/nulls/no-variance). Distinct from Module 1
(Prediction Confidence, which only looks at the probability) and
Module 3 (Signal Intelligence, which looks at business reasoning) —
this engine never reads `context.churn_probability` at all.

Independence from decision_intelligence.py
------------------------------------------------
decision_intelligence.py already computes something shaped like this
("evidence_strength") for its own executive-report purpose. This is a
deliberately SEPARATE, independent calculation living in the
Prediction Intelligence package — PIE must not import
decision_intelligence.py (that module sits downstream/parallel, not
upstream, of PIE, and importing it would create a layering cycle risk
plus tie PIE's evolution to a different package's internals). Both
modules are allowed to read the same underlying CoverageResult /
QualityResult objects and reach a similar-shaped number; that overlap
is expected, not a bug — see prediction_confidence.py's docstring for
the same reasoning applied to its own near-neighbor
(reporting.Prediction_Confidence).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..interfaces import PredictionIntelligenceContext, PredictionIntelligenceEngine


@dataclass(frozen=True)
class EvidenceResult:
    coverage_component: float
    concept_component: float | None     # None if concept_confidence was unavailable
    quality_component: float | None      # None if quality was unavailable
    evidence_strength: float             # weighted combination, in [0, 1]
    evidence_band: str                   # 'Strong' | 'Moderate' | 'Weak' | 'Insufficient'
    missing_signals: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            'coverage_component': self.coverage_component,
            'concept_component': self.concept_component,
            'quality_component': self.quality_component,
            'evidence_strength': self.evidence_strength,
            'evidence_band': self.evidence_band,
            'missing_signals': list(self.missing_signals),
        }


def _band_for(strength: float) -> str:
    if strength >= 0.75:
        return "Strong"
    if strength >= 0.50:
        return "Moderate"
    if strength >= 0.25:
        return "Weak"
    return "Insufficient"


class EvidenceEngine(PredictionIntelligenceEngine[EvidenceResult]):
    """Module 2. No upstream dependencies — reads only the shared
    context, same fan-out tier as Module 1 and Module 3."""

    name = "evidence_engine"
    requires: tuple[str, ...] = ()

    #: Weights when every component is present. Re-normalized over
    #: whichever components are actually available for a given
    #: context, so a missing signal never silently zeroes out the
    #: score — it narrows the denominator instead (same "absence is
    #: not evidence of low quality" policy routing.py and
    #: decision_intelligence.py already use for missing concept
    #: confidence).
    WEIGHTS = {'coverage': 0.45, 'concept': 0.30, 'quality': 0.25}

    def analyze(
        self,
        context: PredictionIntelligenceContext,
        **prior_results,
    ) -> EvidenceResult:
        missing: list[str] = []

        coverage_component = context.coverage.coverage_score

        concept_component = None
        if context.concept_confidence is not None:
            concept_component = context.concept_confidence.overall_confidence
        else:
            missing.append("concept_confidence")

        quality_component = None
        if context.quality is not None:
            quality_component = 0.0 if context.quality.status == 'FAIL' else (
                0.5 if context.quality.status == 'WARN' else 1.0
            )
        else:
            missing.append("quality")

        weighted_sum = coverage_component * self.WEIGHTS['coverage']
        weight_total = self.WEIGHTS['coverage']
        if concept_component is not None:
            weighted_sum += concept_component * self.WEIGHTS['concept']
            weight_total += self.WEIGHTS['concept']
        if quality_component is not None:
            weighted_sum += quality_component * self.WEIGHTS['quality']
            weight_total += self.WEIGHTS['quality']

        evidence_strength = round(weighted_sum / weight_total, 4) if weight_total else 0.0

        # A hard quality FAIL caps evidence regardless of coverage —
        # leaked/tainted data cannot count as "strong evidence" just
        # because the schema was well-populated.
        if context.quality is not None and context.quality.status == 'FAIL':
            evidence_strength = min(evidence_strength, 0.20)

        return EvidenceResult(
            coverage_component=round(coverage_component, 4),
            concept_component=round(concept_component, 4) if concept_component is not None else None,
            quality_component=quality_component,
            evidence_strength=evidence_strength,
            evidence_band=_band_for(evidence_strength),
            missing_signals=tuple(missing),
        )
