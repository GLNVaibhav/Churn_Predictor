"""Additive V2 canonical business-feature construction.

This module is deliberately not imported by V1 prediction or routing paths.
It projects recognised business concepts into sector-stable training features;
it never attempts to populate a legacy model's dataset-specific columns.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

from .business_meaning import BusinessMeaning
from .canonical_mapping import CanonicalMappingResult
from .coverage import CoverageResult
from .semantic_graph import SemanticKnowledgeGraph


@dataclass(frozen=True)
class CanonicalFeatureSpecification:
    name: str
    description: str
    required_evidence: tuple[str, ...]
    optional_evidence: tuple[str, ...]
    derivation_strategy: str
    confidence_rules: dict[str, float]
    supported_raw_concepts: tuple[str, ...]


@dataclass(frozen=True)
class CanonicalFeatureProvenance:
    source_column: str
    business_concept: str
    canonical_concept: str
    confidence: float


@dataclass(frozen=True)
class CanonicalFeatureValue:
    name: str
    value: pd.Series
    confidence: float
    provenance: tuple[CanonicalFeatureProvenance, ...]
    supporting_evidence: tuple[str, ...]
    derivation_method: str
    status: str  # Available | Derived | Unsupported


@dataclass(frozen=True)
class CanonicalFeatureSet:
    sector: str
    features: tuple[CanonicalFeatureValue, ...]
    canonical_coverage: float
    available_count: int
    derived_count: int
    unsupported_count: int
    source_coverage: float
    graph_consistency: float

    def feature(self, name: str) -> CanonicalFeatureValue:
        return next(item for item in self.features if item.name == name)


def _knowledge_root() -> Path:
    return Path(__file__).resolve().parent.parent / "knowledge"


@lru_cache(maxsize=None)
def load_canonical_feature_specifications(sector: str) -> tuple[CanonicalFeatureSpecification, ...]:
    """Load a sector's V2 feature contract without affecting V1 knowledge loading."""
    path = _knowledge_root() / sector.lower() / "canonical_features.yaml"
    if not path.is_file():
        raise ValueError(f"No canonical feature specification for sector '{sector}'.")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    specifications = []
    for name, definition in payload.items():
        definition = definition or {}
        specifications.append(CanonicalFeatureSpecification(
            name=str(name), description=str(definition.get("description", "")),
            required_evidence=tuple(map(str, definition.get("required_evidence", []))),
            optional_evidence=tuple(map(str, definition.get("optional_evidence", []))),
            derivation_strategy=str(definition.get("derivation_strategy", "direct_or_mean_numeric")),
            confidence_rules={str(key): float(value) for key, value in (definition.get("confidence_rules", {}) or {}).items()},
            supported_raw_concepts=tuple(map(str, definition.get("supported_raw_concepts", []))),
        ))
    return tuple(specifications)


def _numeric_or_category(values: list[pd.Series], strategy: str, index: pd.Index) -> pd.Series:
    if not values:
        return pd.Series(np.nan, index=index, dtype=float)
    if strategy == "categorical_first":
        return values[0].astype("string")
    numeric = [pd.to_numeric(value, errors="coerce") for value in values]
    if strategy == "binary_any":
        binary = [value.astype(str).str.strip().str.lower().isin({"yes", "true", "1", "y"}).astype(float) for value in values]
        return pd.concat(binary, axis=1).max(axis=1)
    return pd.concat(numeric, axis=1).mean(axis=1)


def build_canonical_feature_set(
    raw_df: pd.DataFrame,
    business_meanings: Iterable[BusinessMeaning],
    canonical_mapping: CanonicalMappingResult,
    semantic_graph: SemanticKnowledgeGraph,
    coverage: CoverageResult,
    *,
    sector: str,
) -> CanonicalFeatureSet:
    """Build a V2 feature set from auditable semantic evidence.

    ``required_evidence`` entries are alternatives: a feature is supported
    when at least one recognised concept is present.  No defaults or
    dataset-name rules are introduced; unsupported features remain missing.
    """
    meanings = tuple(business_meanings)
    mappings = tuple(canonical_mapping.mappings)
    if len(raw_df.columns) != len(meanings) or len(meanings) != len(mappings):
        raise ValueError("Raw columns, BusinessMeanings, and canonical mappings must be aligned.")
    rows = tuple(zip(raw_df.columns, meanings, mappings))
    graph_factor = float(semantic_graph.consistency_score)
    coverage_factor = float(coverage.summary.confidence_coverage)
    values: list[CanonicalFeatureValue] = []

    for specification in load_canonical_feature_specifications(sector):
        supported = set(specification.supported_raw_concepts)
        evidence = [
            (str(column), meaning, mapping)
            for column, meaning, mapping in rows
            if meaning.primary_business_concept in supported
            or mapping.chosen_concept.name in supported
        ]
        sources = [raw_df[column] for column, _, _ in evidence]
        provenance = tuple(CanonicalFeatureProvenance(
            source_column=column,
            business_concept=meaning.primary_business_concept,
            canonical_concept=mapping.chosen_concept.name,
            confidence=float(mapping.confidence),
        ) for column, meaning, mapping in evidence)
        result = _numeric_or_category(sources, specification.derivation_strategy, raw_df.index)
        direct = len(evidence) == 1
        status = "Unsupported" if not evidence else ("Available" if direct else "Derived")
        mapping_confidence = float(np.mean([entry.confidence for entry in provenance])) if provenance else 0.0
        base = specification.confidence_rules.get("direct" if direct else "derived", 0.0)
        confidence = min(mapping_confidence, base) * (0.8 + 0.1 * graph_factor + 0.1 * coverage_factor) if evidence else 0.0
        confidence = max(0.0, min(1.0, confidence))
        values.append(CanonicalFeatureValue(
            name=specification.name, value=result, confidence=confidence,
            provenance=provenance,
            supporting_evidence=tuple(entry.business_concept for entry in provenance),
            derivation_method=specification.derivation_strategy,
            status=status,
        ))

    available = sum(item.status == "Available" for item in values)
    derived = sum(item.status == "Derived" for item in values)
    unsupported = len(values) - available - derived
    resolved = available + derived
    return CanonicalFeatureSet(
        sector=sector.lower(), features=tuple(values),
        canonical_coverage=resolved / len(values) if values else 0.0,
        available_count=available, derived_count=derived, unsupported_count=unsupported,
        source_coverage=coverage_factor, graph_consistency=graph_factor,
    )
