from dataclasses import dataclass
from typing import List, Tuple, Dict, Set

from .business_meaning import BusinessMeaning
from .context_validation import ContextValidation
from .semantic_graph import (
    SemanticKnowledgeGraph,
    GraphNode,
    BusinessEntity,
)

# -----------------------------------------------------------------
# Canonical Vocabulary – immutable mapping of universal concepts
# -----------------------------------------------------------------

@dataclass(frozen=True)
class CanonicalConcept:
    """Universal business concept identifier.

    Attributes
    ----------
    name: str – the canonical concept name (e.g., "Customer").
    description: str – optional human‑readable description.
    tags: Tuple[str, ...] – deterministic tags associated with the concept.
    domain: str – primary industry domain (optional).
    metric: str – typical metric type (optional).
    dimension: str – typical customer dimension (optional).
    """

    name: str
    description: str = ""
    tags: Tuple[str, ...] = ()
    domain: str = ""
    metric: str = ""
    dimension: str = ""

# Default canonical vocabulary covering the five industry taxonomies.
# The mapping includes additional metadata to enable richer scoring.
_CANONICAL_VOCABULARY: Dict[str, CanonicalConcept] = {
    "Customer": CanonicalConcept(
        name="Customer",
        description="An individual or organization receiving a service",
        tags=("customer", "client"),
        domain="",
        metric="Count",
        dimension="Demographic",
    ),
    "Policy": CanonicalConcept(
        name="Policy",
        description="Insurance or subscription policy",
        tags=("policy", "coverage"),
        domain="Insurance",
        metric="Count",
        dimension="Insurance",
    ),
    "Claim": CanonicalConcept(
        name="Claim",
        description="Insurance claim or service request",
        tags=("claim", "request"),
        domain="Insurance",
        metric="Money",
        dimension="Insurance",
    ),
    "Subscription": CanonicalConcept(
        name="Subscription",
        description="Recurring service subscription",
        tags=("subscription", "plan"),
        domain="Telecom",
        metric="Money",
        dimension="Product",
    ),
    "Account": CanonicalConcept(
        name="Account",
        description="Financial or user account",
        tags=("account", "balance"),
        domain="Banking",
        metric="Money",
        dimension="Financial",
    ),
    "Invoice": CanonicalConcept(
        name="Invoice",
        description="Billing invoice",
        tags=("invoice", "billing"),
        domain="Retail",
        metric="Money",
        dimension="Financial",
    ),
    "Contract": CanonicalConcept(
        name="Contract",
        description="Legal contract",
        tags=("contract", "agreement"),
        domain="Insurance",
        metric="Money",
        dimension="Insurance",
    ),
    "Revenue": CanonicalConcept(
        name="Revenue",
        description="Income generated",
        tags=("revenue", "income"),
        domain="Financial",
        metric="Money",
        dimension="Financial",
    ),
    "Cost": CanonicalConcept(
        name="Cost",
        description="Expense incurred",
        tags=("cost", "expense"),
        domain="Financial",
        metric="Money",
        dimension="Financial",
    ),
    "ChurnProbability": CanonicalConcept(
        name="ChurnProbability",
        description="Likelihood of churn",
        tags=("churn", "attrition"),
        domain="Risk",
        metric="Score",
        dimension="Risk",
    ),
    "Retention": CanonicalConcept(
        name="Retention",
        description="Customer retention metric",
        tags=("retention", "loyalty"),
        domain="Risk",
        metric="Score",
        dimension="Risk",
    ),
    "LossAmount": CanonicalConcept(
        name="LossAmount",
        description="Monetary loss",
        tags=("loss", "amount"),
        domain="Financial",
        metric="Money",
        dimension="Financial",
    ),
    "Premium": CanonicalConcept(
        name="Premium",
        description="Insurance premium",
        tags=("premium", "payment"),
        domain="Insurance",
        metric="Money",
        dimension="Insurance",
    ),
    "Usage": CanonicalConcept(
        name="Usage",
        description="Resource usage",
        tags=("usage", "consumption"),
        domain="Telecom",
        metric="Count",
        dimension="Product",
    ),
    "RecurringRevenue": CanonicalConcept(
        name="RecurringRevenue", description="Value of recurring prepaid or subscription recharge",
        tags=("recharge", "recurring", "revenue"), domain="Telecom", metric="Money", dimension="Billing",
    ),
    "AverageRevenuePerUser": CanonicalConcept(
        name="AverageRevenuePerUser", description="Average revenue generated per telecom subscriber",
        tags=("arpu", "average", "revenue"), domain="Telecom", metric="Money", dimension="Billing",
    ),
    "MessagingUsage": CanonicalConcept(
        name="MessagingUsage", description="Subscriber SMS or message activity",
        tags=("sms", "messaging", "usage"), domain="Telecom", metric="Count", dimension="Service",
    ),
    "VoiceUsage": CanonicalConcept(
        name="VoiceUsage", description="Subscriber voice calling activity",
        tags=("voice", "call", "usage"), domain="Telecom", metric="Duration", dimension="Service",
    ),
    "SupportContacts": CanonicalConcept(
        name="SupportContacts", description="Customer complaints or support contacts",
        tags=("complaint", "support", "contact"), domain="Telecom", metric="Count", dimension="CustomerSupport",
    ),
    "ActivityRecency": CanonicalConcept(
        name="ActivityRecency", description="Time since the customer's last service activity",
        tags=("recency", "activity", "recharge"), domain="Telecom", metric="Duration", dimension="Lifecycle",
    ),
    "ProductPortfolio": CanonicalConcept(
        name="ProductPortfolio", description="Telecom products adopted by a customer",
        tags=("broadband", "product", "portfolio"), domain="Telecom", metric="Boolean", dimension="Product",
    ),
    "Payment": CanonicalConcept(
        name="Payment",
        description="Payment transaction",
        tags=("payment", "transaction"),
        domain="Retail",
        metric="Money",
        dimension="Financial",
    ),
    "Complaint": CanonicalConcept(name="Complaint", description="Customer complaint history", tags=("complaint", "support"), domain="", metric="Count", dimension="CustomerSupport"),
    "Support": CanonicalConcept(name="Support", description="Support interaction", tags=("support", "ticket"), domain="", metric="Count", dimension="CustomerSupport"),
    "Network": CanonicalConcept(name="Network", description="Service network or region", tags=("network", "operator", "region"), domain="Telecom", metric="Category", dimension="Service"),
    "Marketing": CanonicalConcept(name="Marketing", description="Marketing engagement", tags=("marketing", "campaign"), domain="", metric="Category", dimension="Marketing"),
    "CustomerExperience": CanonicalConcept(name="CustomerExperience", description="Customer experience signal", tags=("experience", "satisfaction"), domain="", metric="Score", dimension="CustomerExperience"),
    "ServiceQuality": CanonicalConcept(name="ServiceQuality", description="Quality of delivered service", tags=("quality", "network", "call"), domain="Telecom", metric="Score", dimension="ServiceQuality"),
    "Risk": CanonicalConcept(name="Risk", description="Business risk signal", tags=("risk", "churn", "port"), domain="Risk", metric="Score", dimension="Risk"),
    "Billing": CanonicalConcept(name="Billing", description="Billing experience", tags=("billing", "charge", "invoice"), domain="Financial", metric="Money", dimension="Billing"),
    "Loyalty": CanonicalConcept(name="Loyalty", description="Customer value or loyalty", tags=("loyalty", "value", "tenure"), domain="", metric="Score", dimension="Loyalty"),
    "Interaction": CanonicalConcept(name="Interaction", description="Customer interaction", tags=("interaction", "usage", "visit"), domain="", metric="Count", dimension="Interaction"),
    "Product": CanonicalConcept(name="Product", description="Product holding", tags=("product", "plan", "service"), domain="", metric="Category", dimension="Product"),
    "Offer": CanonicalConcept(name="Offer", description="Commercial offer", tags=("offer", "cashback", "promotion"), domain="", metric="Money", dimension="Marketing"),
    "Lifecycle": CanonicalConcept(name="Lifecycle", description="Customer relationship lifecycle", tags=("tenure", "lifecycle", "duration"), domain="", metric="Duration", dimension="Lifecycle"),
}

