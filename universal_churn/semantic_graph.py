import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Set

from .business_meaning import BusinessMeaning
from .context_validation import ContextValidation

# ============================================================
# SEMANTIC KNOWLEDGE GRAPH INTELLIGENCE
# ============================================================
# Deterministic graph reasoning without external libraries, embeddings,
# ontologies, or LLMs. All identifiers and clustering are stable across
# runs. Domains are treated as metadata; BusinessEntity models concrete
# business objects (Customer, Policy, Account, Subscription, Claim, etc.).
# ===========================================================

# -----------------------------------------------------------------
# Taxonomy definitions – explicit separation of industry and business entities
# -----------------------------------------------------------------

# Industry taxonomy (metadata only)
_INDUSTRY_TAXONOMY: Set[str] = {
    "Insurance",
    "Telecom",
    "Retail",
    "Healthcare",
    "Banking",
}

# Business entity taxonomy (core semantic layer)
_BUSINESS_ENTITY_TAXONOMY: Set[str] = {
    "Customer",
    "Policy",
    "Claim",
    "Subscription",
    "Account",
    "Invoice",
    "Contract",
}

# -----------------------------------------------------------------
# Immutable dataclasses – public contract
# -----------------------------------------------------------------

@dataclass(frozen=True)
class GraphNode:
    """Node representing a BusinessMeaning in the knowledge graph.

    Attributes
    ----------
    node_id: int – stable deterministic identifier (1‑based after sorting).
    label: str – primary business concept.
    domain: str – industry context (e.g., "Insurance").
    metric: str – metric type (Money, Count, etc.).
    dimension: str – customer dimension.
    confidence: float – original confidence from BusinessMeaning.
    tags: Tuple[str, ...] – deterministic, sorted business tags.
    """

    node_id: int
    label: str
    domain: str
    metric: str
    dimension: str
    confidence: float
    tags: Tuple[str, ...]

@dataclass(frozen=True)
class GraphEdge:
    """Edge connecting two GraphNode instances.

    `directed` determines whether the edge should be interpreted as a
    directed relationship (source → target) or as an undirected link.
    """

    source_id: int
    target_id: int
    relation_type: str  # "semantic" or "dependency"
    weight: float  # deterministic similarity score between 0 and 1
    directed: bool = True

# -----------------------------------------------------------------
# BusinessEntity – concrete business objects (Customer, Policy, ...)
# -----------------------------------------------------------------

@dataclass(frozen=True)
class BusinessEntity:
    """Aggregates GraphNodes that belong to the same business object.

    The `entity_type` is a high‑level business object name (e.g., "Customer").
    The `domain` attribute stores industry context metadata (e.g., "Insurance").
    """

    entity_type: str                # e.g., "Customer"
    primary_concept: str            # primary concept that defines the entity
    domain: str                     # industry domain (metadata only)
    node_ids: Tuple[int, ...]       # IDs of nodes belonging to this entity
    aggregate_confidence: float
    related_entities: Tuple[str, ...] = ()  # optional cross‑entity links

@dataclass(frozen=True)
class SemanticCluster:
    """Hierarchical cluster – deterministic based on Domain → Metric → Dimension → Tags.
    """

    cluster_id: int
    level: str  # "domain", "metric", "dimension", "tag"
    key: str    # the actual value (e.g., "Financial")
    node_ids: Tuple[int, ...]

@dataclass(frozen=True)
class SemanticKnowledgeGraph:
    """Immutable container for the entire deterministic knowledge graph.

    Provides high‑level statistics and a reasoning narrative.
    """

    nodes: Tuple[GraphNode, ...]
    edges: Tuple[GraphEdge, ...]
    entities: Tuple[BusinessEntity, ...]
    clusters: Tuple[SemanticCluster, ...]
    central_concept_id: int
    consistency_score: float
    node_count: int
    edge_count: int
    connected_components: int
    average_degree: float
    density: float
    summary: str
    reasoning: str

# -----------------------------------------------------------------
# Helper utilities – deterministic only
# -----------------------------------------------------------------

def _stable_node_ids(bms: List[BusinessMeaning]) -> List[Tuple[int, BusinessMeaning]]:
    """Assign deterministic IDs based on alphabetical order of primary concept.
    Returns a list of (node_id, BusinessMeaning) tuples.
    """
    sorted_bms = sorted(bms, key=lambda bm: bm.primary_business_concept)
    return [(idx + 1, bm) for idx, bm in enumerate(sorted_bms)]

