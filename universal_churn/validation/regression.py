"""
universal_churn/validation/regression.py
══════════════════════════════════════════════════════════════════════
Regression Harness — Part 2 of the Version 6 / Chunk 4 validation
milestone.

For every supported sector this module walks the pipeline

    Raw CSV
      -> Canonical DataFrame        (schema_resolution.resolve_schema)
      -> Business Concepts          (business_concepts.compute_concept_values)
      -> Engineered Features        (feature_engineering.extract_universal_features)
      -> Model Input                (feature_engineering.transform_features_by_sector)
      -> Prediction                 (universal_pipeline.predict_universal /
                                      sector_pipeline.SectorPipeline.predict)

and, at every stage, records:
    - a deterministic content hash
    - row count
    - column count
    - the sorted column list (schema fingerprint)

Results are compared against a persisted baseline
(outputs/validation/regression_baseline.json). The FIRST run for a
given sector bootstraps the baseline; every subsequent run compares
against it and reports DRIFT with (stage, expected hash, actual hash,
likely cause) rather than silently continuing.

This module is read-only with respect to the production pipeline — it
never mutates config, models, or scalers, and it is never imported by
cli.py / sector_pipeline.py / universal_pipeline.py.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import SECTOR_CONFIG
from ..schema_resolution import resolve_schema
from ..business_concepts import compute_concept_values
from ..feature_engineering import extract_universal_features, transform_features_by_sector
from ..preprocessing import sanitize_numerical_columns, derive_temporal_features

BASELINE_PATH = Path("outputs/validation/regression_baseline.json")

# Rows are truncated for regression hashing so the harness stays fast
# and so hashes aren't sensitive to unrelated dataset growth.
DEFAULT_SAMPLE_ROWS = 25


# ══════════════════════════════════════════════════════════════════
# HASHING
# ══════════════════════════════════════════════════════════════════

def _hash_dataframe(df: pd.DataFrame, float_round: int = 6) -> str:
    """
    Deterministic content hash of a DataFrame, independent of column
    order (sorted alphabetically) and of float representation noise
    (rounded before serialisation).
    """
    if df is None:
        return "NONE"
    work = df.copy()
    # Sort columns by name using positional selection (not label-based
    # reindex) — resolve_schema() can legitimately map several raw
    # columns onto the same canonical field name, producing duplicate
    # column labels that label-based reindex() cannot handle.
    order = sorted(range(len(work.columns)), key=lambda i: (work.columns[i], i))
    work = work.iloc[:, order]
    for i, col in enumerate(work.columns):
        series = work.iloc[:, i]
        if pd.api.types.is_numeric_dtype(series):
            work.isetitem(i, series.astype(float).round(float_round))
    work.columns = [f"{c}__{i}" for i, c in enumerate(work.columns)]
    work = work.reset_index(drop=True)
    payload = work.to_csv(index=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# ══════════════════════════════════════════════════════════════════
# RESULT STRUCTURES
# ══════════════════════════════════════════════════════════════════

@dataclass
class PipelineStageResult:
    stage: str
    ok: bool
    row_count: int = 0
    column_count: int = 0
    columns: list[str] = field(default_factory=list)
    content_hash: str = ""
    error: str | None = None
    drift_detected: bool = False
    expected_hash: str | None = None
    likely_cause: str | None = None


@dataclass
class RegressionResult:
    sector: str
    passed: bool
    stages: list[PipelineStageResult] = field(default_factory=list)
    bootstrap: bool = False  # True if this run created a new baseline

    def to_dict(self) -> dict:
        return {
            "sector": self.sector,
            "passed": self.passed,
            "bootstrap": self.bootstrap,
            "stages": [vars(s) for s in self.stages],
        }


# ══════════════════════════════════════════════════════════════════
# BASELINE PERSISTENCE
# ══════════════════════════════════════════════════════════════════

def _load_baseline() -> dict:
    if BASELINE_PATH.exists():
        try:
            return json.loads(BASELINE_PATH.read_text())
        except Exception:
            return {}
    return {}


def _save_baseline(baseline: dict) -> None:
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(json.dumps(baseline, indent=2, sort_keys=True))


def _likely_cause(stage: str) -> str:
    causes = {
        "raw": "Source CSV changed (data/<sector>/*.csv was edited or replaced).",
        "canonical": "schema_resolution.py alias/regex registry changed, or raw columns changed.",
        "concepts": "business_concepts.py source mapping, confidence, or transform changed.",
        "features": "feature_engineering.py derivation logic or norm_stats changed.",
        "model_input": "transform_features_by_sector() column ordering/defaults changed, "
                        "or outputs/universal/universal_features.csv changed.",
        "prediction": "Model artifact was retrained, or an upstream stage silently changed "
                       "the feature values feeding the model.",
    }
    return causes.get(stage, "Unknown — inspect the stage function directly.")


# ══════════════════════════════════════════════════════════════════
# PER-SECTOR REGRESSION RUN
# ══════════════════════════════════════════════════════════════════

def run_regression_for_sector(
    sector: str,
    sample_rows: int = DEFAULT_SAMPLE_ROWS,
    update_baseline: bool = True,
) -> RegressionResult:
    """
    Run the full raw -> prediction regression walk for one sector and
    compare every stage's hash against the persisted baseline.
    """
    config = SECTOR_CONFIG[sector]
    stages: list[PipelineStageResult] = []
    baseline = _load_baseline()
    sector_baseline = baseline.get(sector, {})
    bootstrap = sector not in baseline
    overall_ok = True

    def record(stage_name: str, df: pd.DataFrame | None, error: str | None = None) -> None:
        nonlocal overall_ok
        if error is not None:
            stages.append(PipelineStageResult(stage=stage_name, ok=False, error=error))
            overall_ok = False
            return
        h = _hash_dataframe(df)
        expected = sector_baseline.get(stage_name)
        drift = expected is not None and expected != h
        if drift:
            overall_ok = False
        stages.append(PipelineStageResult(
            stage=stage_name,
            ok=not drift,
            row_count=len(df) if df is not None else 0,
            column_count=len(df.columns) if df is not None else 0,
            columns=sorted(df.columns.tolist()) if df is not None else [],
            content_hash=h,
            drift_detected=drift,
            expected_hash=expected,
            likely_cause=_likely_cause(stage_name) if drift else None,
        ))

    # ── Stage 0: Raw CSV ─────────────────────────────────────────
    data_path = config["data_path"]
    if not Path(data_path).exists():
        record("raw", None, error=f"Data file not found: {data_path}")
        return RegressionResult(sector=sector, passed=False, stages=stages, bootstrap=bootstrap)

    try:
        df_raw = pd.read_csv(data_path).head(sample_rows).copy()
        df_raw = sanitize_numerical_columns(df_raw)
        df_raw = derive_temporal_features(df_raw)
        record("raw", df_raw)
    except Exception as exc:
        record("raw", None, error=str(exc))
        return RegressionResult(sector=sector, passed=False, stages=stages, bootstrap=bootstrap)

    # ── Stage 1: Canonical DataFrame ─────────────────────────────
    try:
        canonical_df, _resolutions = resolve_schema(df_raw)
        record("canonical", canonical_df)
    except Exception as exc:
        record("canonical", None, error=str(exc))
        canonical_df = None

    # ── Stage 2: Business Concepts ───────────────────────────────
    if canonical_df is not None:
        try:
            # NOTE (discovered during validation): schema_resolution.
            # resolve_schema() can legitimately map several raw columns
            # onto the same canonical field name (e.g. ecommerce/
            # healthcare production data both have >=2 raw columns
            # aliasing to one canonical field). business_concepts.
            # compute_concept_values() indexes canonical_df[field] and
            # expects a Series, so duplicate-labelled columns make that
            # a DataFrame and raise. This combination (resolve_schema's
            # output fed straight into compute_concept_values) is not
            # actually exercised by the live predict path today —
            # sector_pipeline.py / universal_pipeline.py use the
            # legacy feature_engineering.extract_universal_features /
            # transform_features_by_sector functions instead, and the
            # newer build_canonical_dataframe() (feature_engineering.py)
            # already de-duplicates before calling compute_business_
            # concepts(). We de-duplicate here too (keep first) so the
            # regression harness measures compute_concept_values()'s
            # real behaviour rather than tripping on an input shape it
            # was never designed to receive, while still recording the
            # duplication as a schema-fingerprint fact via row/column
            # counts on the "canonical" stage above.
            deduped = canonical_df.loc[:, ~canonical_df.columns.duplicated(keep="first")]
            concept_df, _confidence = compute_concept_values(deduped, sector)
            record("concepts", concept_df)
        except Exception as exc:
            record("concepts", None, error=str(exc))

    # ── Stage 3: Engineered / Normalized Universal Features ──────
    try:
        target_col = config["target_col"]
        feat_df = extract_universal_features(df_raw.copy(), sector, target_col, norm_stats=None)
        record("features", feat_df)
    except Exception as exc:
        record("features", None, error=str(exc))

    # ── Stage 4: Model Input (universal-model feature matrix) ────
    try:
        X_processed = transform_features_by_sector(df_raw.copy(), sector)
        record("model_input", X_processed)
    except Exception as exc:
        record("model_input", None, error=str(exc))

    # ── Stage 5: Prediction (universal model, if trained) ────────
    try:
        from ..universal_pipeline import predict_universal
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as tmp:
            df_raw.to_csv(tmp.name, index=False)
            tmp_path = tmp.name
        results = predict_universal(
            tmp_path, force_sector=sector, _prediction_mode="Regression")
        pred_df = results[["Predicted_Churn", "Churn_Probability"]].copy()
        record("prediction", pred_df)
        Path(tmp_path).unlink(missing_ok=True)
    except FileNotFoundError as exc:
        stages.append(PipelineStageResult(
            stage="prediction", ok=True,
            error=f"Skipped — universal model not trained yet ({exc})",
        ))
    except Exception as exc:
        record("prediction", None, error=str(exc))

    result = RegressionResult(sector=sector, passed=overall_ok, stages=stages, bootstrap=bootstrap)

    if update_baseline and (bootstrap or overall_ok is False or True):
        # Persist current hashes as the new baseline for stages that
        # succeeded without an existing conflicting baseline entry, and
        # always bootstrap missing entries. We do NOT silently overwrite
        # a stage that just drifted — that must be a conscious decision
        # (re-run with update_baseline=False to inspect without
        # accepting the new hash as correct).
        new_sector_baseline = dict(sector_baseline)
        for s in stages:
            if s.content_hash and not s.drift_detected:
                new_sector_baseline[s.stage] = s.content_hash
        if bootstrap:
            for s in stages:
                if s.content_hash:
                    new_sector_baseline[s.stage] = s.content_hash
        baseline[sector] = new_sector_baseline
        _save_baseline(baseline)

    return result


def run_full_regression(
    sectors: list[str] | None = None,
    sample_rows: int = DEFAULT_SAMPLE_ROWS,
    update_baseline: bool = True,
) -> dict[str, RegressionResult]:
    """Run the regression harness for every (or a chosen subset of) sector."""
    sectors = sectors or list(SECTOR_CONFIG.keys())
    return {
        sector: run_regression_for_sector(sector, sample_rows=sample_rows,
                                          update_baseline=update_baseline)
        for sector in sectors
    }


def print_regression_report(results: dict[str, RegressionResult]) -> bool:
    """Human-readable regression report. Returns overall pass/fail."""
    sep = "─" * 68
    print(f"\n{sep}\n  REGRESSION HARNESS REPORT\n{sep}")
    all_passed = True
    for sector, result in results.items():
        tag = "BOOTSTRAP" if result.bootstrap else ("PASS" if result.passed else "FAIL")
        icon = "✔" if result.passed else "✖"
        print(f"\n  [{sector.upper()}] {icon} {tag}")
        for s in result.stages:
            if s.error and not s.drift_detected and s.ok:
                print(f"      {s.stage:<14} SKIPPED — {s.error}")
                continue
            if s.error:
                print(f"      {s.stage:<14} ERROR — {s.error}")
                all_passed = False
                continue
            status = "OK" if not s.drift_detected else "DRIFT"
            print(f"      {s.stage:<14} {status:<6} rows={s.row_count:<4} "
                  f"cols={s.column_count:<3} hash={s.content_hash}")
            if s.drift_detected:
                all_passed = False
                print(f"                     expected_hash={s.expected_hash}  "
                      f"actual_hash={s.content_hash}")
                print(f"                     likely_cause: {s.likely_cause}")
        if not result.passed:
            all_passed = False
    print(f"\n{sep}")
    print(f"  Overall regression status: {'PASS' if all_passed else 'FAIL'}")
    print(sep)
    return all_passed
