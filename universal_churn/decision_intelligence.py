"""
universal_churn/decision_intelligence.py
══════════════════════════════════════════════════════════════════════
Decision Intelligence Layer — Version 8, Chunk 1.

Sits AFTER prediction and explanation:

    Prediction
      -> Prediction Explanation    (prediction_explanation.py)
      -> Decision Intelligence     (THIS MODULE)
      -> Executive Decision Report (decision_report.py)

This is a DIAGNOSTICS-ONLY layer. It must never, and does never:
    - retrain models
    - modify prediction probabilities
    - modify routing
    - modify feature engineering
    - modify semantic resolution
    - modify business reasoning
    - modify coverage
    - modify the quality gate

Prediction outputs remain byte-identical whether or not this module is
ever imported or called. It is a pure, read-only CONSUMER of outputs
already produced elsewhere:

    Prediction results          (pd.DataFrame — Predicted_Churn,
                                  Churn_Probability, Risk_Level, ...)
    Coverage Result              (coverage.py's dict, or the value
                                  already attached to
                                  results.attrs['coverage'])
    Quality Result                (quality_gate.py's dict, or the value
                                  already attached to
                                  results.attrs['quality'])
    Routing Decision              (routing.RoutingDecision, or the
                                  value already attached to
                                  results.attrs['routing_decision'])
    Concept Confidence Report    (concept_confidence.py's report,
                                  embedded inside the coverage dict by
                                  coverage.py — read from there, never
                                  recomputed here)
    Reasoning Report              (business_reasoning.ReasoningReport —
                                  built fresh, read-only, by calling
                                  business_reasoning.py's existing
                                  public run_business_reasoning(), or
                                  passed in already-built)
    Knowledge Base                 (knowledge_base.py, via
                                  knowledge_loader.py's singleton)

Nothing here recomputes any of those numbers — it only combines
already-produced values into a single executive-facing assessment,
the same way routing.py combines (but never mutates) Coverage and
Quality results into a RoutingDecision.

Non-interference guarantee
-----------------------------
No function in this module accepts a mutable prediction-pipeline
object and writes into it. `assess()` reads its inputs and returns a
new, frozen `DecisionAssessment`. Attaching that assessment to a
results DataFrame (see decision_report.py's `attach_decision_columns()`)
only ever APPENDS new `Decision_*` columns to a COPY of the frame —
exactly the pattern prediction_explanation_report.py already uses for
`Explanation_*` columns — and never overwrites an existing column or
mutates the input in place.

Nothing in cli.py, sector_pipeline.py, universal_pipeline.py,
routing.py, coverage.py, quality_gate.py, feature_engineering.py,
schema_resolution.py, or business_reasoning.py imports this module —
it is opt-in, additive tooling, called explicitly by whoever wants an
executive decision report (see decision_report.py's
`build_and_attach_decision_intelligence()`), exactly as
prediction_explanation.py was before it was wired into cli.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

import pandas as pd

from .routing import RoutingDecision, ReliabilityLevel
from .business_reasoning import ReasoningReport
from .concept_confidence import MIN_RECONSTRUCTABLE_OVERALL_CONFIDENCE
from .knowledge_base import KnowledgeBase
from .knowledge_loader import get_default_knowledge_base


# ══════════════════════════════════════════════════════════════════
# THRESHOLDS
# ══════════════════════════════════════════════════════════════════
# Deliberately separate constants from every other module's — decision
# readiness is its own axis and should be tunable independently of
# coverage.py's Green/Yellow/Red bands or quality_gate.py's leakage
# thresholds.

#: Below this concept confidence, evidence is considered insufficient
#: to act on at all. Reuses concept_confidence.py's own
#: reconstructability floor (0.15) rather than inventing a second,
#: competing "is there any signal at all" threshold.
MIN_CONCEPT_CONFIDENCE_FOR_EVIDENCE: float = MIN_RECONSTRUCTABLE_OVERALL_CONFIDENCE  # 0.15

#: Concept confidence at/above this is "enough business signal to act
#: on automatically", per the Chunk 1 spec's READY rule.
READY_CONCEPT_CONFIDENCE_MIN: float = 0.40

#: Reliability -> point mapping used by the Technical Confidence score.
_RELIABILITY_POINTS: dict[str, float] = {
    ReliabilityLevel.VERY_HIGH.value: 1.00,
    ReliabilityLevel.HIGH.value: 0.80,
    ReliabilityLevel.MODERATE.value: 0.55,
    ReliabilityLevel.LOW.value: 0.30,
    ReliabilityLevel.VERY_LOW.value: 0.00,
}

_SEVERITY_RANK: dict[str, int] = {'LOW': 0, 'MEDIUM': 1, 'HIGH': 2, 'CRITICAL': 3}
_HEALTH_POINTS: dict[str, float] = {'LOW': 0.0, 'MEDIUM': 0.5, 'HIGH': 1.0, 'Unknown': 0.5}


# ══════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════

class DecisionReadiness(str, Enum):
    """
    Whether this prediction is ready to drive an automated business
    action, per the Chunk 1 spec's three-way policy:

        READY
            coverage >= Yellow AND quality GOOD AND
            concept confidence >= 0.40

        REVIEW
            coverage Red, OR concept confidence in [0.15, 0.40)

        INSUFFICIENT_EVIDENCE
            quality FAILED, OR concept confidence below the
            reconstructability floor (< 0.15, including "never
            computed" / unavailable)

    See `_derive_decision_readiness()` for the exact evaluation order
    (hardest block first, mirroring routing.route()'s "quality gate is
    the hard, mode-independent block, checked first" policy).
    """
    READY = "READY"
    REVIEW = "REVIEW"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class RiskLevel(str, Enum):
    """
    Coarse business-risk label. Sourced from the Reasoning Report's
    own `overall_customer_risk` (business_reasoning.py's worst-fired-
    finding severity) when available; otherwise derived from the
    dataset's predicted-churn rate as a neutral, purely descriptive
    fallback that invents no new business reasoning.
    """
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


# ══════════════════════════════════════════════════════════════════
# DATACLASSES
# ══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DecisionEvidenceItem:
    """
    One piece of evidence feeding the assessment, tagged with the
    existing object that produced it — same pattern as
    prediction_explanation.PredictionEvidenceItem.

    Attributes
    ----------
    name : str
        Human-readable label for this evidence item.
    value : str
        The already-computed value, formatted for display.
    source : str
        Which existing object produced this value (e.g.
        'CoverageResult', 'QualityResult', 'RoutingDecision',
        'ConceptConfidenceReport', 'ReasoningReport'). Never a value
        this module invented itself.
    """
    name: str
    value: str
    source: str

    def to_dict(self) -> dict:
        return {'name': self.name, 'value': self.value, 'source': self.source}


@dataclass(frozen=True)
class DecisionAssessment:
    """
    The Chunk 1 deliverable: one executive-facing assessment for a
    prediction run. Immutable once built — a fresh `assess()` call is
    required to reflect any change in upstream state.

    Attributes
    ----------
    overall_confidence : float
        Weighted combination of `business_confidence` and
        `technical_confidence` — the single top-line number, in
        [0, 1]. This is "how much should an executive trust this
        prediction, end to end."
    business_confidence : float
        How much a domain expert should trust the BUSINESS story
        behind this prediction. Derived ONLY from Business Concepts
        (Concept Confidence), Knowledge Base findings (via the
        Reasoning Report, which has already applied KB-driven rules),
        and the Reasoning Report's business-health summary. In [0, 1].
    technical_confidence : float
        How much a data/ML engineer should trust the PIPELINE behind
        this prediction. Derived ONLY from Coverage, Quality, and
        Routing. In [0, 1].
    evidence_strength : float
        Normalized combination of Coverage, Concept Confidence,
        Quality, Routing, and Reasoning into one score, in [0, 1],
        WITHOUT changing any of the underlying values. This is the
        "how much do we actually know about this input" axis —
        distinct from confidence, which is "how much do we trust what
        we know."
    decision_readiness : DecisionReadiness
        READY / REVIEW / INSUFFICIENT_EVIDENCE.
    recommended_action : str
        One deterministic, template-assembled executive recommendation
        sentence. No LLM, no generative text — pure lookup/formatting
        over already-computed state.
    risk_level : RiskLevel
        LOW / MEDIUM / HIGH / CRITICAL / UNKNOWN business risk label.
    supporting_evidence : tuple[DecisionEvidenceItem, ...]
        Evidence items, each citing the existing object it came from.
    warnings : tuple[str, ...]
        Caveats worth surfacing to an executive reader — echoes
        routing warnings / quality warnings / low-confidence concepts.
        Never invents a new warning condition of its own beyond
        formatting an already-known fact.
    sector : str
        The sector this assessment was built for.
    generated_at : str
        UTC timestamp, formatted identically to every other report
        printer in this codebase (see utils._utc_timestamp()'s format).
    """
    overall_confidence: float
    business_confidence: float
    technical_confidence: float
    evidence_strength: float
    decision_readiness: DecisionReadiness
    recommended_action: str
    risk_level: RiskLevel
    supporting_evidence: tuple[DecisionEvidenceItem, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    sector: str = ""
    generated_at: str = ""

    def to_dict(self) -> dict:
        return {
            'overall_confidence': self.overall_confidence,
            'business_confidence': self.business_confidence,
            'technical_confidence': self.technical_confidence,
            'evidence_strength': self.evidence_strength,
            'decision_readiness': self.decision_readiness.value,
            'recommended_action': self.recommended_action,
            'risk_level': self.risk_level.value,
            'supporting_evidence': [e.to_dict() for e in self.supporting_evidence],
            'warnings': list(self.warnings),
            'sector': self.sector,
            'generated_at': self.generated_at,
        }


# ══════════════════════════════════════════════════════════════════
# COMPONENT SCORES
# ══════════════════════════════════════════════════════════════════
# Every function below READS an already-computed number (or returns a
# neutral 0.5 default when that number is unavailable) — none of them
# write back to, or alter, the object they read from.

def _coverage_component(coverage: dict | None) -> float:
    """coverage_score is already a [0,1] float in coverage.py's dict —
    used as-is, never recomputed."""
    if coverage is None:
        return 0.5
    return float(coverage.get('coverage_score', 0.5))


def _concept_confidence_value(coverage: dict | None) -> float | None:
    """Read concept_confidence.py's overall_confidence straight out of
    the coverage dict coverage.py already embedded it in — returns
    None (not 0.0) when unavailable, so callers can distinguish 'no
    data' from 'zero confidence'."""
    if not coverage:
        return None
    concept_data = coverage.get('concept_confidence')
    if not concept_data:
        return None
    return concept_data.get('overall_confidence')


def _quality_component(quality_status: str) -> float:
    return {'GOOD': 1.0, 'WARN': 0.5, 'FAIL': 0.0}.get(quality_status, 0.5)


def _routing_component(routing_decision: RoutingDecision | None) -> float:
    if routing_decision is None:
        return 0.5
    return _RELIABILITY_POINTS.get(routing_decision.reliability.value, 0.5)


def _reasoning_component(reasoning_report: ReasoningReport | None) -> float:
    """Mean confidence of fired findings; neutral (0.5) if none fired
    or no report is available — absence of a finding is not evidence
    of low quality, mirroring routing.py's treatment of missing
    concept confidence as neutral rather than penalized."""
    if reasoning_report is None or not reasoning_report.findings:
        return 0.5
    confidences = [f.confidence for f in reasoning_report.findings]
    return sum(confidences) / len(confidences)


def _health_component(reasoning_report: ReasoningReport | None) -> float:
    if reasoning_report is None or reasoning_report.summary is None:
        return 0.5
    return _HEALTH_POINTS.get(reasoning_report.summary.overall_business_health, 0.5)


# ══════════════════════════════════════════════════════════════════
# EVIDENCE STRENGTH
# ══════════════════════════════════════════════════════════════════

_EVIDENCE_WEIGHTS: dict[str, float] = {
    'coverage': 0.25,
    'concept': 0.25,
    'quality': 0.25,
    'routing': 0.15,
    'reasoning': 0.10,
}


def _compute_evidence_strength(
    coverage: dict | None,
    quality_status: str,
    routing_decision: RoutingDecision | None,
    reasoning_report: ReasoningReport | None,
) -> float:
    """
    Combine Coverage, Concept Confidence, Quality, Routing, and
    Reasoning into one normalized [0, 1] score, WITHOUT changing any
    of the underlying values — every component reads an
    already-computed number (or a neutral 0.5 default when
    unavailable), and this function only takes a fixed weighted
    average of them.
    """
    concept_conf = _concept_confidence_value(coverage)
    components = {
        'coverage': _coverage_component(coverage),
        'concept': concept_conf if concept_conf is not None else 0.5,
        'quality': _quality_component(quality_status),
        'routing': _routing_component(routing_decision),
        'reasoning': _reasoning_component(reasoning_report),
    }
    score = sum(components[k] * _EVIDENCE_WEIGHTS[k] for k in _EVIDENCE_WEIGHTS)
    return round(min(max(score, 0.0), 1.0), 4)


# ══════════════════════════════════════════════════════════════════
# BUSINESS / TECHNICAL CONFIDENCE
# ══════════════════════════════════════════════════════════════════

def _compute_business_confidence(
    coverage: dict | None,
    reasoning_report: ReasoningReport | None,
) -> float:
    """
    Derived ONLY from Business Concepts (Concept Confidence), the
    Knowledge Base (via fired findings' confidence — already floored
    at business_reasoning.MIN_FINDING_CONFIDENCE by that module), and
    the Reasoning Report's business-health summary. Coverage, Quality,
    and Routing never enter this calculation — see
    `_compute_technical_confidence()` for those.
    """
    concept_conf = _concept_confidence_value(coverage)
    components = [
        concept_conf if concept_conf is not None else 0.5,
        _reasoning_component(reasoning_report),
        _health_component(reasoning_report),
    ]
    return round(sum(components) / len(components), 4)


def _compute_technical_confidence(
    coverage: dict | None,
    quality_status: str,
    routing_decision: RoutingDecision | None,
) -> float:
    """
    Derived ONLY from Coverage, Quality, and Routing — mirrors
    routing.py's own `_derive_reliability()` point scoring in spirit,
    expressed as a continuous [0, 1] score rather than a five-band
    label (ReliabilityLevel already exists for the label; this is the
    numeric counterpart Decision Intelligence needs for averaging).
    """
    components = [
        _coverage_component(coverage),
        _quality_component(quality_status),
        _routing_component(routing_decision),
    ]
    return round(sum(components) / len(components), 4)


# ══════════════════════════════════════════════════════════════════
# DECISION READINESS
# ══════════════════════════════════════════════════════════════════

def _derive_decision_readiness(
    coverage_band: str,
    quality_status: str,
    concept_confidence: float | None,
) -> DecisionReadiness:
    """
    Three-way policy, evaluated hardest-block-first — mirrors
    routing.route()'s "quality gate is the hard, mode-independent
    block, checked first" ordering:

        1. INSUFFICIENT_EVIDENCE — quality FAILED, or concept
           confidence is below the reconstructability floor (< 0.15).
           A `None` concept confidence (never computed) is treated the
           same as "below the floor": Decision Intelligence cannot
           certify sufficient evidence about an input it has no
           concept-confidence data for at all.
        2. REVIEW — coverage is Red, or concept confidence sits in the
           [0.15, 0.40) band (some signal, not enough to automate on).
        3. READY — coverage is Green or Yellow, quality is GOOD, and
           concept confidence is >= 0.40.
        4. Fallback — REVIEW (a conservative default for any state
           that doesn't cleanly match rows 1-3, e.g. Yellow coverage
           combined with WARN quality).
    """
    if quality_status == 'FAIL':
        return DecisionReadiness.INSUFFICIENT_EVIDENCE
    if concept_confidence is None or concept_confidence < MIN_CONCEPT_CONFIDENCE_FOR_EVIDENCE:
        return DecisionReadiness.INSUFFICIENT_EVIDENCE

    if coverage_band == 'Red':
        return DecisionReadiness.REVIEW
    if MIN_CONCEPT_CONFIDENCE_FOR_EVIDENCE <= concept_confidence < READY_CONCEPT_CONFIDENCE_MIN:
        return DecisionReadiness.REVIEW

    if (
        coverage_band in ('Green', 'Yellow')
        and quality_status == 'GOOD'
        and concept_confidence >= READY_CONCEPT_CONFIDENCE_MIN
    ):
        return DecisionReadiness.READY

    return DecisionReadiness.REVIEW


# ══════════════════════════════════════════════════════════════════
# RISK LEVEL
# ══════════════════════════════════════════════════════════════════

def _derive_risk_level(
    reasoning_report: ReasoningReport | None,
    results: pd.DataFrame | None,
) -> RiskLevel:
    """
    Prefer the Reasoning Report's own `overall_customer_risk` (already
    the worst fired finding's severity — see business_reasoning.py's
    `_summarize()`). Falls back to the dataset's predicted-churn rate
    only when no reasoning summary is available at all, so this
    function never invents business reasoning of its own — it either
    reads business_reasoning.py's answer, or falls back to a purely
    descriptive statistic of `results`, which already exists.
    """
    if reasoning_report is not None and reasoning_report.summary is not None:
        try:
            return RiskLevel(reasoning_report.summary.overall_customer_risk)
        except ValueError:
            pass  # unrecognized label — fall through to the dataset-rate fallback

    if results is not None and len(results) and 'Predicted_Churn' in results.columns:
        rate = (results['Predicted_Churn'] == 'Yes').mean()
        if rate >= 0.60:
            return RiskLevel.HIGH
        if rate >= 0.30:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    return RiskLevel.UNKNOWN


# ══════════════════════════════════════════════════════════════════
# EXECUTIVE RECOMMENDATION
# ══════════════════════════════════════════════════════════════════

def _recommend_action(
    decision_readiness: DecisionReadiness,
    risk_level: RiskLevel,
    reasoning_report: ReasoningReport | None,
) -> str:
    """
    Deterministic, template-assembled recommendation text — no LLM, no
    generative model, pure lookup/formatting over already-computed
    state. Mirrors prediction_explanation.py's narrative templates in
    spirit (see `_build_narrative()` there).
    """
    if decision_readiness == DecisionReadiness.INSUFFICIENT_EVIDENCE:
        return (
            "Prediction not suitable for automated action — collect "
            "additional customer information before deciding."
        )

    if decision_readiness == DecisionReadiness.REVIEW:
        return (
            "Review prediction manually before acting — evidence is "
            "present but not yet strong enough to automate."
        )

    # READY
    top_finding = None
    if reasoning_report is not None and reasoning_report.findings:
        top_finding = max(
            reasoning_report.findings,
            key=lambda f: _SEVERITY_RANK.get(f.severity.value, 0),
        )

    if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
        if top_finding is not None and top_finding.recommendation:
            return f"Proceed with retention campaign — {top_finding.recommendation}"
        return "Proceed with retention campaign for this customer segment."

    if risk_level == RiskLevel.MEDIUM:
        return "Proceed with targeted monitoring; escalate to a retention campaign if risk increases."

    return "Proceed with standard monitoring — no immediate action required."


# ══════════════════════════════════════════════════════════════════
# WARNINGS / EVIDENCE ASSEMBLY
# ══════════════════════════════════════════════════════════════════

def _collect_warnings(
    quality_status: str,
    routing_decision: RoutingDecision | None,
    concept_confidence: float | None,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if quality_status == 'WARN':
        warnings.append("Data quality gate returned WARN — see the Quality Report for detail.")
    if quality_status == 'FAIL':
        warnings.append("Data quality gate FAILED (target leakage detected) — evidence is unreliable.")
    if routing_decision is not None:
        warnings.extend(routing_decision.warnings)
    if concept_confidence is not None and concept_confidence < READY_CONCEPT_CONFIDENCE_MIN:
        warnings.append(
            f"Concept confidence is {concept_confidence*100:.1f}%, below the "
            f"{READY_CONCEPT_CONFIDENCE_MIN*100:.0f}% automation threshold."
        )
    if concept_confidence is None:
        warnings.append("Concept confidence data unavailable for this input.")

    # De-duplicate while preserving order — a warning that is both a
    # routing warning and independently detected here should surface
    # once, not twice.
    seen: list[str] = []
    for w in warnings:
        if w not in seen:
            seen.append(w)
    return tuple(seen)


def _collect_evidence(
    coverage: dict | None,
    quality_status: str,
    routing_decision: RoutingDecision | None,
    reasoning_report: ReasoningReport | None,
) -> tuple[DecisionEvidenceItem, ...]:
    items: list[DecisionEvidenceItem] = []
    coverage_score = _coverage_component(coverage)
    coverage_band = coverage.get('status', 'Unknown') if coverage else 'Unknown'
    concept_conf = _concept_confidence_value(coverage)

    items.append(DecisionEvidenceItem(
        name="Coverage Score", value=f"{coverage_score*100:.1f}%", source="CoverageResult",
    ))
    items.append(DecisionEvidenceItem(
        name="Coverage Band", value=coverage_band, source="CoverageResult",
    ))
    items.append(DecisionEvidenceItem(
        name="Concept Confidence",
        value=f"{concept_conf*100:.1f}%" if concept_conf is not None else "N/A",
        source="ConceptConfidenceReport",
    ))
    items.append(DecisionEvidenceItem(
        name="Quality Status", value=quality_status, source="QualityResult",
    ))
    if routing_decision is not None:
        items.append(DecisionEvidenceItem(
            name="Selected Model", value=routing_decision.selected_model.value,
            source="RoutingDecision",
        ))
        items.append(DecisionEvidenceItem(
            name="Prediction Reliability", value=routing_decision.reliability.value,
            source="RoutingDecision",
        ))
    if reasoning_report is not None:
        items.append(DecisionEvidenceItem(
            name="Business Findings Fired", value=str(len(reasoning_report.findings)),
            source="ReasoningReport",
        ))
        if reasoning_report.summary is not None:
            items.append(DecisionEvidenceItem(
                name="Business Health", value=reasoning_report.summary.overall_business_health,
                source="ReasoningReport",
            ))
    return tuple(items)


# ══════════════════════════════════════════════════════════════════
# QUALITY STATUS ADAPTER
# ══════════════════════════════════════════════════════════════════

def _quality_status_from(
    quality: dict | None,
    routing_decision: RoutingDecision | None,
) -> str:
    """
    Mirrors routing.QualityResult.from_quality_dict()'s GOOD/WARN/FAIL
    derivation (reading the same quality_gate.py dict shape it does)
    without importing that adapter's dataclass machinery. Falls back
    to the already-computed RoutingDecision.quality_status when no raw
    quality dict is available (e.g. a universal-mode fallback call
    that only received `_precomputed_coverage`), and finally to
    'Unknown' if neither is available. Never recomputes quality_gate.py's
    underlying checks — only reads its dict output.
    """
    if quality is not None:
        leakage_detected = quality.get('leakage_detected', False)
        failed_columns = quality.get('failed_columns', [])
        leakage_flagged = quality.get('leakage_flagged', [])
        leakage_warned = quality.get('leakage_warned', [])
        non_leakage_failures = [c for c in failed_columns if c not in leakage_flagged]
        if leakage_detected:
            return 'FAIL'
        if non_leakage_failures or leakage_warned:
            return 'WARN'
        return 'GOOD'
    if routing_decision is not None:
        return routing_decision.quality_status
    return 'Unknown'


# ══════════════════════════════════════════════════════════════════
# PUBLIC ENGINE
# ══════════════════════════════════════════════════════════════════

class DecisionIntelligenceEngine:
    """
    Combines Prediction, Coverage, Quality, Routing, Concept
    Confidence, Reasoning, and the Knowledge Base into one
    DecisionAssessment. Stateless aside from an optional injected
    KnowledgeBase — this chunk's `business_confidence` calculation
    reads the already-produced Reasoning Report (which has already
    applied Knowledge-Base-driven rules), so `assess()` does not need
    to re-consult the Knowledge Base directly; the reference is kept
    on the engine for future extension and diagnostics only.
    """

    def __init__(self, knowledge_base: KnowledgeBase | None = None) -> None:
        self.knowledge_base = knowledge_base or get_default_knowledge_base()

    def assess(
        self,
        sector: str,
        results: pd.DataFrame | None = None,
        coverage: dict | None = None,
        quality: dict | None = None,
        routing_decision: RoutingDecision | None = None,
        reasoning_report: ReasoningReport | None = None,
    ) -> DecisionAssessment:
        """
        Build one DecisionAssessment from already-computed pipeline
        outputs. Every argument is optional and independently
        nullable — a partial call (e.g. only `coverage` + `quality`,
        no `reasoning_report`) still returns a complete assessment,
        with missing signals treated neutrally rather than penalized
        (matching routing.py's own handling of missing concept-
        confidence data). Does not mutate any argument.
        """
        quality_status = _quality_status_from(quality, routing_decision)
        coverage_band = (
            coverage.get('status', 'Unknown') if coverage
            else (routing_decision.coverage_band if routing_decision else 'Unknown')
        )
        concept_confidence = _concept_confidence_value(coverage)
        if concept_confidence is None and routing_decision is not None:
            concept_confidence = routing_decision.concept_confidence

        evidence_strength = _compute_evidence_strength(
            coverage, quality_status, routing_decision, reasoning_report)
        business_confidence = _compute_business_confidence(coverage, reasoning_report)
        technical_confidence = _compute_technical_confidence(
            coverage, quality_status, routing_decision)
        overall_confidence = round((business_confidence + technical_confidence) / 2, 4)

        decision_readiness = _derive_decision_readiness(
            coverage_band, quality_status, concept_confidence)
        risk_level = _derive_risk_level(reasoning_report, results)
        recommended_action = _recommend_action(decision_readiness, risk_level, reasoning_report)

        warnings = _collect_warnings(quality_status, routing_decision, concept_confidence)
        supporting_evidence = _collect_evidence(
            coverage, quality_status, routing_decision, reasoning_report)

        return DecisionAssessment(
            overall_confidence=overall_confidence,
            business_confidence=business_confidence,
            technical_confidence=technical_confidence,
            evidence_strength=evidence_strength,
            decision_readiness=decision_readiness,
            recommended_action=recommended_action,
            risk_level=risk_level,
            supporting_evidence=supporting_evidence,
            warnings=warnings,
            sector=sector,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        )


def run_decision_intelligence(
    sector: str,
    results: pd.DataFrame | None = None,
    coverage: dict | None = None,
    quality: dict | None = None,
    routing_decision: RoutingDecision | None = None,
    reasoning_report: ReasoningReport | None = None,
) -> DecisionAssessment:
    """Module-level convenience wrapper around a default-configured engine."""
    return DecisionIntelligenceEngine().assess(
        sector=sector, results=results, coverage=coverage, quality=quality,
        routing_decision=routing_decision, reasoning_report=reasoning_report,
    )


# ══════════════════════════════════════════════════════════════════
# MERMAID ARCHITECTURE DIAGRAM
# ══════════════════════════════════════════════════════════════════

def to_mermaid() -> str:
    """
    Static architecture diagram for the Decision Intelligence layer
    and its place in the wider pipeline. Purely descriptive text — has
    no effect on, and reads no state from, the live pipeline.
    """
    return (
        "graph TD\n"
        "    Prediction[Prediction] --> Explanation[Prediction Explanation]\n"
        "    Explanation --> DI[Decision Intelligence]\n"
        "    DI --> Report[Executive Decision Report]\n"
        "    Coverage[Coverage Result] --> DI\n"
        "    Quality[Quality Result] --> DI\n"
        "    Routing[Routing Decision] --> DI\n"
        "    ConceptConf[Concept Confidence Report] --> DI\n"
        "    Reasoning[Reasoning Report] --> DI\n"
        "    KB[Knowledge Base] --> Reasoning\n"
    )
