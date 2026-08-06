"""Additive readiness assessment for legacy and future universal models."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .canonical_feature_builder import CanonicalFeatureSet


class CompatibilityLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INCOMPATIBLE = "INCOMPATIBLE"


@dataclass(frozen=True)
class CompatibilityAssessment:
    future_universal_model: CompatibilityLevel
    legacy_sector_model: CompatibilityLevel | None
    canonical_coverage: float
    confidence_coverage: float
    available_features: tuple[str, ...]
    derived_features: tuple[str, ...]
    unsupported_features: tuple[str, ...]
    reasoning: tuple[str, ...]


def _level(coverage: float, confidence: float) -> CompatibilityLevel:
    score = 0.65 * coverage + 0.35 * confidence
    if coverage >= 0.80 and confidence >= 0.70: return CompatibilityLevel.HIGH
    if score >= 0.60: return CompatibilityLevel.MEDIUM
    if score >= 0.35: return CompatibilityLevel.LOW
    return CompatibilityLevel.INCOMPATIBLE


def evaluate_compatibility(
    feature_set: CanonicalFeatureSet,
    *,
    legacy_required_features: Iterable[str] | None = None,
) -> CompatibilityAssessment:
    """Assess suitability without changing any routing or model selection.

    Legacy compatibility is only evaluated if its explicit historical feature
    schema is supplied.  V2 canonical feature names must not be assumed to
    stand in for legacy dataset columns.
    """
    available = tuple(item.name for item in feature_set.features if item.status == "Available")
    derived = tuple(item.name for item in feature_set.features if item.status == "Derived")
    unsupported = tuple(item.name for item in feature_set.features if item.status == "Unsupported")
    confidence = (sum(item.confidence for item in feature_set.features) / len(feature_set.features)) if feature_set.features else 0.0
    future = _level(feature_set.canonical_coverage, confidence)
    reasoning = [f"Future-universal canonical coverage={feature_set.canonical_coverage:.1%}; mean feature confidence={confidence:.1%}."]
    legacy = None
    if legacy_required_features is not None:
        required = set(legacy_required_features)
        raw_sources = {source.source_column for item in feature_set.features for source in item.provenance}
        legacy_coverage = len(required & raw_sources) / len(required) if required else 1.0
        legacy = _level(legacy_coverage, confidence)
        reasoning.append(f"Legacy schema source coverage={legacy_coverage:.1%}; canonical features were not substituted for legacy columns.")
    else:
        reasoning.append("Legacy compatibility not evaluated: no explicit legacy feature schema supplied.")
    return CompatibilityAssessment(future, legacy, feature_set.canonical_coverage, confidence, available, derived, unsupported, tuple(reasoning))