# -----------------------------------------------------------------
# Helper structures for deterministic scoring
# -----------------------------------------------------------------

# Priority list for entity type inference – mirrors semantic_graph logic.
_ENTITY_PRIORITY = [
    ("customer", "Customer"),
    ("policy", "Policy"),
    ("claim", "Claim"),
    ("subscription", "Subscription"),
    ("account", "Account"),
    ("invoice", "Invoice"),
    ("contract", "Contract"),
]

def _infer_entity_type(concept: str) -> str:
    """Map a BusinessMeaning primary concept to a business entity type.
    Deterministic – first matching keyword wins; otherwise "Other".
    """
    lowered = concept.lower()
    for kw, ent in _ENTITY_PRIORITY:
        if kw in lowered:
            return ent
    return "Other"

def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 1.0
    inter = a & b
    union = a | b
    return len(inter) / len(union)

def _graph_neighbors(node_id: int, graph: SemanticKnowledgeGraph) -> List[GraphNode]:
    neighbor_ids = set()
    for e in graph.edges:
        if e.source_id == node_id:
            neighbor_ids.add(e.target_id)
        if e.target_id == node_id:
            neighbor_ids.add(e.source_id)
    return [n for n in graph.nodes if n.node_id in neighbor_ids]

def _entity_match_score(bm_entity: str, canon_entity: str) -> float:
    return 1.0 if bm_entity == canon_entity else 0.0