def _build_nodes(bms: List[BusinessMeaning]) -> List[GraphNode]:
    nodes: List[GraphNode] = []
    for node_id, bm in _stable_node_ids(bms):
        node = GraphNode(
            node_id=node_id,
            label=bm.primary_business_concept,
            domain=bm.domain,
            metric=bm.metric_type,
            dimension=bm.customer_dimension,
            confidence=bm.confidence,
            tags=tuple(sorted(bm.business_tags)),
        )
        nodes.append(node)
    return nodes

def _jaccard_similarity(a: Tuple[str, ...], b: Tuple[str, ...]) -> float:
    set_a, set_b = set(a), set(b)
    if not set_a and not set_b:
        return 1.0
    inter = set_a & set_b
    union = set_a | set_b
    return len(inter) / len(union)

def _discover_semantic_edges(nodes: List[GraphNode]) -> List[GraphEdge]:
    edges: List[GraphEdge] = []
    n = len(nodes)
    for i in range(n):
        for j in range(i + 1, n):
            src, tgt = nodes[i], nodes[j]
            tag_sim = _jaccard_similarity(src.tags, tgt.tags)
            domain_sim = 1.0 if src.domain == tgt.domain else 0.0
            weight = 0.7 * tag_sim + 0.3 * domain_sim
            if weight > 0.0:
                edges.append(GraphEdge(
                    source_id=src.node_id,
                    target_id=tgt.node_id,
                    relation_type="semantic",
                    weight=weight,
                    directed=False,
                ))
    return edges

# -----------------------------------------------------------------
# Concept → Business Entity mapping (deterministic heuristic)
# -----------------------------------------------------------------

def _build_concept_entity_map() -> Dict[str, str]:
    """Map each concept to a business entity type using keyword heuristics.

    The mapping is deterministic: the first matching entity keyword in the
    priority list is chosen. If no keyword matches, the concept is assigned to
    "Other" (still part of the taxonomy but not a core entity).
    """
    # Priority list – earlier entries win when multiple keywords could match.
    priority = [
        ("customer", "Customer"),
        ("policy", "Policy"),
        ("claim", "Claim"),
        ("subscription", "Subscription"),
        ("account", "Account"),
        ("invoice", "Invoice"),
        ("contract", "Contract"),
    ]
    concept_map: Dict[str, str] = {}
    # Gather all concepts from the business meaning taxonomy (via import).
    try:
        from .business_meaning import _HIERARCHICAL_CONCEPT_TAXONOMY
    except ImportError:
        _HIERARCHICAL_CONCEPT_TAXONOMY = {}
    for domain_info in _HIERARCHICAL_CONCEPT_TAXONOMY.values():
        for concept in domain_info.get("children", {}):
            lowered = concept.lower()
            assigned = "Other"
            for keyword, entity in priority:
                if keyword in lowered:
                    assigned = entity
                    break
            concept_map[concept] = assigned
    return concept_map

_CONCEPT_ENTITY_MAP = _build_concept_entity_map()

# -----------------------------------------------------------------
# Business entity hierarchy (parent → child) – deterministic static mapping
# -----------------------------------------------------------------

_ENTITY_PARENT_MAP: Dict[str, str] = {
    "Policy": "Customer",
    "Claim": "Policy",
    "Subscription": "Account",
    "Invoice": "Account",
    "Contract": "Policy",
    "Account": "Customer",
    # "Customer" has no parent (top level)
}

def _entity_parent(entity: str) -> Optional[str]:
    return _ENTITY_PARENT_MAP.get(entity)

# -----------------------------------------------------------------
# Concept‑based dependency edges (real business semantics)
# -----------------------------------------------------------------

def _concept_dependency_edges(nodes: List[GraphNode]) -> List[GraphEdge]:
    """Create directed edges based on business‑entity hierarchy.

    For each node, we determine its `entity_type` via `_CONCEPT_ENTITY_MAP`.
    If that entity has a parent entity, we locate a node that represents the
    parent entity (preferring the smallest node_id for determinism) and emit a
    directed edge parent → child.
    """
    edges: List[GraphEdge] = []
    # Map node_id -> entity_type
    node_entity: Dict[int, str] = {}
    for node in nodes:
        entity = _CONCEPT_ENTITY_MAP.get(node.label, "Other")
        node_entity[node.node_id] = entity
    # Group nodes by entity_type for quick lookup
    entity_nodes: Dict[str, List[int]] = {}
    for nid, ent in node_entity.items():
        entity_nodes.setdefault(ent, []).append(nid)
    # Deterministic lookup: sort node ids within each entity list
    for ents in entity_nodes.values():
        ents.sort()
    for child_nid, child_entity in node_entity.items():
        parent_entity = _entity_parent(child_entity)
        if not parent_entity:
            continue
        parent_candidates = entity_nodes.get(parent_entity, [])
        if not parent_candidates:
            continue
        # Choose the smallest node_id of the parent entity (deterministic)
        parent_nid = parent_candidates[0]
        edges.append(GraphEdge(
            source_id=parent_nid,
            target_id=child_nid,
            relation_type="dependency",
            weight=0.95,
            directed=True,
        ))
    return edges

