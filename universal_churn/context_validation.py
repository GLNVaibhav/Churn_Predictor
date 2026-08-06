import re
from dataclasses import dataclass, field
from typing import List, Dict, Any

from .business_meaning import BusinessMeaning

# ============================================================
# CONTEXT VALIDATION INTELLIGENCE
# ============================================================
# This module provides deterministic validation of a dataset's
# contextual consistency based on a list of BusinessMeaning objects.
# No external embeddings, LLMs, or knowledge‑graph resources are used.
# ============================================================


@dataclass(frozen=True)
class ContextValidation:
    """Immutable representation of dataset‑level context validation.

    All fields are derived deterministically from the supplied list of
    ``BusinessMeaning`` instances.
    """

    dataset_domain: str
    dataset_subdomain: str
    domain_confidence: float
    domain_votes: Dict[str, int]
    consensus_score: float
    ambiguity_detected: bool
    ambiguity_columns: List[str]
    cross_column_relationships: List[Dict[str, Any]]
    confidence_adjustments: float
    validation_messages: List[str]
    dataset_health: str
    reasoning: str

# ------------------------------------------------------------
# Helper functions – deterministic only
# ------------------------------------------------------------

def _aggregate_domain_votes(bms: List[BusinessMeaning]) -> Dict[str, int]:
    votes: Dict[str, int] = {}
    for bm in bms:
        votes[bm.domain] = votes.get(bm.domain, 0) + 1
    return votes

def _detect_ambiguity(bms: List[BusinessMeaning]) -> (bool, List[str]):
    """Identify columns whose meaning confidence is low.

    A column is considered ambiguous when its confidence is below 0.6.
    The identifier used is the primary business concept, which uniquely
    represents the column in the current deterministic pipeline.
    """
    ambiguous = [bm.primary_business_concept for bm in bms if bm.confidence < 0.6]
    return (len(ambiguous) > 0, ambiguous)

def _cross_column_relationships(bms: List[BusinessMeaning]) -> List[Dict[str, Any]]:
    """Create simple domain‑centric relationships.

    For each domain we list the primary concepts that belong to it.
    """
    domain_map: Dict[str, List[str]] = {}
    for bm in bms:
        domain_map.setdefault(bm.domain, []).append(bm.primary_business_concept)
    relationships: List[Dict[str, Any]] = []
    for domain, concepts in domain_map.items():
        if len(concepts) > 1:
            relationships.append({"domain": domain, "columns": concepts})
    return relationships

def _derive_subdomain(bms: List[BusinessMeaning]) -> str:
    """Derive a sub‑domain based on secondary concepts.

    The most common secondary concept across the dataset is used as the
    sub‑domain indicator. If no secondary concepts exist, the sub‑domain
    mirrors the primary domain.
    """
    secondary_counter: Dict[str, int] = {}
    for bm in bms:
        for sec in bm.secondary_concepts:
            secondary_counter[sec] = secondary_counter.get(sec, 0) + 1
    if secondary_counter:
        return max(secondary_counter, key=secondary_counter.get)
    # Fallback to the dominant domain
    domain_votes = _aggregate_domain_votes(bms)
    return max(domain_votes, key=domain_votes.get) if domain_votes else "General"

def _adjust_confidence(domain_conf: float, ambiguous: bool, ambiguity_ratio: float) -> float:
    """Apply a deterministic penalty for ambiguity.

    The penalty is 0.1 * ambiguity_ratio (the proportion of ambiguous
    columns). The result is clipped to the [0, 1] range.
    """
    penalty = 0.1 * ambiguity_ratio
    adjusted = domain_conf - penalty
    return max(0.0, min(1.0, adjusted))

def _assess_dataset_health(adjusted_conf: float, ambiguity: bool, contradictions: bool, cross_issues: bool) -> str:
    """Rich health diagnostic based on multiple signals.

    - Healthy: high adjusted confidence, no ambiguity, no contradictions,
      and no cross‑column semantic issues.
    - Warning: moderate confidence or a single mild issue.
    - Critical: low confidence or multiple serious issues.
    """
    if adjusted_conf >= 0.85 and not any([ambiguity, contradictions, cross_issues]):
        return "Healthy"
    if adjusted_conf >= 0.65 or sum([ambiguity, contradictions, cross_issues]) == 1:
        return "Warning"
    return "Critical"

