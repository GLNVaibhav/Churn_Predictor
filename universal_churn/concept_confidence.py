"""
universal_churn.concept_confidence
====================================
Concept Confidence Engine — Phase 4 of the Schema Intelligence Layer.

Answers a different question than coverage.py does:

    coverage.py         : are the ENGINEERED FEATURES a sector model
                           expects present and usable?
    concept_confidence   : how well can the underlying, sector-
                           independent BUSINESS CONCEPTS (concepts.py)
                           be reconstructed from whatever columns THIS
                           input file actually has?

A file can score well here (e.g. it clearly has a recurring-cost-like
column and a tenure-like column, just under unfamiliar names) even if
it fails strict sector coverage — which is exactly the situation the
Business Concept Layer (schema_resolution.py + concepts.py) already
exists to handle, but which nothing was reading yet.

This module does NOT replace or modify coverage.py's scoring, and it
does NOT change schema_resolution.py or concepts.py — it is a pure
read-only consumer of both, per "every module has a single
responsibility."

Derivation (Version 7, Chunk 2 update)
----------------------------------------
Internally, per-concept confidence is now computed by
business_concept_graph.py's BusinessConceptGraph instead of an
isolated per-concept calculation — see that module's docstring for the
full graph-propagation policy. The PUBLIC interface below
(compute_concept_confidence, ConceptConfidenceReport,
ConceptConfidenceEntry, print_concept_confidence_report,
MIN_RECONSTRUCTABLE_OVERALL_CONFIDENCE) is UNCHANGED — coverage.py and
routing.py require zero changes, per "No API changes."

For every BusinessConcept in concepts.BUSINESS_CONCEPTS:

    1. Does `sector` have a documented ConceptSource for this concept?
       (concept.sources.get(sector))  -- if not: the graph now checks
       whether any OTHER canonical field this concept graph-depends on
       (possibly documented for a different sector) resolved anyway in
       this file, and gives partial credit if so; otherwise confidence
       0.0, reconstructable = False, reason = "no documented source"
       (identical to the pre-graph result whenever nothing else in the
       graph resolves either).

    2. Did the canonical field that source depends on
       (source.canonical_field) actually resolve from THIS file's raw
       columns?  Determined via schema_resolution.resolve_schema(),
       which reports HOW each raw column resolved (exact / regex /
       unresolved) and at what confidence (1.0 / 0.8 / 0.0).
       If it never resolved: the graph again attempts partial recovery
       via the concept's other documented fields before falling back
       to confidence 0.0 (identical to pre-graph behaviour if nothing
       else resolves).

    3. Otherwise (primary field resolved normally — the common case,
       UNCHANGED from before the graph):
           concept_confidence = source.confidence * resolution.confidence
       i.e. how good a proxy the sector's mapping is (source.confidence)
       combined with how sure we are the raw column really IS that
       canonical field (resolution.confidence).

Overall Concept Confidence is the mean across every concept in the
registry (unavailable concepts count as 0.0, matching the "how much of
our business vocabulary can we actually speak for this file" framing
used in the architecture spec).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .concepts import BUSINESS_CONCEPTS, CONCEPT_NAMES
from .schema_resolution import resolve_schema
from .business_concept_graph import resolve_graph_confidence


# Below this overall confidence (with zero reconstructable concepts
# excluded already via reconstructable_concepts == 0), we consider the
# business concepts effectively unreconstructable for routing purposes.
# This is intentionally low — Phase 5's policy is "don't reject just
# because feature COUNT is low", so this only trips when almost
# nothing in the file maps to anything we understand.
MIN_RECONSTRUCTABLE_OVERALL_CONFIDENCE = 0.15


@dataclass
class ConceptConfidenceEntry:
    concept: str
    confidence: float
    reconstructable: bool
    reason: str
    canonical_field: str | None = None
    source_confidence: float | None = None
    resolution_confidence: float | None = None


@dataclass
class ConceptConfidenceReport:
    sector: str
    per_concept: dict[str, ConceptConfidenceEntry] = field(default_factory=dict)
    overall_confidence: float = 0.0
    reconstructable_concepts: int = 0
    total_concepts: int = 0
    concepts_reconstructable: bool = False  # >= MIN_RECONSTRUCTABLE_OVERALL_CONFIDENCE
                                             # AND at least one concept reconstructed

    def to_dict(self) -> dict:
        """
        Plain-dict shape consumed by coverage.py (embedded in its
        return dict) and by routing.py's CoverageResult adapter.
        """
        return {
            'sector'                  : self.sector,
            'per_concept'             : {
                name: {
                    'confidence'            : e.confidence,
                    'reconstructable'       : e.reconstructable,
                    'reason'                : e.reason,
                    'canonical_field'       : e.canonical_field,
                    'source_confidence'     : e.source_confidence,
                    'resolution_confidence' : e.resolution_confidence,
                }
                for name, e in self.per_concept.items()
            },
            'overall_confidence'      : self.overall_confidence,
            'reconstructable_concepts': self.reconstructable_concepts,
            'total_concepts'          : self.total_concepts,
            'concepts_reconstructable': self.concepts_reconstructable,
        }


def compute_concept_confidence(df_input: pd.DataFrame, sector: str) -> ConceptConfidenceReport:
    """
    Compute the Concept Confidence Report for one input file + sector.

    Read-only: does not mutate df_input, does not touch coverage.py,
    does not touch concepts.py or schema_resolution.py.

    Internally delegates to business_concept_graph.resolve_graph_confidence()
    for the actual per-concept number (Version 7, Chunk 2) — this
    function's job is now just to translate the graph's per-node result
    into the same ConceptConfidenceReport/ConceptConfidenceEntry shape
    every existing caller (coverage.py, tests) already expects.
    """
    _, resolutions = resolve_schema(df_input)

    # A canonical field may have resolved from more than one raw column
    # (rare, but possible with messy exports) — keep the best (highest
    # confidence) resolution seen for each canonical field name.
    best_resolution_confidence: dict[str, float] = {}
    for r in resolutions:
        if r.canonical_field is None:
            continue
        prev = best_resolution_confidence.get(r.canonical_field, 0.0)
        best_resolution_confidence[r.canonical_field] = max(prev, r.confidence)

    graph = resolve_graph_confidence(df_input, sector)

    per_concept: dict[str, ConceptConfidenceEntry] = {}

    for concept_name in CONCEPT_NAMES:
        concept = BUSINESS_CONCEPTS[concept_name]
        source = concept.sources.get(sector)
        graph_node = graph.get_node(concept_name)

        if source is None:
            if graph_node is not None and graph_node.confidence > 0.0:
                # Graph partial recovery (Part 3): some OTHER
                # canonical field this concept depends on (documented
                # for a different sector) resolved anyway in this file.
                per_concept[concept_name] = ConceptConfidenceEntry(
                    concept=concept_name, confidence=graph_node.confidence,
                    reconstructable=True,
                    reason=(
                        f"No documented business-concept source for sector "
                        f"'{sector}', but partially reconstructed via graph "
                        f"fallback field(s): {graph_node.resolved_fields}."
                    ),
                )
            else:
                per_concept[concept_name] = ConceptConfidenceEntry(
                    concept=concept_name, confidence=0.0, reconstructable=False,
                    reason=f"No documented business-concept source for sector '{sector}'.",
                )
            continue

        resolution_confidence = best_resolution_confidence.get(source.canonical_field, 0.0)

        if resolution_confidence == 0.0:
            if graph_node is not None and graph_node.confidence > 0.0:
                per_concept[concept_name] = ConceptConfidenceEntry(
                    concept=concept_name, confidence=graph_node.confidence,
                    reconstructable=True,
                    reason=(
                        f"Canonical field '{source.canonical_field}' did not "
                        f"resolve, but partially reconstructed via graph "
                        f"fallback field(s): {graph_node.resolved_fields}."
                    ),
                    canonical_field=source.canonical_field,
                    source_confidence=source.confidence,
                    resolution_confidence=0.0,
                )
                continue
            per_concept[concept_name] = ConceptConfidenceEntry(
                concept=concept_name, confidence=0.0, reconstructable=False,
                reason=(
                    f"Canonical field '{source.canonical_field}' did not "
                    f"resolve from any column in this input."
                ),
                canonical_field=source.canonical_field,
                source_confidence=source.confidence,
                resolution_confidence=0.0,
            )
            continue

        combined = round(source.confidence * resolution_confidence, 4)
        per_concept[concept_name] = ConceptConfidenceEntry(
            concept=concept_name, confidence=combined, reconstructable=True,
            reason="Reconstructed from resolved canonical field.",
            canonical_field=source.canonical_field,
            source_confidence=source.confidence,
            resolution_confidence=resolution_confidence,
        )

    total = len(per_concept)
    scores = [e.confidence for e in per_concept.values()]
    overall = round(sum(scores) / total, 4) if total else 0.0
    reconstructable_count = sum(1 for e in per_concept.values() if e.reconstructable)

    concepts_reconstructable = (
        reconstructable_count > 0 and overall >= MIN_RECONSTRUCTABLE_OVERALL_CONFIDENCE
    )

    return ConceptConfidenceReport(
        sector=sector,
        per_concept=per_concept,
        overall_confidence=overall,
        reconstructable_concepts=reconstructable_count,
        total_concepts=total,
        concepts_reconstructable=concepts_reconstructable,
    )


def print_concept_confidence_report(report: ConceptConfidenceReport | dict) -> None:
    """Human-readable report, same visual style as coverage.py / quality_gate.py."""
    d = report.to_dict() if isinstance(report, ConceptConfidenceReport) else report
    sep = '─' * 60
    print(f"\n{sep}")
    print(f"  CONCEPT CONFIDENCE REPORT  [{d['sector'].upper()}]")
    print(sep)
    print(f"  Overall Concept Confidence : {d['overall_confidence']*100:.1f}%")
    print(f"  Reconstructable concepts   : {d['reconstructable_concepts']}/{d['total_concepts']}")
    print(f"  Concepts reconstructable   : {'✔ Yes' if d['concepts_reconstructable'] else '✖ No'}")
    print()
    for name, entry in d['per_concept'].items():
        mark = '✔' if entry['reconstructable'] else '✖'
        print(f"    {mark} {name:<22} {entry['confidence']*100:5.1f}%   {entry['reason']}")
    print(sep)