# -----------------------------------------------------------------
# BusinessEntity discovery – separate Domain (metadata) from Entity
# -----------------------------------------------------------------

def _discover_entities(nodes: List[GraphNode]) -> List[BusinessEntity]:
    """Group nodes by their business entity type, keeping industry domain separate.
    """
    entity_groups: Dict[Tuple[str, str], List[int]] = {}
    confidence_groups: Dict[Tuple[str, str], List[float]] = {}
    for node in nodes:
        entity_type = _CONCEPT_ENTITY_MAP.get(node.label, "Other")
        key = (entity_type, node.domain)  # domain is metadata only
        entity_groups.setdefault(key, []).append(node.node_id)
        confidence_groups.setdefault(key, []).append(node.confidence)
    entities: List[BusinessEntity] = []
    for (entity_type, domain), ids in entity_groups.items():
        avg_conf = sum(confidence_groups[(entity_type, domain)]) / len(ids)
        # Primary concept – pick the label of the first node (deterministic)
        primary_concept = next(
            n.label for n in nodes if n.node_id == ids[0]
        )
        entities.append(BusinessEntity(
            entity_type=entity_type,
            primary_concept=primary_concept,
            domain=domain,
            node_ids=tuple(sorted(ids)),
            aggregate_confidence=avg_conf,
            related_entities=(),
        ))
    return entities

# -----------------------------------------------------------------
# Hierarchical deterministic clustering (Domain → Metric → Dimension → Tags)
# -----------------------------------------------------------------

def _hierarchical_clusters(nodes: List[GraphNode]) -> List[SemanticCluster]:
    clusters: List[SemanticCluster] = []
    cid = 1
    # Level 1 – Domain
    domain_map: Dict[str, List[int]] = {}
    for node in nodes:
        domain_map.setdefault(node.domain, []).append(node.node_id)
    for domain, ids in domain_map.items():
        clusters.append(SemanticCluster(cid, "domain", domain, tuple(sorted(ids))))
        cid += 1
    # Level 2 – Metric within each domain
    for domain, ids in domain_map.items():
        metric_map: Dict[str, List[int]] = {}
        for nid in ids:
            node = next(n for n in nodes if n.node_id == nid)
            metric_map.setdefault(node.metric, []).append(nid)
        for metric, mids in metric_map.items():
            clusters.append(SemanticCluster(cid, "metric", metric, tuple(sorted(mids))))
            cid += 1
    # Level 3 – Dimension within each metric
    for metric_cluster in [c for c in clusters if c.level == "metric"]:
        dim_map: Dict[str, List[int]] = {}
        for nid in metric_cluster.node_ids:
            node = next(n for n in nodes if n.node_id == nid)
            dim_map.setdefault(node.dimension, []).append(nid)
        for dim, dids in dim_map.items():
            clusters.append(SemanticCluster(cid, "dimension", dim, tuple(sorted(dids))))
            cid += 1
    # Level 4 – Tag clusters
    tag_map: Dict[str, List[int]] = {}
    for node in nodes:
        for tag in node.tags:
            tag_map.setdefault(tag, []).append(node.node_id)
    for tag, tids in tag_map.items():
        clusters.append(SemanticCluster(cid, "tag", tag, tuple(sorted(tids))))
        cid += 1
    return clusters

# -----------------------------------------------------------------
# Central concept identification (degree + confidence weighted)
# -----------------------------------------------------------------

def _compute_central_concept(nodes: List[GraphNode], edges: List[GraphEdge]) -> int:
    degree: Dict[int, int] = {node.node_id: 0 for node in nodes}
    for e in edges:
        degree[e.source_id] += 1
        degree[e.target_id] += 1
    max_deg = max(degree.values()) if degree else 1
    max_conf = max(node.confidence for node in nodes) if nodes else 1.0
    scores: Dict[int, float] = {}
    for node in nodes:
        deg_norm = degree[node.node_id] / max_deg if max_deg else 0.0
        conf_norm = node.confidence / max_conf if max_conf else 0.0
        scores[node.node_id] = 0.6 * deg_norm + 0.4 * conf_norm
    return max(scores, key=scores.get)

# -----------------------------------------------------------------
# Graph statistics (undirected view for connectivity)
# -----------------------------------------------------------------

