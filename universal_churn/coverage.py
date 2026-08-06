# coverage.py
"""Coverage Intelligence

Evaluates dataset coverage based on previous UCIF layers.
Implements deterministic scoring without external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Dict, Set, Any

from .business_meaning import BusinessMeaning
from .context_validation import ContextValidation
from .semantic_graph import (
    SemanticKnowledgeGraph,
    GraphNode,
    BusinessEntity,
)
from .canonical_mapping import CanonicalMappingResult, CanonicalMapping

# ---------------------------------------------------------------------------
# Immutable dataclasses – public contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CoverageMetric:
    """A single coverage metric.

    Attributes
    ----------
    name: str – metric identifier (e.g., "concept_coverage").
    score: float – normalized score in [0, 1].
    reasoning: str – deterministic explanation of the score.
    """

    name: str
    score: float
    reasoning: str


@dataclass(frozen=True)
class CoverageIssue:
    """A detected quality issue.

    Attributes
    ----------
    issue_type: str – e.g., "duplicate_mapping".
    severity: str – one of "LOW", "MEDIUM", "HIGH", "INFO".
    affected_items: Tuple[str, ...] – identifiers of items concerned.
    reason: str – deterministic description of why it is an issue.
    recommendation: str – suggested remediation.
    """

    issue_type: str
    severity: str
    affected_items: Tuple[str, ...]
    reason: str
    recommendation: str


@dataclass(frozen=True)
class CoverageSummary:
    """Aggregated coverage scores and readiness level."""

    concept_coverage: float
    entity_coverage: float
    semantic_coverage: float
    confidence_coverage: float
    stability_coverage: float
    overall_coverage: float
    readiness: str


@dataclass(frozen=True)
class CoverageAssessment:
    """Detailed assessment – metrics and issues."""

    metrics: Tuple[CoverageMetric, ...]
    issues: Tuple[CoverageIssue, ...]


@dataclass(frozen=True)
class CoverageResult:
    """Full result returned by ``infer_coverage``."""

    summary: CoverageSummary
    assessment: CoverageAssessment

# ---------------------------------------------------------------------------
# Helper utilities – deterministic only
# ---------------------------------------------------------------------------

# Component weights (sum = 0.90). Penalty weight = 0.10.
_WEIGHT_CONCEPT = 0.25
_WEIGHT_ENTITY = 0.20
_WEIGHT_SEMANTIC = 0.25
_WEIGHT_CONFIDENCE = 0.20
_WEIGHT_PENALTY = 0.10
_TOTAL_WEIGHT = (
    _WEIGHT_CONCEPT + _WEIGHT_ENTITY + _WEIGHT_SEMANTIC + _WEIGHT_CONFIDENCE + _WEIGHT_PENALTY
)

# Severity weight mapping – used for penalty calculation.
_SEVERITY_WEIGHTS: Dict[str, float] = {
    "INFO": 0.0,
    "LOW": 0.1,
    "MEDIUM": 0.3,
    "HIGH": 0.6,
}

# ---------------------------------------------------------------------------
# Concept coverage
# ---------------------------------------------------------------------------

def _concept_coverage(
    bms: List[BusinessMeaning], cm: CanonicalMappingResult
) -> Tuple[float, List[CoverageIssue], CoverageMetric]:
    total = len(bms)
    mapped = sum(1 for m in cm.mappings if m.confidence > 0.0)
    unmapped = total - mapped
    dup_counts: Dict[str, int] = {}
    for m in cm.mappings:
        dup_counts[m.chosen_concept.name] = dup_counts.get(m.chosen_concept.name, 0) + 1
    duplicate = sum(1 for c, cnt in dup_counts.items() if cnt > 1)
    conflict = 0
    conflict_items: List[str] = []
    if duplicate:
        def infer_entity(bm: BusinessMeaning) -> str:
            lowered = bm.primary_business_concept.lower()
            for kw, ent in [
                ("customer", "Customer"),
                ("policy", "Policy"),
                ("claim", "Claim"),
                ("subscription", "Subscription"),
                ("account", "Account"),
                ("invoice", "Invoice"),
                ("contract", "Contract"),
            ]:
                if kw in lowered:
                    return ent
            return "Other"
        entity_map: Dict[str, Set[str]] = {}
        for bm, mapping in zip(bms, cm.mappings):
            ent = infer_entity(bm)
            entity_map.setdefault(mapping.chosen_concept.name, set()).add(ent)
        for canon, ents in entity_map.items():
            if len(ents) > 1:
                conflict += 1
                conflict_items.append(canon)
    concept_score = mapped / total if total else 0.0
    reasoning = (
        f"{mapped}/{total} concepts mapped ({concept_score:.2f}); "
        f"{duplicate} duplicate, {conflict} conflicting."
    )
    metric = CoverageMetric(name="concept_coverage", score=concept_score, reasoning=reasoning)
    issues: List[CoverageIssue] = []
    if unmapped:
        issues.append(
            CoverageIssue(
                issue_type="unmapped_concepts",
                severity="MEDIUM",
                affected_items=tuple(bm.primary_business_concept for bm, m in zip(bms, cm.mappings) if m.confidence == 0.0),
                reason="Concepts without a confident canonical mapping.",
                recommendation="Review ambiguous columns or enrich vocabulary.",
            )
        )
    if duplicate:
        issues.append(
            CoverageIssue(
                issue_type="duplicate_mappings",
                severity="LOW",
                affected_items=tuple(c for c, cnt in dup_counts.items() if cnt > 1),
                reason="Same canonical concept used for multiple columns.",
                recommendation="Ensure distinct concepts where appropriate.",
            )
        )
    if conflict:
        issues.append(
            CoverageIssue(
                issue_type="conflicting_mappings",
                severity="HIGH",
                affected_items=tuple(conflict_items),
                reason="Duplicate canonical concept maps to different inferred entities.",
                recommendation="Disambiguate by refining BusinessMeaning definitions.",
            )
        )
    return concept_score, issues, metric

# ---------------------------------------------------------------------------
# Entity coverage
# ---------------------------------------------------------------------------

def _entity_coverage(graph: SemanticKnowledgeGraph) -> Tuple[float, List[CoverageIssue], CoverageMetric]:
    total_entities = len(graph.entities)
    if total_entities == 0:
        return 0.0, [], CoverageMetric(name="entity_coverage", score=0.0, reasoning="No entities present.")
    node_to_entity: Dict[int, BusinessEntity] = {}
    for ent in graph.entities:
        for nid in ent.node_ids:
            node_to_entity[nid] = ent
    participating_entities: Set[BusinessEntity] = set()
    for e in graph.edges:
        src_ent = node_to_entity.get(e.source_id)
        tgt_ent = node_to_entity.get(e.target_id)
        if src_ent:
            participating_entities.add(src_ent)
        if tgt_ent:
            participating_entities.add(tgt_ent)
    participating = len(participating_entities)
    isolated = total_entities - participating
    entity_score = participating / total_entities
    reasoning = (
        f"{participating}/{total_entities} entities have relationships ({entity_score:.2f}); "
        f"{isolated} isolated."
    )
    metric = CoverageMetric(name="entity_coverage", score=entity_score, reasoning=reasoning)
    issues: List[CoverageIssue] = []
    if isolated:
        issues.append(
            CoverageIssue(
                issue_type="isolated_entities",
                severity="MEDIUM",
                affected_items=tuple(ent.entity_type for ent in graph.entities if ent not in participating_entities),
                reason="Entities without any graph edges.",
                recommendation="Inspect entity definitions or add missing relationships.",
            )
        )
    return entity_score, issues, metric

# ---------------------------------------------------------------------------
# Semantic coverage
# ---------------------------------------------------------------------------

def _dependency_coverage(graph: SemanticKnowledgeGraph) -> float:
    """Structural dependency coverage.

    Ratio of actual edges to the maximum possible undirected edges between nodes.
    """
    n = graph.node_count
    if n <= 1:
        return 1.0
    max_possible = n * (n - 1) / 2
    return graph.edge_count / max_possible


def _semantic_coverage(graph: SemanticKnowledgeGraph) -> Tuple[float, List[CoverageIssue], CoverageMetric]:
    max_components = max(1, graph.connected_components)
    connectivity_score = 1.0 - (graph.connected_components - 1) / max_components
    nodes_in_clusters = set()
    for cl in graph.clusters:
        nodes_in_clusters.update(cl.node_ids)
    cluster_participation = len(nodes_in_clusters) / graph.node_count if graph.node_count else 0.0
    dependency_score = _dependency_coverage(graph)
    consistency_score = graph.consistency_score
    semantic_score = (connectivity_score + cluster_participation + dependency_score + consistency_score) / 4.0
    reasoning = (
        f"Conn={connectivity_score:.2f}, ClustPart={cluster_participation:.2f}, Dep={dependency_score:.2f}, Cons={consistency_score:.2f} => {semantic_score:.2f}"
    )
    metric = CoverageMetric(name="semantic_coverage", score=semantic_score, reasoning=reasoning)
    issues: List[CoverageIssue] = []
    if graph.connected_components > 1:
        issues.append(
            CoverageIssue(
                issue_type="disconnected_graph",
                severity="LOW",
                affected_items=tuple(),
                reason="Graph has multiple connected components.",
                recommendation="Consider adding missing semantic edges.",
            )
        )
    if graph.consistency_score < 0.9:
        issues.append(
            CoverageIssue(
                issue_type="graph_inconsistency",
                severity="MEDIUM",
                affected_items=tuple(),
                reason="Low consistency score detected.",
                recommendation="Review contradictory semantics.",
            )
        )
    return semantic_score, issues, metric

# ---------------------------------------------------------------------------
# Confidence coverage
# ---------------------------------------------------------------------------

def _confidence_coverage(
    bms: List[BusinessMeaning],
    ctx: ContextValidation,
    cm: CanonicalMappingResult,
) -> Tuple[float, List[CoverageIssue], CoverageMetric]:
    bm_conf = sum(bm.confidence for bm in bms) / len(bms) if bms else 0.0
    cm_conf = cm.overall_confidence
    ctx_conf = (ctx.domain_confidence + ctx.confidence_adjustments) / 2.0 if hasattr(ctx, "domain_confidence") else 0.0
    confidence_score = (0.5 * bm_conf) + (0.25 * cm_conf) + (0.25 * ctx_conf)
    reasoning = f"BM={bm_conf:.2f}, CM={cm_conf:.2f}, CTX={ctx_conf:.2f} => {confidence_score:.2f}"
    metric = CoverageMetric(name="confidence_coverage", score=confidence_score, reasoning=reasoning)
    issues: List[CoverageIssue] = []
    if confidence_score < 0.6:
        issues.append(
            CoverageIssue(
                issue_type="low_confidence",
                severity="MEDIUM",
                affected_items=tuple(),
                reason="Overall confidence below acceptable threshold.",
                recommendation="Investigate ambiguous BusinessMeanings or insufficient validation.",
            )
        )
    return confidence_score, issues, metric

# ---------------------------------------------------------------------------
# Stability metric (balance across components)
# ---------------------------------------------------------------------------

def _stability_metric(scores: List[float]) -> Tuple[float, CoverageMetric]:
    if not scores:
        return 1.0, CoverageMetric(name="coverage_stability", score=1.0, reasoning="No components to evaluate.")
    range_score = max(scores) - min(scores)
    stability = 1.0 - range_score  # 1 = perfectly balanced, 0 = max imbalance
    reasoning = f"Component score range={range_score:.2f}; stability={stability:.2f}"
    metric = CoverageMetric(name="coverage_stability", score=stability, reasoning=reasoning)
    return stability, metric

# ---------------------------------------------------------------------------
# Penalty calculation – based on detected issues
# ---------------------------------------------------------------------------

def _quality_penalty(issues: List[CoverageIssue]) -> float:
    total_weight = sum(_SEVERITY_WEIGHTS.get(issue.severity, 0.0) for issue in issues)
    max_possible = len(issues) * _SEVERITY_WEIGHTS["HIGH"] if issues else 1.0
    normalized = total_weight / max_possible if max_possible else 0.0
    return _WEIGHT_PENALTY * normalized

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def infer_coverage(
    business_meanings: List[BusinessMeaning],
    context: ContextValidation,
    semantic_graph: SemanticKnowledgeGraph,
    canonical_mapping: CanonicalMappingResult,
) -> CoverageResult:
    """Compute deterministic coverage assessment.

    Returns
    -------
    CoverageResult
        Includes per‑component scores, detected issues, overall coverage, and readiness.
    """
    concept_score, concept_issues, concept_metric = _concept_coverage(business_meanings, canonical_mapping)
    entity_score, entity_issues, entity_metric = _entity_coverage(semantic_graph)
    semantic_score, semantic_issues, semantic_metric = _semantic_coverage(semantic_graph)
    confidence_score, confidence_issues, confidence_metric = _confidence_coverage(
        business_meanings, context, canonical_mapping
    )
    all_issues = concept_issues + entity_issues + semantic_issues + confidence_issues
    weighted_sum = (
        _WEIGHT_CONCEPT * concept_score
        + _WEIGHT_ENTITY * entity_score
        + _WEIGHT_SEMANTIC * semantic_score
        + _WEIGHT_CONFIDENCE * confidence_score
    )
    penalty = _quality_penalty(all_issues)
    # Normalize to allow a perfect dataset to reach 1.0
    raw_overall = max(0.0, weighted_sum - penalty)
    overall = min(1.0, raw_overall / (1.0 - _WEIGHT_PENALTY))
    # Stability metric across the four primary scores
    stability_score, stability_metric = _stability_metric([
        concept_score,
        entity_score,
        semantic_score,
        confidence_score,
    ])
    # Readiness thresholds (user‑specified)
    if overall >= 0.92:
        readiness = "READY"
    elif overall >= 0.80:
        readiness = "MOSTLY_READY"
    elif overall >= 0.60:
        readiness = "PARTIALLY_READY"
    else:
        readiness = "NOT_READY"
    summary = CoverageSummary(
        concept_coverage=concept_score,
        entity_coverage=entity_score,
        semantic_coverage=semantic_score,
        confidence_coverage=confidence_score,
        stability_coverage=stability_score,
        overall_coverage=overall,
        readiness=readiness,
    )
    assessment = CoverageAssessment(
        metrics=(concept_metric, entity_metric, semantic_metric, confidence_metric, stability_metric),
        issues=tuple(all_issues),
    )
    return CoverageResult(summary=summary, assessment=assessment)
