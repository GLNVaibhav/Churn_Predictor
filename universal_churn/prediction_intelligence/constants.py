"""
universal_churn/prediction_intelligence/constants.py
══════════════════════════════════════════════════════════════════════
Band thresholds for the Prediction Intelligence Engine (PIE).

Deliberately a SEPARATE set of constants from every other module's
thresholds (coverage.py's Green/Yellow/Red, quality_gate.py's leakage
correlation cutoffs, routing.py's ReliabilityLevel scoring) — PIE
measures a different thing (trustworthiness/stability of an already-
made prediction, not input completeness or routing eligibility) and
should be tunable independently.

Every PIE engine that produces a 0-100 score (Prediction Confidence,
Evidence Strength, Prediction Stability, Consistency, the final
Prediction Intelligence Score) uses the SAME five-band vocabulary —
VERY_HIGH / HIGH / MODERATE / LOW / VERY_LOW — so a report reader only
has to learn one scale, not five. `band_for_score()` is the single
place that maps a score to a band; every engine calls it rather than
re-implementing its own if/elif ladder (mirrors coverage.py /
routing.py's pattern of one banding function per axis, reused
everywhere that axis is reported).
"""
from __future__ import annotations

# ── Universal band thresholds (0-100 scale) ─────────────────────────
# Same cut points reused by every PIE engine unless an engine has a
# documented, specific reason to diverge (none do as of Module 1).
BAND_VERY_HIGH_MIN = 85.0
BAND_HIGH_MIN       = 70.0
BAND_MODERATE_MIN   = 50.0
BAND_LOW_MIN        = 30.0
# Below BAND_LOW_MIN -> VERY_LOW

BAND_VERY_HIGH = "VERY_HIGH"
BAND_HIGH       = "HIGH"
BAND_MODERATE   = "MODERATE"
BAND_LOW        = "LOW"
BAND_VERY_LOW   = "VERY_LOW"

ALL_BANDS = (BAND_VERY_HIGH, BAND_HIGH, BAND_MODERATE, BAND_LOW, BAND_VERY_LOW)


def band_for_score(score: float) -> str:
    """
    Map a 0-100 score to one of the five PIE bands. Values outside
    [0, 100] are clamped rather than raising — every engine that feeds
    this already clamps its own component scores to [0, 100], so this
    is a defensive second layer, not the primary guarantee.
    """
    clamped = max(0.0, min(100.0, score))
    if clamped >= BAND_VERY_HIGH_MIN:
        return BAND_VERY_HIGH
    if clamped >= BAND_HIGH_MIN:
        return BAND_HIGH
    if clamped >= BAND_MODERATE_MIN:
        return BAND_MODERATE
    if clamped >= BAND_LOW_MIN:
        return BAND_LOW
    return BAND_VERY_LOW


# ── Quality status -> point mapping ─────────────────────────────────
# Reused by any engine that needs to fold QualityResult into a 0-100
# component score. Mirrors routing.py's own GOOD=2/WARN=1/FAIL=0
# points, rescaled to 0-100.
QUALITY_STATUS_POINTS: dict[str, float] = {
    "GOOD": 100.0,
    "WARN": 50.0,
    "FAIL": 0.0,
}
QUALITY_STATUS_NEUTRAL_DEFAULT = 50.0  # unknown/missing quality status

# ── Routing reliability -> point mapping ────────────────────────────
# Reuses routing.ReliabilityLevel's five bands, rescaled to 0-100.
# Kept as plain string keys (rather than importing the enum) so this
# module never has a hard import dependency on routing.py — callers
# that DO have a ReliabilityLevel just pass `.value`.
RELIABILITY_POINTS: dict[str, float] = {
    "Very High": 100.0,
    "High": 80.0,
    "Moderate": 55.0,
    "Low": 30.0,
    "Very Low": 0.0,
}
RELIABILITY_NEUTRAL_DEFAULT = 50.0  # missing routing decision

# ── Degradation reason codes ─────────────────────────────────────────
# Recorded on PredictionIntelligenceContext.degraded_inputs whenever an
# optional or expected input is missing — the report must record this
# explicitly, per the "degrade gracefully, never treat as failure"
# contract rule.
DEGRADED_NO_ROUTING_DECISION   = "routing_decision_unavailable"
DEGRADED_NO_QUALITY_RESULT     = "quality_result_unavailable"
DEGRADED_NO_CONCEPT_CONFIDENCE = "concept_confidence_unavailable"
DEGRADED_NO_REASONING_REPORT   = "reasoning_report_not_supplied"
DEGRADED_NO_PREDICTION_EXPLANATION = "prediction_explanation_not_supplied"


