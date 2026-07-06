"""
universal_churn/prediction_intelligence/engines/prediction_assurance.py
══════════════════════════════════════════════════════════════════════
Prediction Assurance Engine.

Purpose
-------
Answers exactly one question: "How strongly does the framework stand
behind this prediction?" — nothing else. Not evidence ranking (future
Evidence Engine), not robustness-to-missing-signals (future Robustness
Engine), not a cross-signal agreement check (future Prediction
Intelligence Score Engine). Just: given everything the framework
already knows about this prediction's inputs and routing, how much
weight should a downstream reader (Prediction Explanation, Decision
Intelligence, a human) put behind it.

Why "Assurance" and not "Confidence"
--------------------------------------
The framework already has three differently-scoped numbers that could
plausibly be called "confidence":
    - Concept Confidence     (concept_confidence.py)
    - Coverage Confidence     (utils.coverage_confidence_label)
    - Prediction Probability  (the model's own churn probability)
Adding a fourth, PIE-native "Prediction Confidence" (Module 1,
engines/prediction_confidence.py) already sits alongside these; this
engine is the deliberately differently-named evolution of that same
underlying idea, reframed as "assurance" specifically to stop that
ambiguity from compounding further. `PredictionConfidenceEngine` is
kept, unmodified, for backward compatibility (see orchestrator.py) —
this is an ADDITIONAL engine, not a silent replacement.

Inputs (per the architecture contract)
---------------------------------------
    Required:  Coverage, Concept Confidence, Quality, Routing
               (context.coverage / .concept_confidence / .quality /
               .routing_decision — "required" per contract, but may be
               `None` at runtime on some real call paths; see
               PredictionIntelligenceContext's docstring. This engine
               degrades gracefully rather than raising in that case.)
    Optional:  ReasoningReport, PredictionExplanation
               (context.reasoning_report / .prediction_explanation —
               not read by THIS engine's scoring at all; Assurance is
               scoped to the five weighted signals below only. Their
               absence is still recorded via context.degraded_inputs
               and surfaces as a warning line, per the "record this in
               the report" rule — see _degradation_warning() below.)
    Also read: Prediction Probability (context.churn_probability) —
               feeds the "prediction_reliability" component.

Output
------
    PredictionAssuranceResult — assurance_score, assurance_band,
    positive_factors, penalties, summary, warnings, metadata.

Dependencies
------------
..models (dataclasses), ..constants (thresholds/labels/messages),
..weights (ASSURANCE_WEIGHTS). No ML, no sector pipelines, no raw
data — same dependency discipline as PredictionConfidenceEngine.

Degradation policy
-------------------
Identical neutral-default policy to PredictionConfidenceEngine: a
missing signal scores 50.0 (neutral), is never silently penalized, and
is called out explicitly — here, via a dedicated warning line (see
constants.ASSURANCE_WARNING_DEGRADED_EVIDENCE_TEMPLATE) rather than
folding it into `reasons`, since PredictionAssuranceResult has no
single flat `reasons` list — narrative detail is split across
`positive_factors` / `penalties` / `warnings` by design.
"""
from __future__ import annotations

from ..constants import (
    band_for_score,
    ASSURANCE_STRONG_SIGNAL_MIN,
    ASSURANCE_WEAK_SIGNAL_MAX,
    ASSURANCE_COMPONENT_LABELS,
    ASSURANCE_POSITIVE_FACTOR_TEMPLATE,
    ASSURANCE_PENALTY_TEMPLATE,
    ASSURANCE_WARNING_QUALITY_FAIL,
    ASSURANCE_WARNING_ROUTING_REJECTED,
    ASSURANCE_WARNING_DEGRADED_EVIDENCE_TEMPLATE,
    ASSURANCE_SUMMARY_TEMPLATES,
)
from ..interfaces import PredictionIntelligenceEngine
from ..models import PredictionIntelligenceContext, PredictionAssuranceResult
from ..weights import ASSURANCE_WEIGHTS

# Reuse the exact same component-scoring functions Module 1 already
# implements for coverage / concept confidence / routing reliability /
# quality — these are pure reads of the same context fields, and
# duplicating them here would violate "do not duplicate framework
# contracts" just as much as re-deriving coverage.py's own logic
# would. Only the probability-based component gets its own function
# below, so its reason text can use "reliability" vocabulary instead
# of "certainty" — same math, Assurance-appropriate naming.
from .prediction_confidence import (
    _coverage_component,
    _concept_confidence_component,
    _routing_component,
    _quality_component,
)


def _prediction_reliability_component(context: PredictionIntelligenceContext) -> tuple[float, str]:
    """
    How reliable is THIS prediction's own probability, judged purely by
    its distance from the 0.5 decision boundary — 0.5 (a coin flip)
    scores 0; 0.0 or 1.0 (full commitment either way) scores 100. Same
    formula as PredictionConfidenceEngine's "probability_certainty"
    component, deliberately renamed to "prediction_reliability" here so
    Assurance's vocabulary never re-uses the word "confidence".
    """
    probability = context.churn_probability
    if probability is None:
        return 50.0, "Prediction probability unavailable — neutral score used."
    reliability = abs(float(probability) - 0.5) * 2.0 * 100.0
    reliability = max(0.0, min(100.0, reliability))
    return reliability, f"Prediction reliability was {reliability:.1f}% (probability={probability:.4f})."


