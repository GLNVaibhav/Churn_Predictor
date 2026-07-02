"""
universal_churn/business_concept_graph.py
══════════════════════════════════════════════════════════════════════
Business Concept Graph — Version 7, Chunk 2, Parts 1-3.

Replaces the FLAT confidence representation

    RECURRING_COMMITMENT  -> 80%
    CUSTOMER_LOYALTY      -> 50%
    SUPPORT_FRICTION      -> 90%

with a GRAPH representation:

    RECURRING_COMMITMENT
    ├── Recurring_Cost   (required)
    └── Total_Spend      (optional / proxy)

    CUSTOMER_LOYALTY
    └── Tenure_Raw       (required)

    SUPPORT_FRICTION
    └── Support_Contacts (required)

    ENGAGEMENT_LEVEL
    └── Engagement_Volume (required)

    SATISFACTION_SIGNAL
    └── Satisfaction_Raw  (required)

Per architecture rule "Do NOT duplicate schema mappings", every
dependency edge below is DERIVED from business_concepts.py's existing
`required_canonical_fields` / `optional_canonical_fields` properties
(themselves derived from each concept's per-sector `sources` dict) —
nothing here hand-lists an alias or canonical field name of its own.

This module does NOT touch business_concepts.py, canonical_fields.py,
or schema_resolution.py. It is a pure, read-only, additive consumer of
all three — same pattern concept_confidence.py already established.

Public surface
--------------
    BusinessConceptNode   — one graph node (a concept or, as a leaf,
                             a canonical field).
    BusinessConceptEdge   — one dependency edge.
    BusinessConceptGraph  — the graph: nodes + edges + confidence
                             propagation.
    build_concept_graph() — construct the STRUCTURAL graph (no
                             confidence yet) from BUSINESS_CONCEPTS.
    CONCEPT_GRAPH          — module-level singleton of the structural
                             graph, built once at import time (the
                             structure never changes at runtime; only
                             per-file confidence does).
    resolve_graph_confidence(df_input, sector)
                           — return a per-file COPY of CONCEPT_GRAPH
                             with confidence/resolved_fields/
                             missing_fields populated for that input.

Confidence model (Part 3)
--------------------------
For each concept node, given the set of canonical fields that actually
resolved from THIS input file (via schema_resolution.resolve_schema):

    1. Local confidence — same "primary source" calculation
       concept_confidence.py has always used:
           primary = concept.sources.get(sector)
           if primary resolved:
               local = primary.confidence * resolution_confidence(primary.field)
       This branch is BIT-FOR-BIT unchanged from the pre-graph
       calculation — nothing about an already-working reconstruction
       gets riskier.

    2. Graph propagation / partial recovery — NEW. Only runs when the
       primary source is missing or undocumented for this sector (the
       case that previously always fell straight to confidence 0.0).
       In that case, every OTHER required/optional canonical field
       this concept depends on (which may come from a *different*
       sector's mapping — e.g. RECURRING_COMMITMENT's healthcare
       primary is Recurring_Cost, but banking's Total_Spend is also a
       documented dependency of the same concept) is checked. Each one
       that resolved in this file contributes a weighted, penalized
       bonus:
           - required-field bonus weight  = 1.0
           - optional-field bonus weight  = 0.5
           - each bonus is scaled by that field's own resolution
             confidence and by OPTIONAL_FIELD_BONUS, then the total is
             capped at MAX_OPTIONAL_BONUS so a fallback field can never
             fully substitute for the concept's own primary measure.
       If no other dependency resolved either, confidence stays 0.0 —
       identical to the pre-graph behaviour.

    Because branch (1) is untouched and branch (2) only ever raises a
    result that used to be a hard 0.0, this is additive: it cannot
    lower any previously-computed confidence, and it changes a
    previously-computed confidence only in cases that ALSO had a
    literal 0.0 before AND have some other graph-documented field
    present. See BUSINESS_CONCEPT_GRAPH.md for the parity argument in
    full plus the fixtures/golden files this was checked against.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import copy

from .business_concepts import BUSINESS_CONCEPTS, BusinessConceptDefinition, CONCEPT_NAMES
from .schema_resolution import resolve_schema

import pandas as pd


# ══════════════════════════════════════════════════════════════════
# TUNABLES — separate from concept_confidence.py's constants; this is
# the graph-propagation policy, not the primary-source policy.
# ══════════════════════════════════════════════════════════════════

OPTIONAL_FIELD_BONUS = 0.5   # per-field bonus scale before capping
MAX_OPTIONAL_BONUS   = 0.30  # hard ceiling — a fallback/partial match
                              # can never look as trustworthy as a
                              # real primary-source reconstruction.


# ══════════════════════════════════════════════════════════════════
# PART 1 — GRAPH DATACLASSES
# ══════════════════════════════════════════════════════════════════

@dataclass
class BusinessConceptEdge:
    """One dependency edge: concept -> canonical field (or, for future
    concept-of-concepts nesting, concept -> concept)."""
    source: str                 # concept_id
    target: str                 # canonical field name, or child concept_id
    edge_type: str = "field"    # 'field' | 'concept'
    required: bool = True
    weight: float = 1.0


@dataclass
class BusinessConceptNode:
    """One graph node. Every concept in BUSINESS_CONCEPTS becomes one
    of these; canonical fields are referenced by name (as edge
    targets) rather than materialised as their own node objects, since
    canonical_fields.py is already the single source of truth for
    field-level metadata."""
    concept_id: str
    display_name: str
    description: str = ""
    weight: int = 3                                   # business importance, 1..5

    required_canonical_fields: tuple[str, ...] = field(default_factory=tuple)
    optional_canonical_fields: tuple[str, ...] = field(default_factory=tuple)

    parent_concepts: list[str] = field(default_factory=list)
    child_concepts: list[str] = field(default_factory=list)

    # Populated per-input-file by resolve_graph_confidence(); zero/empty
    # on the structural (CONCEPT_GRAPH) singleton.
    confidence: float = 0.0
    resolved_fields: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def all_dependency_fields(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(
            list(self.required_canonical_fields) + list(self.optional_canonical_fields)
        ))

    def dependency_health(self) -> str:
        """Coarse GOOD / FAIR / POOR band — used by concept_graph_report.py."""
        if self.confidence >= 0.70:
            return "GOOD"
        if self.confidence >= 0.35:
            return "FAIR"
        return "POOR"

    def to_dict(self) -> dict:
        return {
            'concept_id'                : self.concept_id,
            'display_name'               : self.display_name,
            'weight'                     : self.weight,
            'required_canonical_fields'  : list(self.required_canonical_fields),
            'optional_canonical_fields'  : list(self.optional_canonical_fields),
            'parent_concepts'            : self.parent_concepts,
            'child_concepts'             : self.child_concepts,
            'confidence'                 : self.confidence,
            'resolved_fields'            : self.resolved_fields,
            'missing_fields'             : self.missing_fields,
            'dependency_health'          : self.dependency_health(),
            'metadata'                   : self.metadata,
        }


class BusinessConceptGraph:
    """
    A directed graph of BusinessConceptNode objects connected by
    BusinessConceptEdge objects. Today every edge is concept -> field
    (a two-level tree per concept); `parent_concepts` / `child_concepts`
    exist on the node so a FUTURE build (e.g. a higher-level
    "Financial Health" concept composed of RECURRING_COMMITMENT +
    SATISFACTION_SIGNAL) can add concept -> concept edges without any
    structural change here — see BUSINESS_CONCEPT_GRAPH.md, "Future
    expansion".
    """

    def __init__(self) -> None:
        self.nodes: dict[str, BusinessConceptNode] = {}
        self.edges: list[BusinessConceptEdge] = []

    # ── construction helpers ────────────────────────────────────
    def add_node(self, node: BusinessConceptNode) -> None:
        self.nodes[node.concept_id] = node

    def add_edge(self, edge: BusinessConceptEdge) -> None:
        self.edges.append(edge)
        if edge.edge_type == "concept" and edge.target in self.nodes:
            self.nodes[edge.source].child_concepts.append(edge.target)
            self.nodes[edge.target].parent_concepts.append(edge.source)

    # ── read helpers ─────────────────────────────────────────────
    def get_node(self, concept_id: str) -> BusinessConceptNode | None:
        return self.nodes.get(concept_id)

    def field_edges_for(self, concept_id: str) -> list[BusinessConceptEdge]:
        return [e for e in self.edges if e.source == concept_id and e.edge_type == "field"]

    def concept_ids(self) -> list[str]:
        return list(self.nodes.keys())

    # ── PART 3 — CONFIDENCE PROPAGATION ─────────────────────────
    def propagate_confidence(
        self,
        primary_local_confidence: dict[str, float],
        resolved_field_confidence: dict[str, float],
    ) -> None:
        """
        Populate every node's `confidence`, `resolved_fields`, and
        `missing_fields` in place.

        Parameters
        ----------
        primary_local_confidence : dict[concept_id -> float | None]
            The pre-graph "primary source" confidence for each concept
            (source.confidence * resolution_confidence), or None if
            this sector has no documented primary source, or 0.0 if it
            does but the primary field never resolved in this file.
            Concepts with a positive value here short-circuit straight
            to that value (branch 1 — bit-for-bit unchanged behaviour).
        resolved_field_confidence : dict[canonical_field -> float]
            Best resolution confidence (schema_resolution.py) seen for
            every canonical field name that resolved from this input
            file at all, regardless of which concept/sector documents
            it. Drives branch 2 (graph partial recovery).
        """
        for concept_id, node in self.nodes.items():
            node.resolved_fields = [
                f for f in node.all_dependency_fields if f in resolved_field_confidence
            ]
            node.missing_fields = [
                f for f in node.all_dependency_fields if f not in resolved_field_confidence
            ]

            primary = primary_local_confidence.get(concept_id)

            if primary is not None and primary > 0.0:
                # Branch 1 — primary source resolved normally.
                node.confidence = round(primary, 4)
                node.metadata['reconstruction_path'] = 'primary_source'
                continue

            # Branch 2 — graph partial recovery. Only fields OTHER than
            # whatever a primary source already tried (that field is
            # already known unresolved if we got here, so including it
            # in the search is harmless — it just won't be found).
            bonus = 0.0
            contributing: list[str] = []
            for edge in self.field_edges_for(concept_id):
                field_conf = resolved_field_confidence.get(edge.target)
                if not field_conf:
                    continue
                edge_weight = 1.0 if edge.required else 0.5
                bonus += OPTIONAL_FIELD_BONUS * edge_weight * field_conf
                contributing.append(edge.target)

            bonus = min(bonus, MAX_OPTIONAL_BONUS)

            node.confidence = round(bonus, 4)
            node.metadata['reconstruction_path'] = (
                'graph_partial_recovery' if bonus > 0 else 'unreconstructable'
            )
            node.metadata['contributing_fields'] = contributing

    def to_dict(self) -> dict:
        return {
            'nodes': {cid: n.to_dict() for cid, n in self.nodes.items()},
            'edges': [
                {'source': e.source, 'target': e.target, 'edge_type': e.edge_type,
                 'required': e.required, 'weight': e.weight}
                for e in self.edges
            ],
        }


# ══════════════════════════════════════════════════════════════════
# PART 2 — GRAPH CONSTRUCTION (structural, sector-agnostic)
# ══════════════════════════════════════════════════════════════════

def build_concept_graph() -> BusinessConceptGraph:
    """
    Build the STRUCTURAL Business Concept Graph — nodes and dependency
    edges only, no per-file confidence. Every dependency is read
    straight from business_concepts.BUSINESS_CONCEPTS
    (required_canonical_fields / optional_canonical_fields), which are
    themselves derived from each concept's per-sector `sources` dict.
    Nothing here re-lists a canonical field or alias of its own.
    """
    graph = BusinessConceptGraph()

    for concept_id, concept in BUSINESS_CONCEPTS.items():
        node = BusinessConceptNode(
            concept_id=concept_id,
            display_name=concept_id.replace('_', ' ').title(),
            description=concept.documentation,
            weight=concept.weight,
            required_canonical_fields=concept.required_canonical_fields,
            optional_canonical_fields=concept.optional_canonical_fields,
        )
        graph.add_node(node)

    for concept_id, concept in BUSINESS_CONCEPTS.items():
        required_set = set(concept.required_canonical_fields)
        for f in concept.required_canonical_fields:
            graph.add_edge(BusinessConceptEdge(
                source=concept_id, target=f, edge_type="field",
                required=True, weight=1.0,
            ))
        for f in concept.optional_canonical_fields:
            if f in required_set:
                continue
            graph.add_edge(BusinessConceptEdge(
                source=concept_id, target=f, edge_type="field",
                required=False, weight=0.5,
            ))

    return graph


# Module-level singleton — the structure never changes at runtime
# (BUSINESS_CONCEPTS is a static registry), so build it once.
CONCEPT_GRAPH = build_concept_graph()


# ══════════════════════════════════════════════════════════════════
# PER-FILE CONFIDENCE RESOLUTION
# ══════════════════════════════════════════════════════════════════

def resolve_graph_confidence(df_input: pd.DataFrame, sector: str) -> BusinessConceptGraph:
    """
    Return a per-input-file COPY of CONCEPT_GRAPH with confidence,
    resolved_fields, and missing_fields populated for `sector` against
    `df_input`. Read-only with respect to df_input, business_concepts.py
    and schema_resolution.py.
    """
    graph = copy.deepcopy(CONCEPT_GRAPH)

    _, resolutions = resolve_schema(df_input)
    resolved_field_confidence: dict[str, float] = {}
    for r in resolutions:
        if r.canonical_field is None:
            continue
        prev = resolved_field_confidence.get(r.canonical_field, 0.0)
        resolved_field_confidence[r.canonical_field] = max(prev, r.confidence)

    primary_local_confidence: dict[str, float | None] = {}
    for concept_id, concept in BUSINESS_CONCEPTS.items():
        source = concept.sources.get(sector)
        if source is None:
            primary_local_confidence[concept_id] = None
            continue
        field_conf = resolved_field_confidence.get(source.canonical_field, 0.0)
        primary_local_confidence[concept_id] = (
            round(source.confidence * field_conf, 4) if field_conf else 0.0
        )

    graph.propagate_confidence(primary_local_confidence, resolved_field_confidence)
    for node in graph.nodes.values():
        node.metadata['sector'] = sector
    return graph


# ══════════════════════════════════════════════════════════════════
# PART 5 — MERMAID GRAPH GENERATION
# ══════════════════════════════════════════════════════════════════

def _mermaid_id(name: str) -> str:
    return name.replace(' ', '').replace('_', '')


def to_mermaid(graph: "BusinessConceptGraph | None" = None) -> str:
    """
    Generate the `graph TD` Mermaid source for a BusinessConceptGraph
    (defaults to the structural CONCEPT_GRAPH singleton). Regenerate
    business_concept_graph.md from this function's output whenever
    BUSINESS_CONCEPTS changes, so the doc always matches the
    implemented graph (Part 5 / Part 9 requirement) — do not hand-edit
    the Mermaid block in that file.
    """
    g = graph or CONCEPT_GRAPH
    lines = ["graph TD"]
    for concept_id, node in g.nodes.items():
        lines.append(f'    {_mermaid_id(concept_id)}["{node.display_name}"]')
    for concept_id, node in g.nodes.items():
        cid = _mermaid_id(concept_id)
        for edge in g.field_edges_for(concept_id):
            fid = _mermaid_id(edge.target)
            if edge.required:
                lines.append(f'    {cid} --> {fid}["{edge.target}"]')
            else:
                lines.append(f'    {cid} -.->|optional| {fid}["{edge.target}"]')
    return "\n".join(lines)