# ══════════════════════════════════════════════════════════════════
# PREDICTION ASSURANCE ENGINE — bands, thresholds, labels, messages
# ══════════════════════════════════════════════════════════════════
# "How strongly does the framework stand behind this prediction?"
# Assurance reuses the SAME 0-100 scale and band_for_score() as every
# other PIE engine (see module docstring) — a separate band vocabulary
# would fragment the "one scale, one meaning" principle this module
# already establishes. What IS specific to Assurance is which raw
# component scores count as a callable-out "positive factor" vs.
# "penalty", and the fixed label/message text used to build both lists
# plus the human-readable summary — all centralized here so
# engines/prediction_assurance.py never hardcodes a string.

# A component's raw (pre-weight) 0-100 score at or above this is
# strong enough to cite as a POSITIVE FACTOR in the assurance result.
ASSURANCE_STRONG_SIGNAL_MIN = 70.0

# A component's raw score at or below this is weak enough to cite as
# a PENALTY. Between ASSURANCE_WEAK_SIGNAL_MAX and
# ASSURANCE_STRONG_SIGNAL_MIN, a component is neutral — informative in
# the metadata breakdown, but not called out as either a strength or a
# weakness in the narrative fields.
ASSURANCE_WEAK_SIGNAL_MAX = 40.0

# Human-readable display names for each Assurance component, keyed by
# the same names used in weights.ASSURANCE_WEIGHTS. Centralizing this
# mapping means engines/prediction_assurance.py never hand-writes a
# label string, and a future rename only touches this one dict.
ASSURANCE_COMPONENT_LABELS: dict[str, str] = {
    "coverage": "Coverage",
    "concept_confidence": "Concept Confidence",
    "quality": "Quality",
    "routing_reliability": "Routing Reliability",
    "prediction_reliability": "Prediction Reliability",
}

# Template used for every POSITIVE FACTOR line. `{label}` and
# `{score:.1f}` are filled in by the engine.
ASSURANCE_POSITIVE_FACTOR_TEMPLATE = "{label} is strong ({score:.1f}/100)."

# Template used for every PENALTY line.
ASSURANCE_PENALTY_TEMPLATE = "{label} is weak ({score:.1f}/100) and reduces assurance."

# Hard warning messages — surfaced regardless of the component-level
# positive-factor / penalty classification, because these describe a
# framework-level condition (not just a weak signal) serious enough to
# warrant an explicit warning line of its own.
ASSURANCE_WARNING_QUALITY_FAIL = (
    "Quality gate FAILED (target leakage detected) — treat this "
    "prediction with extreme caution regardless of the assurance score."
)
ASSURANCE_WARNING_ROUTING_REJECTED = (
    "Routing rejected this input (CRITICAL_UNRELIABLE) — this "
    "prediction should not be acted on."
)
ASSURANCE_WARNING_DEGRADED_EVIDENCE_TEMPLATE = (
    "Evidence reduced — the following inputs were unavailable: {inputs}."
)

# Summary sentence templates, keyed by band. `{score}`, `{top_positive}`,
# and `{top_penalty}` are filled in by the engine; a template does not
# have to use every placeholder.
ASSURANCE_SUMMARY_TEMPLATES: dict[str, str] = {
    BAND_VERY_HIGH: (
        "The framework has very high assurance in this prediction "
        "({score:.1f}/100). {top_positive}"
    ),
    BAND_HIGH: (
        "The framework has high assurance in this prediction "
        "({score:.1f}/100). {top_positive}"
    ),
    BAND_MODERATE: (
        "The framework has moderate assurance in this prediction "
        "({score:.1f}/100) — usable, but not airtight. {top_penalty}"
    ),
    BAND_LOW: (
        "The framework has low assurance in this prediction "
        "({score:.1f}/100). {top_penalty}"
    ),
    BAND_VERY_LOW: (
        "The framework has very low assurance in this prediction "
        "({score:.1f}/100) — treat it as unreliable. {top_penalty}"
    ),
}