_ASSURANCE_COMPONENT_FUNCTIONS = {
    "coverage": _coverage_component,
    "concept_confidence": _concept_confidence_component,
    "quality": _quality_component,
    "routing_reliability": _routing_component,
    "prediction_reliability": _prediction_reliability_component,
}


def _is_routing_rejected(context: PredictionIntelligenceContext) -> bool:
    decision = context.routing_decision
    if decision is None:
        return False
    selected_model = getattr(getattr(decision, "selected_model", None), "value", None)
    return selected_model == "CRITICAL_UNRELIABLE"


def _is_quality_failed(context: PredictionIntelligenceContext) -> bool:
    quality = context.quality
    if quality is None:
        return False
    return getattr(quality, "status", None) == "FAIL"


class PredictionAssuranceEngine(PredictionIntelligenceEngine):
    """
    Stateless, deterministic. Combines Coverage, Concept Confidence,
    Quality, Routing Reliability, and Prediction Reliability into one
    weighted 0-100 Prediction Assurance score, plus a narrative
    breakdown of what specifically supported or weakened that score.

    Missing/unavailable required inputs are treated NEUTRALLY (50.0 on
    that component's native 0-100 scale) and never penalized — see
    module docstring's "Degradation policy".
    """
    name = "prediction_assurance"

    def analyze(
        self,
        context: PredictionIntelligenceContext,
        **prior_results,
    ) -> PredictionAssuranceResult:
        raw_components: dict[str, float] = {}
        weighted_contributions: dict[str, float] = {}
        component_reasons: dict[str, str] = {}

        for component_name, weight in ASSURANCE_WEIGHTS.items():
            fn = _ASSURANCE_COMPONENT_FUNCTIONS[component_name]
            raw_score, reason = fn(context)
            raw_components[component_name] = raw_score
            weighted_contributions[component_name] = raw_score * weight
            component_reasons[component_name] = reason

        assurance_score = sum(weighted_contributions.values())
        assurance_band = band_for_score(assurance_score)

        positive_factors, penalties = self._classify_components(raw_components)
        warnings = self._collect_warnings(context)
        summary = self._build_summary(assurance_score, assurance_band, positive_factors, penalties)

        metadata = {
            "weights": dict(ASSURANCE_WEIGHTS),
            "raw_components": raw_components,
            "weighted_contributions": weighted_contributions,
            "component_reasons": component_reasons,
            "sector": context.sector,
            "degraded_inputs": list(context.degraded_inputs),
        }

        return PredictionAssuranceResult(
            assurance_score=assurance_score,
            assurance_band=assurance_band,
            positive_factors=tuple(positive_factors),
            penalties=tuple(penalties),
            summary=summary,
            warnings=tuple(warnings),
            metadata=metadata,
        )

    # ── helpers ──────────────────────────────────────────────────

    @staticmethod
    def _classify_components(
        raw_components: dict[str, float],
    ) -> tuple[list[str], list[str]]:
        """
        Sort components by raw score (strongest first) before
        classifying, so `positive_factors[0]` / `penalties[0]` are
        always the single strongest supporting / weakening signal —
        this ordering is what `_build_summary()` relies on to pick the
        "headline" factor and penalty.
        """
        positive_factors: list[str] = []
        penalties: list[str] = []
        for name, score in sorted(raw_components.items(), key=lambda kv: -kv[1]):
            label = ASSURANCE_COMPONENT_LABELS.get(name, name)
            if score >= ASSURANCE_STRONG_SIGNAL_MIN:
                positive_factors.append(
                    ASSURANCE_POSITIVE_FACTOR_TEMPLATE.format(label=label, score=score)
                )
        for name, score in sorted(raw_components.items(), key=lambda kv: kv[1]):
            label = ASSURANCE_COMPONENT_LABELS.get(name, name)
            if score <= ASSURANCE_WEAK_SIGNAL_MAX:
                penalties.append(
                    ASSURANCE_PENALTY_TEMPLATE.format(label=label, score=score)
                )
        return positive_factors, penalties

    @staticmethod
    def _collect_warnings(context: PredictionIntelligenceContext) -> list[str]:
        warnings: list[str] = []
        if _is_quality_failed(context):
            warnings.append(ASSURANCE_WARNING_QUALITY_FAIL)
        if _is_routing_rejected(context):
            warnings.append(ASSURANCE_WARNING_ROUTING_REJECTED)
        if context.degraded_inputs:
            warnings.append(
                ASSURANCE_WARNING_DEGRADED_EVIDENCE_TEMPLATE.format(
                    inputs=", ".join(context.degraded_inputs)
                )
            )
        return warnings

    @staticmethod
    def _build_summary(
        score: float,
        band: str,
        positive_factors: list[str],
        penalties: list[str],
    ) -> str:
        template = ASSURANCE_SUMMARY_TEMPLATES[band]
        top_positive = (
            f"Strongest support: {positive_factors[0]}" if positive_factors
            else "No single signal stood out as strongly supportive."
        )
        top_penalty = (
            f"Primary concern: {penalties[0]}" if penalties
            else "No component fell into the weak range."
        )
        return template.format(score=score, top_positive=top_positive, top_penalty=top_penalty)