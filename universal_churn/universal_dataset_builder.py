"""V2 construction of confidence-aware, sector-canonical training datasets.

This module is intentionally isolated from all V1 prediction and inference
paths.  It prepares governed inputs for a *future* universal sector model and
does not train, load, or alter any existing model artifact.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping
import json

import pandas as pd

from .canonical_feature_builder import (
    CanonicalFeatureSet,
    CanonicalFeatureValue,
    build_canonical_feature_set,
    load_canonical_feature_specifications,
)
from .compatibility_intelligence import CompatibilityAssessment, CompatibilityLevel, evaluate_compatibility
from .intelligence_pipeline import infer_intelligence
from .training_readiness import TrainingReadinessReport, build_training_readiness_report


class DatasetReadiness(str, Enum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class DatasetInput:
    """One training candidate.  Target selection is explicit and never guessed."""
    name: str
    dataframe: pd.DataFrame
    target_column: str


@dataclass(frozen=True)
class DatasetValidationConfig:
    minimum_coverage: float = 0.60
    minimum_mean_confidence: float = 0.40
    maximum_derived_ratio: float = 0.60
    critical_features: tuple[str, ...] = ()
    allow_partial: bool = True


@dataclass(frozen=True)
class DatasetValidationResult:
    dataset_name: str
    readiness: DatasetReadiness
    accepted: bool
    canonical_coverage: float
    mean_feature_confidence: float
    derived_feature_ratio: float
    missing_critical_concepts: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class DatasetQualityReport:
    dataset_name: str
    sector: str
    rows: int
    canonical_coverage: float
    training_readiness: DatasetReadiness
    compatibility: CompatibilityLevel
    derived_features: tuple[str, ...]
    unsupported_features: tuple[str, ...]
    confidence_distribution: dict[str, int]
    rejected_features: tuple[str, ...]
    accepted_features: tuple[str, ...]
    validation_reasons: tuple[str, ...]


@dataclass(frozen=True)
class DatasetBuildResult:
    input: DatasetInput
    feature_set: CanonicalFeatureSet
    compatibility: CompatibilityAssessment
    readiness_report: TrainingReadinessReport
    validation: DatasetValidationResult
    quality_report: DatasetQualityReport


@dataclass(frozen=True)
class CanonicalTrainingDataset:
    """Unified V2 training representation with no raw feature columns.

    ``feature_provenance`` retains full in-memory provenance, including source
    columns.  The CSV exporter intentionally emits semantic provenance only,
    so raw enterprise column names never leave this governed object.
    """
    sector: str
    rows: pd.DataFrame
    canonical_features: tuple[str, ...]
    feature_confidence: pd.DataFrame
    feature_provenance: Mapping[str, Mapping[str, tuple[object, ...]]]
    dataset_reports: tuple[DatasetQualityReport, ...]
    validation_results: tuple[DatasetValidationResult, ...]
    accepted_origins: tuple[str, ...]
    rejected_origins: tuple[str, ...]

    def export_csv(self, path: str | Path) -> Path:
        """Export canonical values and safe metadata; never raw feature names."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.rows.to_csv(destination, index=False)
        return destination

    def quality_report_dict(self) -> dict[str, object]:
        return {
            "sector": self.sector,
            "accepted_origins": list(self.accepted_origins),
            "rejected_origins": list(self.rejected_origins),
            "datasets": [
                {
                    "dataset_name": report.dataset_name, "sector": report.sector,
                    "rows": report.rows, "canonical_coverage": report.canonical_coverage,
                    "training_readiness": report.training_readiness.value,
                    "compatibility": report.compatibility.value,
                    "derived_features": list(report.derived_features),
                    "unsupported_features": list(report.unsupported_features),
                    "confidence_distribution": report.confidence_distribution,
                    "rejected_features": list(report.rejected_features),
                    "accepted_features": list(report.accepted_features),
                    "validation_reasons": list(report.validation_reasons),
                } for report in self.dataset_reports
            ],
        }

    def export_quality_report(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(self.quality_report_dict(), indent=2), encoding="utf-8")
        return destination


