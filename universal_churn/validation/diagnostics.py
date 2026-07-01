"""
universal_churn/validation/diagnostics.py
══════════════════════════════════════════════════════════════════════
Pipeline Diagnostics — Part 4 of the Version 6 / Chunk 4 validation
milestone.

StageDiagnostics captures, per pipeline stage:
    execution_time_ms
    rows_processed
    columns_processed
    feature_count
    canonical_field_count
    business_concept_count
    normalization_strategy
    pipeline_stage

IMPORTANT: this module is purely observational. It is invoked FROM the
validation harness (regression.py / validate_framework.py), never from
cli.py, sector_pipeline.py, universal_pipeline.py, or routing.py.
Diagnostics data is never fed back into a prediction and never changes
control flow — it is instrumentation wrapped AROUND the existing,
unmodified pipeline functions.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field

import pandas as pd

from ..config import SECTOR_CONFIG
from ..schema_resolution import resolve_schema
from ..business_concepts import compute_concept_values, CONCEPT_NAMES
from ..feature_engineering import extract_universal_features
from ..preprocessing import sanitize_numerical_columns, derive_temporal_features


@dataclass
class StageDiagnostics:
    pipeline_stage: str
    execution_time_ms: float = 0.0
    rows_processed: int = 0
    columns_processed: int = 0
    feature_count: int | None = None
    canonical_field_count: int | None = None
    business_concept_count: int | None = None
    normalization_strategy: str | None = None

    def to_dict(self) -> dict:
        return dict(vars(self))


class DiagnosticsCollector:
    """Accumulates StageDiagnostics for one sector's pipeline run."""

    def __init__(self, sector: str) -> None:
        self.sector = sector
        self.stages: list[StageDiagnostics] = []

    @contextmanager
    def _timed_stage(self, name: str, **static_fields):
        start = time.perf_counter()
        box: dict = {}
        yield box
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        diag = StageDiagnostics(
            pipeline_stage=name,
            execution_time_ms=round(elapsed_ms, 4),
            **static_fields,
        )
        for k, v in box.items():
            setattr(diag, k, v)
        self.stages.append(diag)

    def run(self, df_raw: pd.DataFrame) -> list[StageDiagnostics]:
        """
        Run the observable stages of the pipeline for `df_raw` and
        return per-stage diagnostics. Uses the exact same, unmodified
        functions as production (schema_resolution, business_concepts,
        feature_engineering) — it wraps them, it does not reimplement
        them.
        """
        config = SECTOR_CONFIG[self.sector]

        with self._timed_stage("sanitize_and_temporal") as box:
            df = sanitize_numerical_columns(df_raw.copy())
            df = derive_temporal_features(df)
            box["rows_processed"] = len(df)
            box["columns_processed"] = len(df.columns)

        with self._timed_stage("schema_resolution") as box:
            canonical_df, resolutions = resolve_schema(df)
            resolved = sum(1 for r in resolutions if r.canonical_field is not None)
            box["rows_processed"] = len(canonical_df)
            box["columns_processed"] = len(canonical_df.columns)
            box["canonical_field_count"] = resolved

        with self._timed_stage("business_concepts") as box:
            # See validation/regression.py for why de-duplication is needed.
            deduped_canonical = canonical_df.loc[:, ~canonical_df.columns.duplicated(keep="first")]
            concept_df, confidence = compute_concept_values(deduped_canonical, self.sector)
            box["rows_processed"] = len(concept_df)
            box["columns_processed"] = len(concept_df.columns)
            box["business_concept_count"] = sum(
                1 for c in confidence.values() if c > 0)

        with self._timed_stage("feature_engineering",
                                normalization_strategy="persisted_training_stats_or_batch_fallback") as box:
            feat_df = extract_universal_features(
                df.copy(), self.sector, config["target_col"], norm_stats=None)
            box["rows_processed"] = len(feat_df)
            box["columns_processed"] = len(feat_df.columns)
            box["feature_count"] = len([
                c for c in feat_df.columns if c not in ("Churn", "Sector")
            ])

        return self.stages


def print_diagnostics_report(collector: DiagnosticsCollector) -> None:
    sep = "─" * 78
    print(f"\n{sep}\n  PIPELINE DIAGNOSTICS — [{collector.sector.upper()}]\n{sep}")
    for d in collector.stages:
        print(f"  {d.pipeline_stage:<24} time={d.execution_time_ms:>8.3f}ms  "
              f"rows={d.rows_processed:<5} cols={d.columns_processed:<4} "
              f"features={d.feature_count} canonical={d.canonical_field_count} "
              f"concepts={d.business_concept_count}")
    print(sep)