def _domain_match_score(bm_domain: str, canon_domain: str) -> float:
    if not canon_domain:
        return 1.0
    return 1.0 if bm_domain == canon_domain else 0.0

def _metric_match_score(bm_metric: str, canon_metric: str) -> float:
    if not canon_metric:
        return 1.0
    return 1.0 if bm_metric == canon_metric else 0.0

def _dimension_match_score(bm_dim: str, canon_dim: str) -> float:
    if not canon_dim:
        return 1.0
    return 1.0 if bm_dim == canon_dim else 0.0

def _tag_similarity_score(bm_tags: Set[str], canon_tags: Set[str]) -> float:
    return _jaccard(bm_tags, canon_tags)

def _graph_context_score(bm_node: GraphNode, canon: CanonicalConcept, graph: SemanticKnowledgeGraph) -> float:
    neighbors = _graph_neighbors(bm_node.node_id, graph)
    neighbor_tags = set()
    for n in neighbors:
        neighbor_tags.update(t.lower() for t in n.tags)
    return _jaccard(neighbor_tags, set(t.lower() for t in canon.tags))

def _graph_entity_score(bm_node: GraphNode, canon: CanonicalConcept, graph: SemanticKnowledgeGraph) -> float:
    """Score 1.0 if the BusinessEntity containing bm_node matches the canonical entity name.
    """
    for entity in graph.entities:
        if bm_node.node_id in entity.node_ids and entity.entity_type == canon.name:
            return 1.0
    return 0.0

def _context_signal_score(bm: BusinessMeaning, context: ContextValidation) -> float:
    """Combine dominant domain agreement and ambiguity signals.
    Returns a value in [0, 1].
    """
    dominant = None
    if hasattr(context, "domain_votes"):
        votes = getattr(context, "domain_votes")
        if isinstance(votes, dict) and votes:
            dominant = max(votes, key=votes.get)
    domain_score = 1.0 if dominant and bm.domain == dominant else 0.0
    ambiguity_penalty = 0.0
    if getattr(context, "ambiguity_detected", False):
        ambiguous_cols = getattr(context, "ambiguity_columns", [])
        if bm.primary_business_concept in ambiguous_cols:
            ambiguity_penalty = 0.2
    return max(0.0, min(1.0, domain_score - ambiguity_penalty))

# -----------------------------------------------------------------
# Public immutable dataclasses for the result
# -----------------------------------------------------------------

@dataclass(frozen=True)
class CanonicalCandidate:
    concept: CanonicalConcept
    score: float
    reasoning: str

@dataclass(frozen=True)
class CanonicalMapping:
    column_name: str
    chosen_concept: CanonicalConcept
    confidence: float
    reasoning: str
    candidates: Tuple[CanonicalCandidate, ...]

@dataclass(frozen=True)
class CanonicalCoverage:
    mapped_count: int
    unmapped_count: int
    total: int
    completeness: float
    ambiguous_count: int
    conflicting_count: int
    duplicate_count: int
    high_confidence_count: int

@dataclass(frozen=True)
class CanonicalMappingResult:
    mappings: Tuple[CanonicalMapping, ...]
    coverage: CanonicalCoverage
    overall_confidence: float
    reasoning: str

