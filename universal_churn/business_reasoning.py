"""
universal_churn/business_reasoning.py
══════════════════════════════════════════════════════════════════════
Business Reasoning Engine — Version 7, Chunk 3 (rule evaluation),
Chunk 4 (Knowledge-Base-driven).

Consumes a BusinessConceptGraph (business_concept_graph.py) plus the
existing per-row concept value computation (business_concepts.py) and
produces a ReasoningReport: per-concept inferences (aggregate value +
band + confidence) and a list of fired BusinessFindings, each backed
by a rule from the Knowledge Base (knowledge/rules.yaml).

Non-interference guarantee (unchanged from Chunk 3/4)
--------------------------------------------------------
Nothing on the prediction path (routing.py, coverage.py, quality_gate.py,
sector_pipeline.py, universal_pipeline.py) imports this module. It is
read-only with respect to business_concepts.py, business_concept_graph.py,
and schema_resolution.py — it calls their existing public functions and
adds no new schema/feature logic of its own.

Version 7, Chunk 4 — Knowledge Base externalization
------------------------------------------------------
Concept direction/band thresholds, rule trigger conditions, finding
titles/severities/explanations, and recommendation text live in
knowledge/*.yaml, loaded and validated by
knowledge_loader.load_knowledge_base() into a typed
knowledge_base.KnowledgeBase (see BUSINESS_INTELLIGENCE.md).

Version 8, Chunk 1 — Business Intelligence Expansion
--------------------------------------------------------
This chunk is a Knowledge Base *content* expansion (many more
sector-aware rules/findings/recommendations — see knowledge/rules.yaml),
plus the minimal engine changes needed to make that content useful:

    1. BUG FIX: the previous revision of this module built
       `_RULES_BY_ID` (and the `rule_retention_risk` etc. aliases)
       dynamically from the Knowledge Base, but then immediately
       REDEFINED `rule_retention_risk` / `rule_retention_strength` /
       `rule_dormant_customer` / `rule_service_recovery_needed` as
       hardcoded literal functions further down the file, and rebuilt
       `DEFAULT_RULES` from those hardcoded functions instead of the
       Knowledge Base. That meant every rule added to rules.yaml
       beyond the original four was silently invisible to
       BusinessReasoningEngine — the exact opposite of what this
       expansion needs. The duplicate `_ready()` / rule_* definitions
       and the duplicate `DEFAULT_RULES` assignment are removed below;
       there is now exactly one source of rule behaviour (the
       Knowledge Base) and `DEFAULT_RULES` covers every rule in
       rules.yaml, not just four.
    2. Rule priority (Part 4): each fired BusinessFinding now carries
       the priority of the rule that produced it, and
       `_evaluate_rules()` sorts fired findings by priority descending
       (Python's sort is stable, so ties keep rules.yaml declaration
       order).
    3. Sector scoping (Part 1 / Part 9 "sector filtering"): a rule
       whose `sectors` tuple is non-empty is only evaluated when
       `sector` is one of the listed values. Sector metadata is
       attached to each generated rule closure as `fn.rule_meta`
       (a `RuleKnowledge`) rather than changing any function
       signature — `RuleFn` is still `Callable[[dict], BusinessFinding
       | None]`, so `BusinessReasoningEngine(rules=[...])` callers that
       pass a custom list of plain functions keep working.
    4. Richer BusinessFinding fields (Part 6/8): `category`,
       `priority`, `recommendation_priority`, `business_impact`, and
       `expected_outcome` are now populated on every finding, sourced
       entirely from the Knowledge Base (no new computation).

PUBLIC API is otherwise UNCHANGED: every name this module exported
before this chunk — ConceptBand, Direction, CONCEPT_DIRECTION,
LOW_BAND_MAX, HIGH_BAND_MIN, MIN_FINDING_CONFIDENCE, BusinessInference,
Severity, BusinessFinding, ReasoningSummary, ReasoningReport,
rule_retention_risk, rule_retention_strength, rule_dormant_customer,
rule_service_recovery_needed, DEFAULT_RULES, BusinessReasoningEngine,
run_business_reasoning — still exists and behaves the same for
existing callers (prediction_explanation.py reads only
f.title/f.severity/f.confidence/f.explanation/f.recommendation, all of
which are unchanged; the new fields are additive).
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
from .knowledge_base import KnowledgeBase, RuleKnowledge
from .knowledge_loader import get_default_knowledge_base

# ══════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE — loaded once at import time (fail-fast)
# ══════════════════════════════════════════════════════════════════
# A broken knowledge/ directory (missing file, malformed YAML,
# duplicate ID, dangling cross-reference) raises
# KnowledgeValidationError HERE, at import time — not silently at
# prediction time. Nothing on the prediction path imports this
# module (see module docstring's "Non-interference guarantee"), so
# this cannot break routing/prediction even if it were ever wired in
# later; today it only affects code that explicitly imports
# business_reasoning.

KNOWLEDGE_BASE: KnowledgeBase = get_default_knowledge_base()

# ══════════════════════════════════════════════════════════════════
# CONFIGURATION — sourced from the Knowledge Base
# ══════════════════════════════════════════════════════════════════

LOW_BAND_MAX  = KNOWLEDGE_BASE.band_thresholds.low_max
HIGH_BAND_MIN = KNOWLEDGE_BASE.band_thresholds.high_min

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
    HIGH_IS_GOOD = "high_is_good"
    HIGH_IS_BAD  = "high_is_bad"
    NEUTRAL      = "neutral"

CONCEPT_DIRECTION: dict[str, Direction] = {
    concept_id: Direction(KNOWLEDGE_BASE.concept_direction(concept_id))
    for concept_id in KNOWLEDGE_BASE.concept_ids()
}

# Unchanged — reuses concept_confidence.py's existing reconstructability
# floor rather than inventing a second, competing threshold. This is a
# schema-reconstruction concern (concept_confidence.py's domain), not
# business knowledge, so it deliberately does NOT move into the KB.
MIN_FINDING_CONFIDENCE = MIN_RECONSTRUCTABLE_OVERALL_CONFIDENCE

# ══════════════════════════════════════════════════════════════════
# PART 1 — DATACLASSES
# ══════════════════════════════════════════════════════════════════

@dataclass
class BusinessInference:
    concept_id: str
    aggregate_value: float
    band: ConceptBand
    confidence: float
    reconstructable: bool
    dependency_health: str
    resolved_fields: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)

    @property
    def has_sufficient_evidence(self) -> bool:
        return self.confidence >= MIN_FINDING_CONFIDENCE

    def to_dict(self) -> dict:
        return {
            'concept_id': self.concept_id,
            'aggregate_value': round(self.aggregate_value, 4),
            'band': self.band.value,
            'confidence': self.confidence,
            'reconstructable': self.reconstructable,
            'dependency_health': self.dependency_health,
            'resolved_fields': self.resolved_fields,
            'missing_fields': self.missing_fields,
        }

class Severity(str, Enum):
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"

@dataclass
class BusinessFinding:
    finding_id: str
    title: str
    severity: Severity
    confidence: float
    supporting_concepts: list[str]
    explanation: str
    recommendation: str
    # ── Version 8, Chunk 1 additions (Parts 4-6-8) — additive only,
    # every pre-existing field above is untouched. ──────────────────
    category: str = "Uncategorized"
    priority: int = 50                       # rule priority — used for sort order
    recommendation_priority: str = "MEDIUM"   # action urgency (LOW/MEDIUM/HIGH/CRITICAL)
    business_impact: str = ""
    expected_outcome: str = ""

    def to_dict(self) -> dict:
        return {
            'finding_id': self.finding_id, 'title': self.title,
            'severity': self.severity.value, 'confidence': round(self.confidence, 4),
            'supporting_concepts': self.supporting_concepts,
            'explanation': self.explanation, 'recommendation': self.recommendation,
            'category': self.category, 'priority': self.priority,
            'recommendation_priority': self.recommendation_priority,
            'business_impact': self.business_impact,
            'expected_outcome': self.expected_outcome,
        }

@dataclass
class ReasoningSummary:
    overall_business_health: str
    overall_customer_risk: str
    business_strengths: list[str] = field(default_factory=list)
    business_weaknesses: list[str] = field(default_factory=list)
    dominant_failure_reason: str | None = None
    dominant_positive_signal: str | None = None

    def to_dict(self) -> dict:
        return {
            'overall_business_health': self.overall_business_health,
            'overall_customer_risk': self.overall_customer_risk,
            'business_strengths': self.business_strengths,
            'business_weaknesses': self.business_weaknesses,
            'dominant_failure_reason': self.dominant_failure_reason,
            'dominant_positive_signal': self.dominant_positive_signal,
        }

@dataclass
class ReasoningReport:
    sector: str
    generated_at: str
    inferences: dict[str, BusinessInference] = field(default_factory=dict)
    findings: list[BusinessFinding] = field(default_factory=list)
    summary: ReasoningSummary | None = None

    def to_dict(self) -> dict:
        return {
            'sector': self.sector, 'generated_at': self.generated_at,
            'inferences': {k: v.to_dict() for k, v in self.inferences.items()},
            'findings': [f.to_dict() for f in self.findings],
            'summary': self.summary.to_dict() if self.summary else None,
        }

# ══════════════════════════════════════════════════════════════════
# PART 2 — RULES, BUILT FROM THE KNOWLEDGE BASE
# ══════════════════════════════════════════════════════════════════
# A rule fires only when every concept it reasons about (1) has an
# inference at all, (2) has_sufficient_evidence, and (3) matches this
# rule's declared band conditions. `RuleFn` signature is unchanged —
# sector scoping is attached out-of-band via `fn.rule_meta` (see
# `_evaluate_rules()` below) so this is not a breaking type change.

RuleFn = Callable[[dict[str, "BusinessInference"]], "BusinessFinding | None"]

def _ready(inferences: dict[str, BusinessInference], *concept_ids: str) -> bool:
    for cid in concept_ids:
        inf = inferences.get(cid)
        if inf is None or not inf.has_sufficient_evidence:
            return False
    return True

def _make_rule_fn(rule: RuleKnowledge, kb: KnowledgeBase) -> RuleFn:
    """Build one RuleFn from a KnowledgeBase RuleKnowledge entry."""
    finding = kb.get_finding(rule.finding_id)
    recommendation = kb.get_recommendation_details(rule.finding_id)
    recommendation_text = recommendation.text if recommendation else ""
    severity = Severity(finding.severity)

    def _rule_fn(inferences: dict[str, BusinessInference]) -> BusinessFinding | None:
        if not _ready(inferences, *rule.supporting_concepts):
            return None
        for condition in rule.conditions:
            inf = inferences.get(condition.concept)
            if inf is None or inf.band.value != condition.band:
                return None
        conf = min(inferences[cid].confidence for cid in rule.supporting_concepts)
        return BusinessFinding(
            finding_id=rule.finding_id,
            title=finding.title,
            severity=severity,
            confidence=conf,
            supporting_concepts=list(rule.supporting_concepts),
            explanation=finding.explanation,
            recommendation=recommendation_text,
            category=finding.category,
            priority=rule.priority,
            recommendation_priority=recommendation.priority if recommendation else "MEDIUM",
            business_impact=recommendation.business_impact if recommendation else "",
            expected_outcome=recommendation.expected_outcome if recommendation else "",
        )

    _rule_fn.__name__ = f"rule_{rule.rule_id.lower()}"
    _rule_fn.__doc__ = (
        f"Knowledge-Base-driven rule '{rule.rule_id}' -> finding "
        f"'{rule.finding_id}'. Conditions: "
        f"{[(c.concept, c.band) for c in rule.conditions]}. "
        f"Priority={rule.priority}. Sectors="
        f"{list(rule.sectors) if rule.sectors else 'ALL'}."
    )
    # Out-of-band metadata (Version 8, Chunk 1) — does not change the
    # RuleFn call signature, so existing callers that only ever call
    # `fn(inferences)` are unaffected. Used by _evaluate_rules() below
    # for sector scoping and priority sorting.
    _rule_fn.rule_meta = rule  # type: ignore[attr-defined]
    return _rule_fn

_RULES_BY_ID: dict[str, RuleFn] = {
    rule.rule_id: _make_rule_fn(rule, KNOWLEDGE_BASE) for rule in KNOWLEDGE_BASE.rules
}

# ── Named exports (backward compatibility with Chunk 3 call sites) ──
# Kept as aliases into the Knowledge-Base-driven rule map so
# `from business_reasoning import rule_retention_risk` etc. keeps
# working unchanged. If a rule id is ever renamed/removed in
# rules.yaml, this raises a clear KeyError at import time rather than
# silently dropping a rule other code still expects.
rule_retention_risk           = _RULES_BY_ID["RETENTION_RISK"]
rule_retention_strength       = _RULES_BY_ID["RETENTION_STRENGTH"]
rule_dormant_customer         = _RULES_BY_ID["DORMANT_CUSTOMER"]
rule_service_recovery_needed  = _RULES_BY_ID["SERVICE_RECOVERY_NEEDED"]

# The registry every BusinessReasoningEngine instance evaluates by
# default. Version 8, Chunk 1: this is now every rule in the Knowledge
# Base (34 as of this chunk — 11 cross-sector + 6 telecom + 6
# healthcare + 5 banking + 6 e-commerce), not just the four named
# aliases above. This is the fix for the shadowing bug described in
# the module docstring: there is exactly one place DEFAULT_RULES is
# assigned, and it is derived entirely from the Knowledge Base.
DEFAULT_RULES: list[RuleFn] = [
    _RULES_BY_ID[rule.rule_id] for rule in KNOWLEDGE_BASE.rules
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
        self, inferences: dict[str, BusinessInference], sector: str,
    ) -> list[BusinessFinding]:
        """
        Run every eligible rule and return fired findings sorted by
        priority descending (Version 8, Chunk 1 — Part 4). A rule
        carrying `rule_meta.sectors` is skipped when `sector` is not
        in that list (Part 1 / Part 9 "sector filtering"); rules with
        no `rule_meta` at all (a caller-supplied plain function with
        no attached metadata) are always eligible, since there is
        nothing to filter on.

        Python's list.sort() is stable, so findings whose rules share
        the same priority retain the order they were evaluated in —
        which is rules.yaml declaration order, since `self.rules`
        defaults to `DEFAULT_RULES` — satisfying "Rules with equal
        priority retain deterministic ordering" (Part 4).
        """
        findings: list[BusinessFinding] = []
        for rule_fn in self.rules:
            meta: RuleKnowledge | None = getattr(rule_fn, 'rule_meta', None)
            if meta is not None and not meta.applies_to_sector(sector):
                continue
            finding = rule_fn(inferences)
            if finding is not None:
                findings.append(finding)
        findings.sort(key=lambda f: -f.priority)
        return findings

    # ── summarizing (Part 5, Chunk 3) ───────────────────────────

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
        # cross-concept reasoning the summary should defer to. Findings
        # are already priority-sorted by _evaluate_rules(), but risk is
        # still determined by SEVERITY (not priority) since those are
        # deliberately independent axes (see Part 4/Part 5 docs).
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
        findings = self._evaluate_rules(inferences, sector)
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
