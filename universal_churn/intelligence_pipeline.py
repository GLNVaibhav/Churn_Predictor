"""Composition root for UCIF's typed intelligence pipeline.

It owns orchestration only: all inference rules remain in their respective
intelligence modules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
import pandas as pd

from .business_meaning import BusinessMeaning, infer_business_meanings
from .canonical_mapping import CanonicalMappingResult, infer_canonical_mapping
from .context_validation import ContextValidation, validate_context
from .coverage import CoverageResult, infer_coverage
from .routing import RoutingResult, infer_routing
from .semantic_graph import SemanticKnowledgeGraph, infer_semantic_knowledge_graph
from .semantic_schema import profile_column


@dataclass(frozen=True)
class IntelligenceResult:
    business_meanings: tuple[BusinessMeaning, ...]
    context: ContextValidation
    semantic_graph: SemanticKnowledgeGraph
    canonical_mapping: CanonicalMappingResult
    coverage: CoverageResult
    routing: RoutingResult
    stage_timings: dict[str, float] = field(default_factory=dict)


def infer_intelligence(df: pd.DataFrame) -> IntelligenceResult:
    """Compose the existing typed Business Meaning through Routing APIs."""
    started = perf_counter()
    profiles = [profile_column(column, df[column]) for column in df.columns]
    meanings = tuple(infer_business_meanings(profiles))
    timings = {"business_meaning": perf_counter() - started}
    started = perf_counter()
    context = validate_context(list(meanings))
    timings["context_validation"] = perf_counter() - started
    started = perf_counter()
    graph = infer_semantic_knowledge_graph(list(meanings), context)
    timings["semantic_graph"] = perf_counter() - started
    started = perf_counter()
    mapping = infer_canonical_mapping(list(meanings), context, graph)
    timings["canonical_mapping"] = perf_counter() - started
    started = perf_counter()
    coverage = infer_coverage(list(meanings), context, graph, mapping)
    timings["coverage"] = perf_counter() - started
    started = perf_counter()
    routing = infer_routing(list(meanings), context, graph, mapping, coverage)
    timings["routing"] = perf_counter() - started
    return IntelligenceResult(meanings, context, graph, mapping, coverage, routing, timings)