def _mean_confidence(feature_set: CanonicalFeatureSet) -> float:
    return sum(item.confidence for item in feature_set.features) / len(feature_set.features) if feature_set.features else 0.0


def validate_dataset(
    name: str, feature_set: CanonicalFeatureSet, compatibility: CompatibilityAssessment,
    config: DatasetValidationConfig,
) -> DatasetValidationResult:
    """Classify a candidate using canonical evidence only."""
    confidence = _mean_confidence(feature_set)
    total = len(feature_set.features) or 1
    derived_ratio = feature_set.derived_count / total
    feature_names = {item.name for item in feature_set.features if item.status != "Unsupported"}
    missing_critical = tuple(sorted(set(config.critical_features) - feature_names))
    reasons: list[str] = []
    if not feature_set.available_count and not feature_set.derived_count:
        readiness = DatasetReadiness.REJECTED
        reasons.append("No canonical business evidence was available.")
    elif missing_critical:
        readiness = DatasetReadiness.INSUFFICIENT
        reasons.append("Missing critical canonical concepts: " + ", ".join(missing_critical) + ".")
    elif feature_set.canonical_coverage < config.minimum_coverage or confidence < config.minimum_mean_confidence:
        readiness = DatasetReadiness.INSUFFICIENT
        reasons.append("Canonical coverage or mean feature confidence is below the configured minimum.")
    elif (
        derived_ratio > config.maximum_derived_ratio
        or compatibility.future_universal_model in {CompatibilityLevel.MEDIUM, CompatibilityLevel.LOW}
    ):
        readiness = DatasetReadiness.PARTIAL
        reasons.append("Dataset relies on a high proportion of derived features or requires medium/low future-model compatibility governance.")
    elif compatibility.future_universal_model is CompatibilityLevel.INCOMPATIBLE:
        readiness = DatasetReadiness.INSUFFICIENT
        reasons.append("Future universal-model compatibility is incompatible.")
    else:
        readiness = DatasetReadiness.READY
        reasons.append("Canonical coverage, confidence, and compatibility meet the configured requirements.")
    accepted = readiness is DatasetReadiness.READY or (readiness is DatasetReadiness.PARTIAL and config.allow_partial)
    return DatasetValidationResult(name, readiness, accepted, feature_set.canonical_coverage, confidence, derived_ratio, missing_critical, tuple(reasons))


def _build_quality_report(
    candidate: DatasetInput, feature_set: CanonicalFeatureSet,
    compatibility: CompatibilityAssessment, readiness: TrainingReadinessReport,
    validation: DatasetValidationResult, sector: str,
) -> DatasetQualityReport:
    return DatasetQualityReport(
        dataset_name=candidate.name, sector=sector, rows=len(candidate.dataframe),
        canonical_coverage=feature_set.canonical_coverage,
        training_readiness=validation.readiness,
        compatibility=compatibility.future_universal_model,
        derived_features=tuple(item.name for item in feature_set.features if item.status == "Derived"),
        unsupported_features=tuple(item.name for item in feature_set.features if item.status == "Unsupported"),
        confidence_distribution=readiness.confidence_distribution,
        rejected_features=tuple(item.name for item in feature_set.features if item.status == "Unsupported"),
        accepted_features=tuple(item.name for item in feature_set.features if item.status != "Unsupported"),
        validation_reasons=validation.reasons,
    )