# ------------------------------------------------------------
# Advanced consensus and contradiction logic
# ------------------------------------------------------------

def _concept_consensus(bms: List[BusinessMeaning]) -> float:
    """Proportion of columns sharing the most common primary concept.
    """
    counter: Dict[str, int] = {}
    for bm in bms:
        counter[bm.primary_business_concept] = counter.get(bm.primary_business_concept, 0) + 1
    if not counter:
        return 0.0
    most_common = max(counter.values())
    return most_common / len(bms)

def _dimension_consensus(bms: List[BusinessMeaning]) -> float:
    """Proportion of columns sharing the most common customer dimension.
    """
    counter: Dict[str, int] = {}
    for bm in bms:
        counter[bm.customer_dimension] = counter.get(bm.customer_dimension, 0) + 1
    if not counter:
        return 0.0
    most_common = max(counter.values())
    return most_common / len(bms)

def _contradiction_detection(bms: List[BusinessMeaning]) -> List[str]:
    """Detect contradictory interpretations.

    A contradiction is flagged when two columns share the same primary
    concept but disagree on metric type or customer dimension.
    """
    issues: List[str] = []
    # Group by primary concept
    concept_groups: Dict[str, List[BusinessMeaning]] = {}
    for bm in bms:
        concept_groups.setdefault(bm.primary_business_concept, []).append(bm)
    for concept, group in concept_groups.items():
        if len(group) < 2:
            continue
        metric_set = {g.metric_type for g in group}
        dim_set = {g.customer_dimension for g in group}
        if len(metric_set) > 1:
            issues.append(
                f"Metric type conflict for concept '{concept}': {', '.join(metric_set)}"
            )
        if len(dim_set) > 1:
            issues.append(
                f"Customer dimension conflict for concept '{concept}': {', '.join(dim_set)}"
            )
    return issues

def _cross_column_semantic_validation(bms: List[BusinessMeaning]) -> List[str]:
    """Validate simple semantic relationships across columns.

    Currently checks for mixed metric types within the same domain, which
    may indicate inconsistent semantics (e.g., Money and Count metrics in
    a purely financial domain).
    """
    issues: List[str] = []
    domain_metrics: Dict[str, set] = {}
    for bm in bms:
        domain_metrics.setdefault(bm.domain, set()).add(bm.metric_type)
    for domain, metrics in domain_metrics.items():
        if len(metrics) > 1:
            issues.append(
                f"Domain '{domain}' contains mixed metric types: {', '.join(metrics)}"
            )
    return issues

def _refine_confidence(bms: List[BusinessMeaning], concept_cons: float, dim_cons: float) -> Dict[str, float]:
    """Adjust each column's confidence based on dataset‑level consensus.

    The refined confidence is the original confidence scaled by the
    geometric mean of concept and dimension consensus scores. This remains
    deterministic and does not modify the original BusinessMeaning
    instances.
    """
    refined: Dict[str, float] = {}
    scale = (concept_cons * dim_cons) ** 0.5 if concept_cons and dim_cons else 1.0
    for bm in bms:
        refined[bm.primary_business_concept] = max(0.0, min(1.0, bm.confidence * scale))
    return refined

# ------------------------------------------------------------
# Public API – deterministic validation of a list of BusinessMeaning
# ------------------------------------------------------------