def _graph_statistics(nodes: List[GraphNode], edges: List[GraphEdge]) -> Tuple[int, int, float, float, int]:
    node_count = len(nodes)
    edge_count = len(edges)
    adjacency: Dict[int, Set[int]] = {node.node_id: set() for node in nodes}
    for e in edges:
        adjacency[e.source_id].add(e.target_id)
        adjacency[e.target_id].add(e.source_id)
    visited = set()
    components = 0
    for nid in adjacency:
        if nid not in visited:
            components += 1
            stack = [nid]
            while stack:
                cur = stack.pop()
                if cur in visited:
                    continue
                visited.add(cur)
                stack.extend(adjacency[cur] - visited)
    average_degree = (2 * edge_count) / node_count if node_count else 0.0
    possible = node_count * (node_count - 1) / 2
    density = edge_count / possible if possible else 0.0
    return node_count, edge_count, average_degree, density, components

# -----------------------------------------------------------------
# Consistency scoring – cohesion, density, contradiction signals
# -----------------------------------------------------------------

def _consistency_score(nodes: List[GraphNode], edges: List[GraphEdge], contradictions: List[str]) -> float:
    if not edges:
        cohesion = 0.0
    else:
        sims = []
        lookup = {n.node_id: n for n in nodes}
        for e in edges:
            n1, n2 = lookup[e.source_id], lookup[e.target_id]
            sims.append(_jaccard_similarity(n1.tags, n2.tags))
        cohesion = sum(sims) / len(sims)
    _, _, _, density, _ = _graph_statistics(nodes, edges)
    contradiction_penalty = min(1.0, len(contradictions) / max(1, len(nodes)))
    score = 0.4 * cohesion + 0.3 * density + 0.3 * (1.0 - contradiction_penalty)
    return max(0.0, min(1.0, score))

# -----------------------------------------------------------------
# Main public API – deterministic inference of the Semantic Knowledge Graph
# -----------------------------------------------------------------

def infer_semantic_knowledge_graph(
    business_meanings: List[BusinessMeaning],
    context: ContextValidation,
) -> SemanticKnowledgeGraph:
    """Deterministically infer a SemanticKnowledgeGraph from BusinessMeaning
    instances and a ContextValidation result.

    The function respects all non‑negotiable rules: pure Python, no external
    graph libraries, no embeddings, no LLMs, and fully deterministic.
    """
    if not business_meanings:
        raise ValueError("At least one BusinessMeaning is required to build a graph.")

    # 1️⃣ Build nodes with stable IDs
    nodes = _build_nodes(business_meanings)

    # 2️⃣ Discover business entities (separate domain metadata)
    entities = _discover_entities(nodes)

    # 3️⃣ Semantic edges (undirected, based on tag & domain similarity)
    semantic_edges = _discover_semantic_edges(nodes)

    # 4️⃣ Concept‑based dependency edges (directed, reflecting business entity hierarchy)
    dependency_edges = _concept_dependency_edges(nodes)
    all_edges = semantic_edges + dependency_edges

    # 5️⃣ Hierarchical clustering (Domain → Metric → Dimension → Tags)
    clusters = _hierarchical_clusters(nodes)

    # 6️⃣ Central concept (degree + confidence weighted)
    central_id = _compute_central_concept(nodes, all_edges)

    # 7️⃣ Consistency analysis – incorporate contradictions from ContextValidation
    contradictions = [msg for msg in getattr(context, "validation_messages", []) if msg.lower().startswith("contradiction")]
    consistency = _consistency_score(nodes, all_edges, contradictions)

    # 8️⃣ Graph statistics
    node_cnt, edge_cnt, avg_deg, dens, comps = _graph_statistics(nodes, all_edges)

    # 9️⃣ Summary & reasoning narrative
    summary = (
        f"Graph with {node_cnt} nodes, {edge_cnt} edges. "
        f"Connected components: {comps}, density: {dens:.2%}. "
        f"Central concept ID: {central_id}. Consistency score: {consistency:.2%}."
    )
    reasoning = (
        f"Nodes indexed deterministically after sorting by primary concept. "
        f"Semantic edges capture tag and domain similarity (70% tag, 30% domain). "
        f"Dependency edges follow a deterministic business‑entity hierarchy (Customer → Policy → Claim, etc.), providing true business semantics. "
        f"Hierarchical clusters built Domain → Metric → Dimension → Tag. "
        f"Central concept combines degree (60%) and confidence (40%). "
        f"Consistency integrates cohesion, density, and contradiction signals from context."
    )

    return SemanticKnowledgeGraph(
        nodes=tuple(nodes),
        edges=tuple(all_edges),
        entities=tuple(entities),
        clusters=tuple(clusters),
        central_concept_id=central_id,
        consistency_score=consistency,
        node_count=node_cnt,
        edge_count=edge_cnt,
        connected_components=comps,
        average_degree=avg_deg,
        density=dens,
        summary=summary,
        reasoning=reasoning,
    )
