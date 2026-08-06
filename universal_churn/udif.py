"""Read-only structured diagnostics for the Universal Debug Intelligence Framework.

This module deliberately contains collection and analysis only.  Presentation lives
in :mod:`universal_churn.udif_rendering`, allowing the same immutable diagnostic
models to be exported as JSON in a future interface without changing collection.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd


class DiagnosticLevel(str, Enum):
    OFF = "off"
    STANDARD = "standard"
    RESEARCH = "research"


@dataclass(frozen=True)
class SemanticConceptDiagnostic:
    original_column: str
    business_concept: str
    canonical_concept: str
    confidence: float
    mapping_reason: str


@dataclass(frozen=True)
class SemanticIntelligenceDiagnostic:
    rows: int
    columns: int
    sector: str
    business_confidence: float
    concepts: tuple[SemanticConceptDiagnostic, ...]


@dataclass(frozen=True)
class CanonicalFeatureDiagnostic:
    original_column: str
    canonical_feature: str
    confidence: float
    reason: str


@dataclass(frozen=True)
class CanonicalMappingDiagnostic:
    mapped_features: tuple[CanonicalFeatureDiagnostic, ...]
    missing_features: tuple[str, ...]
    coverage_score: float
    coverage_confidence: float
    readiness: str


@dataclass(frozen=True)
class FeatureMatrixDiagnostic:
    rows: int
    columns: int
    column_names: tuple[str, ...]
    missing_values: int
    constant_columns: tuple[str, ...]
    near_constant_columns: tuple[str, ...]
    numeric_standard_deviations: tuple[tuple[str, float], ...]
    first_five_rows: tuple[tuple[Any, ...], ...]


@dataclass(frozen=True)
class FeatureProvenanceDiagnostic:
    feature: str
    canonical_concepts: tuple[str, ...]
    resolved_from: tuple[str | None, ...]
    confidence: tuple[float, ...]
    transformation: str
    status: str
    reason: str | None


@dataclass(frozen=True)
class PredictionCoverageDiagnostic:
    score: float
    resolved: int
    derived: int
    compatibility: int
    default: int
    intentional_neutral: int


@dataclass(frozen=True)
class ModelInputHealthDiagnostic:
    rows: int
    columns: int
    duplicate_rows: int
    missing_values: int
    constant_features: tuple[str, ...]
    near_constant_features: tuple[str, ...]
    variance_summary: tuple[tuple[str, float], ...]
    result: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class HistogramBucket:
    lower: float
    upper: float
    count: int


@dataclass(frozen=True)
class PredictionDiagnostic:
    minimum_probability: float
    maximum_probability: float
    mean_probability: float
    standard_deviation: float
    unique_probability_count: int
    histogram: tuple[HistogramBucket, ...]
    health: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class RootCauseDiagnostic:
    stage: str
    status: str
    evidence: tuple[str, ...]
    recommendation: str | None = None


@dataclass(frozen=True)
class RootCauseAnalysis:
    stages: tuple[RootCauseDiagnostic, ...]


@dataclass
class UDIFRun:
    """Run-scoped, read-only observations. Fields are JSON-export friendly."""
    level: DiagnosticLevel
    semantic: SemanticIntelligenceDiagnostic | None = None
    canonical: CanonicalMappingDiagnostic | None = None
    feature_matrix: FeatureMatrixDiagnostic | None = None
    model_input_health: ModelInputHealthDiagnostic | None = None
    prediction: PredictionDiagnostic | None = None
    feature_provenance: tuple[FeatureProvenanceDiagnostic, ...] = ()
    prediction_coverage: PredictionCoverageDiagnostic | None = None

    def capture_feature_preparation(self, manifest: dict[str, Any]) -> None:
        records = manifest.get('feature_provenance', {})
        diagnostics = []
        for feature, record in records.items():
            sources = tuple(record.sources)
            diagnostics.append(FeatureProvenanceDiagnostic(
                feature=feature, canonical_concepts=tuple(record.concepts),
                resolved_from=tuple(source.source_column for source in sources),
                confidence=tuple(float(source.confidence) for source in sources),
                transformation=record.transformation, status=record.status,
                reason=next((source.reason for source in sources if source.reason), None),
            ))
        self.feature_provenance = tuple(diagnostics)
        statuses = [item.status for item in diagnostics]
        self.prediction_coverage = PredictionCoverageDiagnostic(
            score=float(manifest.get('prediction_coverage', 0.0)),
            resolved=statuses.count('Resolved'), derived=statuses.count('Derived'),
            compatibility=statuses.count('Compatibility'), default=statuses.count('Default'),
            intentional_neutral=statuses.count('Intentional Neutral'),
        )

    def capture_intelligence(self, df: pd.DataFrame, sector: str, intelligence: Any) -> None:
        mappings = intelligence.canonical_mapping.mappings
        concepts = tuple(
            SemanticConceptDiagnostic(
                original_column=str(column),
                business_concept=meaning.primary_business_concept,
                canonical_concept=mapping.chosen_concept.name,
                confidence=float(mapping.confidence),
                mapping_reason=mapping.reasoning,
            )
            for column, meaning, mapping in zip(df.columns, intelligence.business_meanings, mappings)
        )
        confidence = (
            float(np.mean([meaning.confidence for meaning in intelligence.business_meanings]))
            if intelligence.business_meanings else 0.0
        )
        self.semantic = SemanticIntelligenceDiagnostic(
            rows=len(df), columns=len(df.columns), sector=sector,
            business_confidence=confidence, concepts=concepts,
        )
        coverage = intelligence.canonical_mapping.coverage
        mapped = tuple(
            CanonicalFeatureDiagnostic(
                original_column=item.original_column,
                canonical_feature=item.canonical_concept,
                confidence=item.confidence,
                reason=item.mapping_reason,
            ) for item in concepts if item.confidence > 0.0
        )
        missing = tuple(item.original_column for item in concepts if item.confidence <= 0.0)
        self.canonical = CanonicalMappingDiagnostic(
            mapped_features=mapped,
            missing_features=missing,
            coverage_score=float(coverage.completeness),
            coverage_confidence=float(intelligence.canonical_mapping.overall_confidence),
            readiness=intelligence.coverage.summary.readiness,
        )

    def capture_model_input(self, matrix: Any, column_names: list[str] | tuple[str, ...] | None = None) -> None:
        frame = _as_frame(matrix, column_names)
        numeric = frame.select_dtypes(include=[np.number])
        std = numeric.std(ddof=0).replace([np.inf, -np.inf], np.nan)
        constants = tuple(str(name) for name in frame.columns if frame[name].nunique(dropna=False) <= 1)
        near_constants = tuple(
            str(name) for name, value in std.items()
            if name not in constants and pd.notna(value) and float(value) < 1e-8
        )
        variance = tuple((str(name), float(value)) for name, value in std.items() if pd.notna(value))
        preview = tuple(tuple(_json_scalar(value) for value in row) for row in frame.head(5).itertuples(index=False, name=None))
        self.feature_matrix = FeatureMatrixDiagnostic(
            rows=len(frame), columns=len(frame.columns),
            column_names=tuple(map(str, frame.columns)), missing_values=int(frame.isna().sum().sum()),
            constant_columns=constants, near_constant_columns=near_constants,
            numeric_standard_deviations=variance, first_five_rows=preview,
        )
        reasons: list[str] = []
        result = "PASS"
        if len(frame) == 0 or len(frame.columns) == 0:
            result = "FAIL"; reasons.append("Final model input has zero rows or zero columns.")
        elif self.feature_matrix.missing_values:
            result = "FAIL"; reasons.append(f"{self.feature_matrix.missing_values} missing values are present in final model input.")
        elif constants or near_constants or int(frame.duplicated().sum()):
            result = "WARNING"
            if constants: reasons.append(f"{len(constants)} constant feature(s) measured.")
            if near_constants: reasons.append(f"{len(near_constants)} near-constant feature(s) measured.")
            duplicates = int(frame.duplicated().sum())
            if duplicates: reasons.append(f"{duplicates} duplicate model-input row(s) measured.")
        else:
            reasons.append("No missing, constant, near-constant, or duplicate model-input conditions measured.")
        self.model_input_health = ModelInputHealthDiagnostic(
            rows=len(frame), columns=len(frame.columns), duplicate_rows=int(frame.duplicated().sum()),
            missing_values=self.feature_matrix.missing_values, constant_features=constants,
            near_constant_features=near_constants, variance_summary=variance,
            result=result, reasons=tuple(reasons),
        )

    def capture_predictions(self, probabilities: Any) -> None:
        values = np.asarray(probabilities, dtype=float).reshape(-1)
        if not len(values):
            self.prediction = PredictionDiagnostic(0.0, 0.0, 0.0, 0.0, 0, (), "FAIL", ("No probabilities returned by model.predict_proba().",))
            return
        counts, edges = np.histogram(values, bins=10, range=(0.0, 1.0))
        histogram = tuple(HistogramBucket(float(edges[i]), float(edges[i + 1]), int(counts[i])) for i in range(len(counts)))
        std = float(np.std(values))
        reasons = ("Probability standard deviation is below the existing variance-guard threshold.",) if len(values) > 1 and std < 1e-4 else ("Probability distribution measured after model.predict_proba().",)
        self.prediction = PredictionDiagnostic(float(values.min()), float(values.max()), float(values.mean()), std, int(np.unique(values).size), histogram, "FAIL" if len(values) > 1 and std < 1e-4 else "PASS", reasons)

    def root_cause_analysis(self) -> RootCauseAnalysis:
        stages: list[RootCauseDiagnostic] = []
        if self.semantic:
            status = "PASS" if self.semantic.business_confidence > 0.0 else "FAIL"
            stages.append(RootCauseDiagnostic("Business Meaning", status, (f"Measured business confidence: {self.semantic.business_confidence:.1%}.",)))
        if self.canonical:
            status = "PASS" if not self.canonical.missing_features else "WARNING"
            evidence = (f"Measured canonical coverage: {self.canonical.coverage_score:.1%}.", f"Unmapped features: {len(self.canonical.missing_features)}.")
            recommendation = "Review ontology coverage for unresolved source columns." if self.canonical.missing_features else None
            stages.append(RootCauseDiagnostic("Canonical Mapping", status, evidence, recommendation))
        if self.model_input_health:
            stages.append(RootCauseDiagnostic("Model Input Health", self.model_input_health.result, self.model_input_health.reasons, "Inspect preprocessing transformations for measured constant or missing features." if self.model_input_health.result != "PASS" else None))
        if self.prediction:
            stages.append(RootCauseDiagnostic("Prediction", self.prediction.health, self.prediction.reasons, "Inspect the measured final feature matrix and preprocessing transformations." if self.prediction.health == "FAIL" else None))
        return RootCauseAnalysis(tuple(stages))


_ACTIVE_RUN: ContextVar[UDIFRun | None] = ContextVar("udif_active_run", default=None)


def configure(level: DiagnosticLevel) -> UDIFRun | None:
    """Set the process-local diagnostic scope; OFF performs no collection."""
    run = None if level is DiagnosticLevel.OFF else UDIFRun(level)
    _ACTIVE_RUN.set(run)
    return run


def active_run() -> UDIFRun | None:
    return _ACTIVE_RUN.get()


def _as_frame(matrix: Any, column_names: list[str] | tuple[str, ...] | None) -> pd.DataFrame:
    if isinstance(matrix, pd.DataFrame):
        return matrix.copy(deep=False)
    values = np.asarray(matrix)
    names = list(column_names or [f"feature_{index}" for index in range(values.shape[1])])
    return pd.DataFrame(values, columns=names)


def _json_scalar(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