# -----------------------------------------------------------------
# Core scoring – deterministic multi‑factor model with normalized weights
# -----------------------------------------------------------------

# Raw component weights (sum to 0.90). They will be normalized so a perfect match can reach 1.0.
_WEIGHT_ENTITY = 0.15
_WEIGHT_TAGS = 0.10
_WEIGHT_DOMAIN = 0.10
_WEIGHT_METRIC = 0.10
_WEIGHT_DIMENSION = 0.10
_WEIGHT_GRAPH = 0.15
_WEIGHT_CONTEXT = 0.20
_WEIGHT_GRAPH_ENTITY = 0.10
_TOTAL_WEIGHT = (
    _WEIGHT_ENTITY
    + _WEIGHT_TAGS
    + _WEIGHT_DOMAIN
    + _WEIGHT_METRIC
    + _WEIGHT_DIMENSION
    + _WEIGHT_GRAPH
    + _WEIGHT_CONTEXT
    + _WEIGHT_GRAPH_ENTITY
)

def _candidate_score_multi(
    bm: BusinessMeaning,
    canon: CanonicalConcept,
    bm_node: GraphNode,
    graph: SemanticKnowledgeGraph,
    context: ContextValidation,
) -> float:
    declared_canonical = bm.supporting_features.get("canonical")
    if declared_canonical == canon.name:
        # A knowledge pack is an explicit, auditable canonical declaration.
        return 1.0
    bm_entity = _infer_entity_type(bm.primary_business_concept)
    entity_score = _entity_match_score(bm_entity, canon.name)
    tag_score = _tag_similarity_score(set(t.lower() for t in bm.business_tags), set(t.lower() for t in canon.tags))
    domain_score = _domain_match_score(bm.domain, canon.domain)
    metric_score = _metric_match_score(bm.metric_type, canon.metric)
    dimension_score = _dimension_match_score(bm.customer_dimension, canon.dimension)
    graph_score = _graph_context_score(bm_node, canon, graph)
    graph_entity_score = _graph_entity_score(bm_node, canon, graph)
    context_score = _context_signal_score(bm, context)
    raw_total = (
        _WEIGHT_ENTITY * entity_score
        + _WEIGHT_TAGS * tag_score
        + _WEIGHT_DOMAIN * domain_score
        + _WEIGHT_METRIC * metric_score
        + _WEIGHT_DIMENSION * dimension_score
        + _WEIGHT_GRAPH * graph_score
        + _WEIGHT_GRAPH_ENTITY * graph_entity_score
        + _WEIGHT_CONTEXT * context_score
    )
    return max(0.0, min(1.0, raw_total / _TOTAL_WEIGHT))

def _generate_candidates(bm: BusinessMeaning, graph: SemanticKnowledgeGraph, context: ContextValidation) -> List[CanonicalCandidate]:
    matching_nodes = [n for n in graph.nodes if n.label == bm.primary_business_concept]
    if matching_nodes:
        bm_node = matching_nodes[0]
    else:
        bm_node = GraphNode(
            node_id=0,
            label=bm.primary_business_concept,
            domain=bm.domain,
            metric=bm.metric_type,
            dimension=bm.customer_dimension,
            confidence=bm.confidence,
            tags=tuple(sorted(bm.business_tags)),
        )
    candidates: List[CanonicalCandidate] = []
    for canon in _CANONICAL_VOCABULARY.values():
        sc = _candidate_score_multi(bm, canon, bm_node, graph, context)
        reasoning = (
            f"Entity={_entity_match_score(_infer_entity_type(bm.primary_business_concept), canon.name):.2f}; "
            f"TagJacc={_tag_similarity_score(set(t.lower() for t in bm.business_tags), set(t.lower() for t in canon.tags)):.2f}; "
            f"Domain={_domain_match_score(bm.domain, canon.domain):.2f}; "
            f"Metric={_metric_match_score(bm.metric_type, canon.metric):.2f}; "
            f"Dim={_dimension_match_score(bm.customer_dimension, canon.dimension):.2f}; "
            f"Graph={_graph_context_score(bm_node, canon, graph):.2f}; "
            f"GraphEnt={_graph_entity_score(bm_node, canon, graph):.2f}; "
            f"Ctx={_context_signal_score(bm, context):.2f}"
        )
        candidates.append(CanonicalCandidate(concept=canon, score=sc, reasoning=reasoning))
    return candidates