def analyse_dataset(candidate: DatasetInput, *, sector: str, config: DatasetValidationConfig) -> DatasetBuildResult:
    """Run the existing intelligence stages plus additive V2 governance."""
    if candidate.target_column not in candidate.dataframe.columns:
        raise ValueError(f"Target column '{candidate.target_column}' is absent from dataset '{candidate.name}'.")
    intelligence = infer_intelligence(candidate.dataframe)
    feature_set = build_canonical_feature_set(
        candidate.dataframe, intelligence.business_meanings, intelligence.canonical_mapping,
        intelligence.semantic_graph, intelligence.coverage, sector=sector,
    )
    compatibility = evaluate_compatibility(feature_set)
    readiness = build_training_readiness_report(feature_set, compatibility)
    validation = validate_dataset(candidate.name, feature_set, compatibility, config)
    quality = _build_quality_report(candidate, feature_set, compatibility, readiness, validation, sector.lower())
    return DatasetBuildResult(candidate, feature_set, compatibility, readiness, validation, quality)


def _safe_semantic_provenance(feature: CanonicalFeatureValue) -> str:
    """Preserve semantic evidence in exports without exporting raw field names."""
    return json.dumps([
        {"business_concept": source.business_concept, "canonical_concept": source.canonical_concept,
         "confidence": source.confidence}
        for source in feature.provenance
    ], separators=(",", ":"))


def build_universal_training_dataset(
    datasets: Iterable[DatasetInput], *, sector: str,
    validation_config: DatasetValidationConfig | None = None,
) -> CanonicalTrainingDataset:
    """Align accepted datasets into one sector-stable canonical training frame."""
    config = validation_config or DatasetValidationConfig()
    canonical_features = tuple(spec.name for spec in load_canonical_feature_specifications(sector))
    results = tuple(analyse_dataset(item, sector=sector, config=config) for item in datasets)
    frames: list[pd.DataFrame] = []
    confidences: list[pd.DataFrame] = []
    provenance: dict[str, dict[str, tuple[object, ...]]] = {}
    accepted, rejected = [], []
    for result in results:
        if not result.validation.accepted:
            rejected.append(result.input.name)
            continue
        accepted.append(result.input.name)
        features = {item.name: item for item in result.feature_set.features}
        frame = pd.DataFrame({name: features[name].value.reset_index(drop=True) for name in canonical_features})
        # Target is deliberately generic in the universal contract.  The
        # original target column name never enters the export.
        frame["Target"] = result.input.dataframe[result.input.target_column].reset_index(drop=True)
        frame["DatasetOrigin"] = result.input.name
        frame["CanonicalCoverage"] = result.feature_set.canonical_coverage
        frame["TrainingReadiness"] = result.validation.readiness.value
        frame["CompatibilityLevel"] = result.compatibility.future_universal_model.value
        confidence = pd.DataFrame({f"Confidence__{name}": features[name].confidence for name in canonical_features}, index=frame.index)
        metadata = pd.DataFrame({
            f"Derivation__{name}": features[name].derivation_method for name in canonical_features
        }, index=frame.index)
        semantic = pd.DataFrame({
            f"Provenance__{name}": _safe_semantic_provenance(features[name]) for name in canonical_features
        }, index=frame.index)
        frames.append(pd.concat([frame, confidence, metadata, semantic], axis=1))
        confidences.append(confidence)
        provenance[result.input.name] = {name: features[name].provenance for name in canonical_features}
    output_columns = list(canonical_features) + ["Target", "DatasetOrigin", "CanonicalCoverage", "TrainingReadiness", "CompatibilityLevel"]
    metadata_columns = [f"Confidence__{name}" for name in canonical_features] + [f"Derivation__{name}" for name in canonical_features] + [f"Provenance__{name}" for name in canonical_features]
    rows = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=output_columns + metadata_columns)
    feature_confidence = pd.concat(confidences, ignore_index=True) if confidences else pd.DataFrame(columns=[f"Confidence__{name}" for name in canonical_features])
    return CanonicalTrainingDataset(
        sector=sector.lower(), rows=rows, canonical_features=canonical_features,
        feature_confidence=feature_confidence, feature_provenance=provenance,
        dataset_reports=tuple(item.quality_report for item in results),
        validation_results=tuple(item.validation for item in results),
        accepted_origins=tuple(accepted), rejected_origins=tuple(rejected),
    )
