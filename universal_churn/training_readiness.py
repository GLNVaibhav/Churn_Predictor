"""Read-only V2 training-readiness reporting for canonical feature sets."""
from __future__ import annotations

from dataclasses import dataclass

from .canonical_feature_builder import CanonicalFeatureSet
from .compatibility_intelligence import CompatibilityAssessment


@dataclass(frozen=True)
class TrainingReadinessReport:
    sector: str
    canonical_coverage: float
    derived_features: tuple[str, ...]
    unsupported_concepts: tuple[str, ...]
    missing_business_concepts: tuple[str, ...]
    confidence_distribution: dict[str, int]
    feature_provenance: dict[str, tuple[str, ...]]
    compatibility: CompatibilityAssessment


def build_training_readiness_report(
    feature_set: CanonicalFeatureSet, compatibility: CompatibilityAssessment,
) -> TrainingReadinessReport:
    buckets = {"high": 0, "medium": 0, "low": 0, "missing": 0}
    provenance = {}
    for feature in feature_set.features:
        if feature.status == "Unsupported": buckets["missing"] += 1
        elif feature.confidence >= 0.75: buckets["high"] += 1
        elif feature.confidence >= 0.50: buckets["medium"] += 1
        else: buckets["low"] += 1
        provenance[feature.name] = tuple(source.source_column for source in feature.provenance)
    missing = tuple(item.name for item in feature_set.features if item.status == "Unsupported")
    return TrainingReadinessReport(
        sector=feature_set.sector, canonical_coverage=feature_set.canonical_coverage,
        derived_features=tuple(item.name for item in feature_set.features if item.status == "Derived"),
        unsupported_concepts=missing, missing_business_concepts=missing,
        confidence_distribution=buckets, feature_provenance=provenance,
        compatibility=compatibility,
    )
