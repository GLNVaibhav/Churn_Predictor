"""
universal_churn/business_reasoning.py
══════════════════════════════════════════════════════════════════════
Business Reasoning Engine — Version 7, Chunk 3.

Extends (does NOT replace) the Business Concept Graph
(business_concept_graph.py) with a deterministic reasoning layer that
turns per-concept signals into human-readable Business Findings.

Target architecture (this chunk)
----------------------------------
    Canonical Fields
      -> Business Concept Graph      (business_concept_graph.py, unchanged)
      -> Business Reasoning Engine   (THIS MODULE)
      -> Reasoning State             (ReasoningReport, below)
      -> Prediction                  (untouched — see module docstring
                                       note on non-interference)

Two inputs, one report
------------------------
The Business Concept Graph (business_concept_graph.resolve_graph_confidence)
answers "how confidently can we reconstruct concept X for this input
file at all" — it is a SCHEMA-level signal and carries no per-row
concept VALUE.

The per-row concept VALUE (e.g. "this population's engagement is
low") comes from the existing, unmodified business_concepts.
compute_concept_values(), which this module also calls, unchanged.

BusinessReasoningEngine.analyze() combines both:
    1. Runs the (existing, unmodified) schema resolution + concept
       graph propagation to get per-concept RECONSTRUCTION CONFIDENCE.
    2. Runs the (existing, unmodified) per-row concept value
       computation and aggregates it (population mean) into a
       LOW / MEDIUM / HIGH band per concept.
    3. Packages both into a BusinessInference per concept.
    4. Evaluates the deterministic rule set (Part 2) against those
       inferences to produce BusinessFinding objects.
    5. Summarizes everything into a ReasoningReport (Part 5).

Non-interference guarantee
-----------------------------
This module is purely ADDITIVE and READ-ONLY with respect to every
other module in the package:
    - It does not modify schema_resolution.py, feature_engineering.py,
      coverage.py, routing.py, business_concepts.py, or
      business_concept_graph.py.
    - It is not imported by cli.py, sector_pipeline.py,
      universal_pipeline.py, or routing.py — nothing on the prediction
      path calls into this module, so prediction output is bit-for-bit
      identical to before this chunk (see BUSINESS_REASONING_ENGINE.md,
      "Prediction Parity").
    - ReasoningReport is diagnostics-only. No model consumes it yet;
      a future Core Model (see core_model_interface.py) is the
      documented future consumer (Chunk 5+), not this chunk.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

import pandas as pd

from .business_concepts import BUSINESS_CONCEPTS, CONCEPT_NAMES, compute_concept_values
from .business_concept_graph import (
    BusinessConceptGraph, BusinessConceptNode, resolve_graph_confidence,
)
from .schema_resolution import resolve_schema
from .concept_confidence import MIN_RECONSTRUCTABLE_OVERALL_CONFIDENCE


# ══════════════════════════════════════════════════════════════════
# CONFIGURATION — concept value banding + direction + reasoning gate
# ══════════════════════════════════════════════════════════════════

# A concept's aggregate [0,1] value is banded into one of three
# levels. These thresholds are deliberately symmetric around the
# concept's own neutral midpoint (0.5) — the same midpoint
# business_concepts.py already uses for "no signal" / "unavailable"
# concept values, so an unavailable concept bands to MEDIUM rather
# than spuriously LOW or HIGH.
LOW_BAND_MAX  = 0.35
HIGH_BAND_MIN = 0.65


class ConceptBand(str, Enum):
    LOW    = "LOW"
    MEDIUM = "MEDIUM"
    HIGH   = "HIGH"


def _band_for(value: float) -> ConceptBand:
    if value <= LOW_BAND_MAX:
        return ConceptBand.LOW
    if value >= HIGH_BAND_MIN:
        return ConceptBand.HIGH
    return ConceptBand.MEDIUM


class Direction(str, Enum):
    """
    Whether HIGH is a good sign or a bad sign for this concept, purely
    for the reasoning summary's strengths/weaknesses classification —
    rules themselves (Part 2) reason about bands directly and do not
    consult this.
    """
    HIGH_IS_GOOD = "high_is_good"
    HIGH_IS_BAD  = "high_is_bad"
    NEUTRAL      = "neutral"   # e.g. RECURRING_COMMITMENT — a size, not a health signal


CONCEPT_DIRECTION: dict[str, Direction] = {
    "CUSTOMER_LOYALTY":     Direction.HIGH_IS_GOOD,
    "ENGAGEMENT_LEVEL":     Direction.HIGH_IS_GOOD,
    "SATISFACTION_SIGNAL":  Direction.HIGH_IS_GOOD,
    "SUPPORT_FRICTION":     Direction.HIGH_IS_BAD,
    "RECURRING_COMMITMENT": Direction.NEUTRAL,
}

# Concepts whose reconstruction confidence is below this floor are
# treated as "insufficient evidence" by the rule engine — a rule will
# not fire on a concept we can barely reconstruct for this input file,
# even if its aggregate value happens to land in a triggering band.
# Reuses concept_confidence.py's existing reconstructability floor
# rather than inventing a second, competing threshold.
MIN_FINDING_CONFIDENCE = MIN_RECONSTRUCTABLE_OVERALL_CONFIDENCE


# ══════════════════════════════════════════════════════════════════
# PART 1 — DATACLASSES
# ══════════════════════════════════════════════════════════════════

@dataclass
class BusinessInference:
    """
    One concept's reasoning-ready summary for a given input file +
    sector — the unit the rule engine (Part 2) actually reasons over.
    """
    concept_id: str
    aggregate_value: float               # population-mean concept value, [0,1]
    band: ConceptBand
    confidence: float                    # graph reconstruction confidence, [0,1]
    reconstructable: bool
    dependency_health: str                # 'GOOD' | 'FAIR' | 'POOR' (from the graph node)
    resolved_fields: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)

    @property
    def has_sufficient_evidence(self) -> bool:
        return self.confidence >= MIN_FINDING_CONFIDENCE

    def to_dict(self) -> dict:
        return {
            'concept_id'        : self.concept_id,
            'aggregate_value'   : round(self.aggregate_value, 4),
            'band'               : self.band.value,
            'confidence'         : self.confidence,
            'reconstructable'    : self.reconstructable,
            'dependency_health'  : self.dependency_health,
            'resolved_fields'    : self.resolved_fields,
            'missing_fields'     : self.missing_fields,
        }


class Severity(str, Enum):
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class BusinessFinding:
    """One fired business rule — see Part 2 for the rule catalogue."""
    finding_id: str
    title: str
    severity: Severity
    confidence: float                      # min() of supporting concepts' confidence
    supporting_concepts: list[str]
    explanation: str
    recommendation: str

    def to_dict(self) -> dict:
        return {
            'finding_id'          : self.finding_id,
            'title'                : self.title,
            'severity'             : self.severity.value,
            'confidence'           : round(self.confidence, 4),
            'supporting_concepts'  : self.supporting_concepts,
            'explanation'          : self.explanation,
            'recommendation'       : self.recommendation,
        }


@dataclass
class ReasoningSummary:
    """Part 5 — dataset-level roll-up. Diagnostics only."""
    overall_business_health: str            # LOW | MEDIUM | HIGH
    overall_customer_risk: str               # LOW | MEDIUM | HIGH | CRITICAL
    business_strengths: list[str] = field(default_factory=list)
    business_weaknesses: list[str] = field(default_factory=list)
    dominant_failure_reason: str | None = None
    dominant_positive_signal: str | None = None

    def to_dict(self) -> dict:
        return {
            'overall_business_health'   : self.overall_business_health,
            'overall_customer_risk'      : self.overall_customer_risk,
            'business_strengths'         : self.business_strengths,
            'business_weaknesses'        : self.business_weaknesses,
            'dominant_failure_reason'    : self.dominant_failure_reason,
            'dominant_positive_signal'   : self.dominant_positive_signal,
        }


@dataclass
class ReasoningReport:
    """
    The full output of one BusinessReasoningEngine.analyze() call.
    Purely informational — see module docstring, "Non-interference
    guarantee". Nothing in the prediction path reads this object.
    """
    sector: str
    generated_at: str
    inferences: dict[str, BusinessInference] = field(default_factory=dict)
    findings: list[BusinessFinding] = field(default_factory=list)
    summary: ReasoningSummary | None = None

    def to_dict(self) -> dict:
        return {
            'sector'        : self.sector,
            'generated_at'  : self.generated_at,
            'inferences'    : {k: v.to_dict() for k, v in self.inferences.items()},
            'findings'      : [f.to_dict() for f in self.findings],
            'summary'       : self.summary.to_dict() if self.summary else None,
        }


# ══════════════════════════════════════════════════════════════════
# PART 2 — BUSINESS RULES (deterministic, documented)
# ══════════════════════════════════════════════════════════════════
# Every rule is a plain function: (inferences: dict[str, BusinessInference])
# -> BusinessFinding | None. A rule fires only when:
#   1. every concept it reasons about resolved to an inference at all
#      (some concepts may be entirely absent from `inferences` if they
#      are not in CONCEPT_NAMES — defensive, should not happen), AND
#   2. every concept it reasons about has_sufficient_evidence (its
#      graph reconstruction confidence clears MIN_FINDING_CONFIDENCE),
#      AND
#   3. every concept's band matches this rule's triggering condition.
# Rules never fire on a concept the graph could not reconstruct with
# at least minimal confidence — an unreconstructable LOW is not
# evidence of anything, it's an absence of evidence, and treating it
# as a genuine LOW risks manufacturing findings out of missing data.

RuleFn = Callable[[dict[str, "BusinessInference"]], "BusinessFinding | None"]


def _ready(inferences: dict[str, BusinessInference], *concept_ids: str) -> bool:
    """True iff every named concept is present and has sufficient evidence."""
    for cid in concept_ids:
        inf = inferences.get(cid)
        if inf is None or not inf.has_sufficient_evidence:
            return False
    return True


def rule_retention_risk(inferences: dict[str, BusinessInference]) -> BusinessFinding | None:
    """
    Rule: RECURRING_COMMITMENT LOW + SUPPORT_FRICTION HIGH -> Retention Risk HIGH

    Rationale: a customer paying little (or, for sectors where the
    concept is a reward rather than a cost, receiving little value)
    AND generating a lot of support friction has both a weak financial
    tether to the business and an active source of dissatisfaction —
    the combination the churn literature treats as the clearest
    voluntary-churn precursor of the concepts available here.
    """
    if not _ready(inferences, "RECURRING_COMMITMENT", "SUPPORT_FRICTION"):
        return None
    commitment = inferences["RECURRING_COMMITMENT"]
    friction = inferences["SUPPORT_FRICTION"]
    if commitment.band != ConceptBand.LOW or friction.band != ConceptBand.HIGH:
        return None
    conf = min(commitment.confidence, friction.confidence)
    return BusinessFinding(
        finding_id="RETENTION_RISK",
        title="Retention Risk",
        severity=Severity.HIGH,
        confidence=conf,
        supporting_concepts=["RECURRING_COMMITMENT", "SUPPORT_FRICTION"],
        explanation=(
            "Recurring commitment is weak while support friction is high — "
            "customers have little financial tie to the business and an "
            "active, unresolved source of dissatisfaction."
        ),
        recommendation="Launch a targeted retention campaign for the affected segment.",
    )


def rule_retention_strength(inferences: dict[str, BusinessInference]) -> BusinessFinding | None:
    """
    Rule: CUSTOMER_LOYALTY HIGH + ENGAGEMENT_LEVEL HIGH -> Retention Strength HIGH

    Rationale: a long, committed relationship combined with active,
    frequent usage is the strongest available signal that a segment is
    entrenched rather than merely inertial.
    """
    if not _ready(inferences, "CUSTOMER_LOYALTY", "ENGAGEMENT_LEVEL"):
        return None
    loyalty = inferences["CUSTOMER_LOYALTY"]
    engagement = inferences["ENGAGEMENT_LEVEL"]
    if loyalty.band != ConceptBand.HIGH or engagement.band != ConceptBand.HIGH:
        return None
    conf = min(loyalty.confidence, engagement.confidence)
    return BusinessFinding(
        finding_id="RETENTION_STRENGTH",
        title="Retention Strength",
        severity=Severity.LOW,
        confidence=conf,
        supporting_concepts=["CUSTOMER_LOYALTY", "ENGAGEMENT_LEVEL"],
        explanation=(
            "Customer loyalty and engagement are both high — the "
            "relationship is entrenched, not merely long-standing."
        ),
        recommendation="Protect this segment's experience; consider it a reference base for loyalty programs.",
    )


def rule_dormant_customer(inferences: dict[str, BusinessInference]) -> BusinessFinding | None:
    """
    Rule: RECURRING_COMMITMENT HIGH + ENGAGEMENT_LEVEL LOW -> Dormant Customer

    Rationale: a customer still financially committed (still paying /
    still holding value) but no longer actively engaging is a classic
    dormancy pattern — the relationship hasn't ended, but it has gone
    quiet, which often precedes non-renewal.
    """
    if not _ready(inferences, "RECURRING_COMMITMENT", "ENGAGEMENT_LEVEL"):
        return None
    commitment = inferences["RECURRING_COMMITMENT"]
    engagement = inferences["ENGAGEMENT_LEVEL"]
    if commitment.band != ConceptBand.HIGH or engagement.band != ConceptBand.LOW:
        return None
    conf = min(commitment.confidence, engagement.confidence)
    return BusinessFinding(
        finding_id="DORMANT_CUSTOMER",
        title="Customer Dormancy",
        severity=Severity.MEDIUM,
        confidence=conf,
        supporting_concepts=["RECURRING_COMMITMENT", "ENGAGEMENT_LEVEL"],
        explanation=(
            "Recurring commitment remains high but engagement has dropped — "
            "the relationship is financially intact but has gone quiet."
        ),
        recommendation="Enroll the segment in a re-engagement program before the next renewal cycle.",
    )


def rule_service_recovery_needed(inferences: dict[str, BusinessInference]) -> BusinessFinding | None:
    """
    Rule: SUPPORT_FRICTION HIGH + SATISFACTION_SIGNAL LOW -> Service Recovery Needed

    Rationale: high complaint/support volume combined with low
    satisfaction is a direct, first-party signal that the service
    experience itself — not just price or usage — is the churn driver.
    """
    if not _ready(inferences, "SUPPORT_FRICTION", "SATISFACTION_SIGNAL"):
        return None
    friction = inferences["SUPPORT_FRICTION"]
    satisfaction = inferences["SATISFACTION_SIGNAL"]
    if friction.band != ConceptBand.HIGH or satisfaction.band != ConceptBand.LOW:
        return None
    conf = min(friction.confidence, satisfaction.confidence)
    return BusinessFinding(
        finding_id="SERVICE_RECOVERY_NEEDED",
        title="Service Recovery Needed",
        severity=Severity.HIGH,
        confidence=conf,
        supporting_concepts=["SUPPORT_FRICTION", "SATISFACTION_SIGNAL"],
        explanation=(
            "Support friction is high and satisfaction is low at the same "
            "time — the service experience itself is the likely churn driver."
        ),
        recommendation="Trigger a service-recovery workflow (proactive outreach, issue audit) for the affected segment.",
    )


# The registry every BusinessReasoningEngine instance evaluates, in
# this fixed order. Add a new rule by writing a RuleFn (documented,
# per Part 2) and appending it here — nothing else needs to change.
DEFAULT_RULES: list[RuleFn] = [
    rule_retention_risk,
    rule_retention_strength,
    rule_dormant_customer,
    rule_service_recovery_needed,
]


# ══════════════════════════════════════════════════════════════════
# PART 3 — THE ENGINE
# ══════════════════════════════════════════════════════════════════

class BusinessReasoningEngine:
    """
    Consumes a BusinessConceptGraph (+ the existing per-row concept
    value computation) and produces a ReasoningReport. Stateless aside
    from its rule registry — safe to reuse across many analyze() calls.
    """

    def __init__(self, rules: list[RuleFn] | None = None) -> None:
        self.rules: list[RuleFn] = list(rules) if rules is not None else list(DEFAULT_RULES)

    # ── building inferences ─────────────────────────────────────

    def _build_inferences(
        self,
        graph: BusinessConceptGraph,
        concept_df: pd.DataFrame,
    ) -> dict[str, BusinessInference]:
        inferences: dict[str, BusinessInference] = {}
        for concept_id in CONCEPT_NAMES:
            node = graph.get_node(concept_id)
            if node is None:
                continue
            aggregate_value = (
                float(concept_df[concept_id].mean())
                if concept_id in concept_df.columns and len(concept_df) > 0
                else 0.5
            )
            inferences[concept_id] = BusinessInference(
                concept_id=concept_id,
                aggregate_value=aggregate_value,
                band=_band_for(aggregate_value),
                confidence=node.confidence,
                reconstructable=node.confidence > 0.0,
                dependency_health=node.dependency_health(),
                resolved_fields=list(node.resolved_fields),
                missing_fields=list(node.missing_fields),
            )
        return inferences

    # ── evaluating rules ─────────────────────────────────────────

    def _evaluate_rules(
        self, inferences: dict[str, BusinessInference],
    ) -> list[BusinessFinding]:
        findings: list[BusinessFinding] = []
        for rule in self.rules:
            finding = rule(inferences)
            if finding is not None:
                findings.append(finding)
        return findings

    # ── summarizing (Part 5) ────────────────────────────────────

    def _summarize(
        self,
        inferences: dict[str, BusinessInference],
        findings: list[BusinessFinding],
    ) -> ReasoningSummary:
        # Business health: mean of "high is good" concepts (inverted
        # for "high is bad" ones), restricted to concepts with
        # sufficient evidence. Neutral concepts (e.g. RECURRING_
        # COMMITMENT) do not participate — they measure size, not
        # health.
        health_scores: list[float] = []
        strengths: list[str] = []
        weaknesses: list[str] = []
        best_positive: tuple[str, float] | None = None

        for concept_id, direction in CONCEPT_DIRECTION.items():
            inf = inferences.get(concept_id)
            if inf is None or not inf.has_sufficient_evidence or direction == Direction.NEUTRAL:
                continue
            oriented_value = (
                inf.aggregate_value if direction == Direction.HIGH_IS_GOOD
                else 1.0 - inf.aggregate_value
            )
            health_scores.append(oriented_value)

            is_strength = (
                (direction == Direction.HIGH_IS_GOOD and inf.band == ConceptBand.HIGH) or
                (direction == Direction.HIGH_IS_BAD and inf.band == ConceptBand.LOW)
            )
            is_weakness = (
                (direction == Direction.HIGH_IS_GOOD and inf.band == ConceptBand.LOW) or
                (direction == Direction.HIGH_IS_BAD and inf.band == ConceptBand.HIGH)
            )
            if is_strength:
                strengths.append(concept_id)
                if best_positive is None or oriented_value > best_positive[1]:
                    best_positive = (concept_id, oriented_value)
            elif is_weakness:
                weaknesses.append(concept_id)

        overall_health_value = sum(health_scores) / len(health_scores) if health_scores else 0.5
        overall_business_health = _band_for(overall_health_value).value

        # Customer risk: driven by the worst fired finding's severity,
        # not by concept values directly — findings already encode the
        # cross-concept reasoning the summary should defer to.
        severity_rank = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2, Severity.CRITICAL: 3}
        if findings:
            worst = max(findings, key=lambda f: severity_rank[f.severity])
            overall_customer_risk = worst.severity.value
            dominant_failure_reason = worst.explanation
        else:
            overall_customer_risk = "LOW"
            dominant_failure_reason = None

        dominant_positive_signal = (
            f"{best_positive[0]} ({ConceptBand.HIGH.value if inferences[best_positive[0]].band == ConceptBand.HIGH else inferences[best_positive[0]].band.value})"
            if best_positive is not None else None
        )

        return ReasoningSummary(
            overall_business_health=overall_business_health,
            overall_customer_risk=overall_customer_risk,
            business_strengths=strengths,
            business_weaknesses=weaknesses,
            dominant_failure_reason=dominant_failure_reason,
            dominant_positive_signal=dominant_positive_signal,
        )

    # ── public entry points ─────────────────────────────────────

    def analyze_from_graph(
        self,
        graph: BusinessConceptGraph,
        concept_df: pd.DataFrame,
        sector: str,
    ) -> ReasoningReport:
        """
        Reason over an already-computed BusinessConceptGraph + concept
        value table — the seam a future caller (e.g. a batch job that
        already computed both for other reasons) can use to avoid
        recomputation. Never called from the prediction path today.
        """
        inferences = self._build_inferences(graph, concept_df)
        findings = self._evaluate_rules(inferences)
        summary = self._summarize(inferences, findings)
        return ReasoningReport(
            sector=sector,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            inferences=inferences,
            findings=findings,
            summary=summary,
        )

    def analyze(self, df_input: pd.DataFrame, sector: str) -> ReasoningReport:
        """
        One-shot entry point: raw input DataFrame + sector -> full
        ReasoningReport. Internally calls the existing, unmodified
        resolve_schema() / compute_concept_values() / graph
        propagation — this method adds no new schema or feature logic
        of its own.
        """
        canonical_df, _resolutions = resolve_schema(df_input)
        deduped = canonical_df.loc[:, ~canonical_df.columns.duplicated(keep="first")]
        concept_df, _confidence = compute_concept_values(deduped, sector)
        graph = resolve_graph_confidence(df_input, sector)
        return self.analyze_from_graph(graph, concept_df, sector)


def run_business_reasoning(df_input: pd.DataFrame, sector: str) -> ReasoningReport:
    """Module-level convenience wrapper around a default-configured engine."""
    return BusinessReasoningEngine().analyze(df_input, sector)