def validate_context(business_meanings: List[BusinessMeaning]) -> ContextValidation:
    """Validate dataset context based on deterministic heuristics.

    Parameters
    ----------
    business_meanings: List[BusinessMeaning]
        The per‑column business interpretations produced by the Business
        Meaning Intelligence layer.

    Returns
    -------
    ContextValidation
        An immutable dataclass containing validation results and a
        reasoning narrative.
    """
    total = len(business_meanings)
    if total == 0:
        raise ValueError("At least one BusinessMeaning instance is required for validation.")

    # 1️⃣ Domain voting
    domain_votes = _aggregate_domain_votes(business_meanings)
    dataset_domain = max(domain_votes, key=domain_votes.get)
    domain_confidence = domain_votes[dataset_domain] / total

    # 2️⃣ Sub‑domain detection
    dataset_subdomain = _derive_subdomain(business_meanings)

    # 3️⃣ Ambiguity detection
    ambiguity_detected, ambiguity_columns = _detect_ambiguity(business_meanings)
    ambiguity_ratio = len(ambiguity_columns) / total

    # 4️⃣ Cross‑column relationships
    cross_relationships = _cross_column_relationships(business_meanings)

    # 5️⃣ Consensus metrics
    concept_consensus_score = _concept_consensus(business_meanings)
    dimension_consensus_score = _dimension_consensus(business_meanings)

    # 6️⃣ Contradiction detection
    contradictions = _contradiction_detection(business_meanings)

    # 7️⃣ Cross‑column semantic validation
    semantic_issues = _cross_column_semantic_validation(business_meanings)

    # 8️⃣ Confidence adjustment (deterministic penalty + consensus scaling)
    base_adjusted = _adjust_confidence(domain_confidence, ambiguity_detected, ambiguity_ratio)
    # Apply consensus scaling to obtain final adjusted confidence for the dataset
    confidence_adjustments = base_adjusted * (concept_consensus_score * dimension_consensus_score) ** 0.5
    confidence_adjustments = max(0.0, min(1.0, confidence_adjustments))

    # 9️⃣ Consensus score – here defined as the final adjusted confidence
    consensus_score = confidence_adjustments

    # 10️⃣ Validation messages
    messages: List[str] = []
    if ambiguity_detected:
        messages.append(
            f"Ambiguity detected in columns: {', '.join(ambiguity_columns)} (confidence < 0.6)."
        )
    if domain_confidence < 0.5:
        messages.append(
            f"Low domain consensus: only {domain_confidence:.2%} of columns map to the dominant domain '{dataset_domain}'."
        )
    if concept_consensus_score < 0.5:
        messages.append(
            f"Concept consensus low ({concept_consensus_score:.2%}); many columns have differing primary concepts."
        )
    if dimension_consensus_score < 0.5:
        messages.append(
            f"Dimension consensus low ({dimension_consensus_score:.2%}); customer dimensions are varied."
        )
    if contradictions:
        messages.append(f"Contradictions found: {'; '.join(contradictions)}")
    if semantic_issues:
        messages.append(f"Semantic issues: {'; '.join(semantic_issues)}")
    if not cross_relationships:
        messages.append("No cross‑column domain relationships identified.")

    # 11️⃣ Dataset health assessment (richer diagnostics)
    dataset_health = _assess_dataset_health(
        confidence_adjustments,
        ambiguity_detected,
        bool(contradictions),
        bool(semantic_issues),
    )

    # 12️⃣ Reasoning narrative
    reasoning = (
        f"Domain voting yields '{dataset_domain}' with confidence {domain_confidence:.2%}. "
        f"Sub‑domain derived as '{dataset_subdomain}'. "
        f"Ambiguity flag is {ambiguity_detected} affecting {len(ambiguity_columns)} columns. "
        f"Concept consensus score {concept_consensus_score:.2%}, dimension consensus score {dimension_consensus_score:.2%}. "
        f"Detected {len(contradictions)} contradiction(s) and {len(semantic_issues)} semantic issue(s). "
        f"Cross‑column relationships found: {len(cross_relationships)} groups. "
        f"Adjusted confidence after ambiguity and consensus penalties: {confidence_adjustments:.2%}. "
        f"Overall dataset health assessed as '{dataset_health}'."
    )

    return ContextValidation(
        dataset_domain=dataset_domain,
        dataset_subdomain=dataset_subdomain,
        domain_confidence=domain_confidence,
        domain_votes=domain_votes,
        consensus_score=consensus_score,
        ambiguity_detected=ambiguity_detected,
        ambiguity_columns=ambiguity_columns,
        cross_column_relationships=cross_relationships,
        confidence_adjustments=confidence_adjustments,
        validation_messages=messages,
        dataset_health=dataset_health,
        reasoning=reasoning,
    )