def _rank_candidates(candidates: List[CanonicalCandidate]) -> List[CanonicalCandidate]:
    return sorted(candidates, key=lambda c: (-c.score, c.concept.name))

# -----------------------------------------------------------------
# Core API – deterministic canonical mapping inference
# -----------------------------------------------------------------

_AMBIGUITY_MARGIN = 0.05
_HIGH_CONFIDENCE_THRESHOLD = 0.80

def infer_canonical_mapping(
    business_meanings: List[BusinessMeaning],
    context: ContextValidation,
    semantic_graph: SemanticKnowledgeGraph,
) -> CanonicalMappingResult:
    """Map dataset‑specific BusinessMeanings to a universal canonical vocabulary.

    Leverages graph relationships, entity information, context signals, and a deterministic
    multi‑factor scoring model with normalized weights.
    """
    if not business_meanings:
        raise ValueError("At least one BusinessMeaning is required for canonical mapping.")

    mappings: List[CanonicalMapping] = []
    ambiguous_counter = 0
    duplicate_counter: Dict[str, int] = {}
    high_conf_counter = 0
    conflicting_counter = 0

    for idx, bm in enumerate(business_meanings):
        column_name = f"col_{idx}_{bm.primary_business_concept}"
        candidates = _generate_candidates(bm, semantic_graph, context)
        ranked = _rank_candidates(candidates)
        top = ranked[0]
        second_score = ranked[1].score if len(ranked) > 1 else 0.0
        margin = top.score - second_score
        confidence = top.score
        if margin < _AMBIGUITY_MARGIN:
            ambiguous_counter += 1
        dup_key = top.concept.name
        duplicate_counter[dup_key] = duplicate_counter.get(dup_key, 0) + 1
        if confidence >= _HIGH_CONFIDENCE_THRESHOLD:
            high_conf_counter += 1
        if duplicate_counter[dup_key] > 1:
            prev = [m for m in mappings if m.chosen_concept.name == dup_key]
            for p in prev:
                prev_entity = _infer_entity_type(p.column_name.split('_', 2)[-1])
                curr_entity = _infer_entity_type(bm.primary_business_concept)
                if prev_entity != curr_entity:
                    conflicting_counter += 1
                    break
        reasoning = (
            f"Top candidate {top.concept.name} (score={top.score:.3f}, margin={margin:.3f}); "
            f"{top.reasoning}"
        )
        mappings.append(
            CanonicalMapping(
                column_name=column_name,
                chosen_concept=top.concept,
                confidence=confidence,
                reasoning=reasoning,
                candidates=tuple(ranked),
            )
        )

    total = len(business_meanings)
    mapped = sum(1 for m in mappings if m.confidence > 0.0)
    unmapped = total - mapped
    completeness = mapped / total if total else 0.0
    duplicate_total = sum(1 for v in duplicate_counter.values() if v > 1)
    coverage = CanonicalCoverage(
        mapped_count=mapped,
        unmapped_count=unmapped,
        total=total,
        completeness=completeness,
        ambiguous_count=ambiguous_counter,
        conflicting_count=conflicting_counter,
        duplicate_count=duplicate_total,
        high_confidence_count=high_conf_counter,
    )
    overall_conf = sum(m.confidence for m in mappings) / total if total else 0.0

    parts = []
    if ambiguous_counter:
        parts.append(f"{ambiguous_counter} ambiguous mappings (margin < {_AMBIGUITY_MARGIN}).")
    if duplicate_total:
        parts.append(f"{duplicate_total} duplicate canonical concepts across columns.")
    if conflicting_counter:
        parts.append(f"{conflicting_counter} conflicting mappings detected (different inferred entities).")
    if high_conf_counter:
        parts.append(f"{high_conf_counter} high‑confidence mappings (score ≥ {_HIGH_CONFIDENCE_THRESHOLD}).")
    if not parts:
        parts.append("All mappings confident, unique, and high quality.")
    overall_reasoning = " ".join(parts)

    return CanonicalMappingResult(
        mappings=tuple(mappings),
        coverage=coverage,
        overall_confidence=overall_conf,
        reasoning=overall_reasoning,
    )
