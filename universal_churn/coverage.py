"""
universal_churn/coverage.py
────────────────────────────
Weighted feature coverage scoring and feature recovery.

Routing bands
─────────────
Green  ≥ 85%  →  Full sector-specific XGBoost  (Prediction_Mode = 'Full')
Yellow 60–85% →  Universal XGBoost fallback     (Prediction_Mode = 'Fallback')
Red    < 60%  →  Hard stop, no prediction       (Prediction_Mode = 'Refused')
"""
from __future__ import annotations

import pandas as pd

from .config import SECTOR_FEATURE_WEIGHTS


# ── Feature recovery rules ────────────────────────────────────────
# (target_feature, [source_columns_needed], derivation_fn)
_DERIVATION_RULES: list[tuple[str, list[str], object]] = [
    (
        'Tenure_Months', ['Policy_Start_Date'],
        lambda df: (
            (pd.Timestamp.now() - pd.to_datetime(df['Policy_Start_Date'], errors='coerce'))
            .dt.days / 30.44
        ).round(1),
    ),
    (
        'Age', ['Date_of_Birth'],
        lambda df: (
            (pd.Timestamp.now() - pd.to_datetime(df['Date_of_Birth'], errors='coerce'))
            .dt.days / 365.25
        ).round(0),
    ),
    (
        'Days_Since_Last_Visit', ['Last_Visit_Date'],
        lambda df: (
            (pd.Timestamp.now() - pd.to_datetime(df['Last_Visit_Date'], errors='coerce'))
            .dt.days
        ).round(0),
    ),
    (
        'DaySinceLastOrder', ['Last_Order_Date'],
        lambda df: (
            (pd.Timestamp.now() - pd.to_datetime(df['Last_Order_Date'], errors='coerce'))
            .dt.days
        ).round(0),
    ),
    (
        'MonthlyCharges', ['AnnualPremium'],
        lambda df: (df['AnnualPremium'] / 12).round(2),
    ),
    (
        'Avg_Out_Of_Pocket_Cost', ['AnnualPremium'],
        lambda df: (df['AnnualPremium'] / 12).round(2),
    ),
    (
        'Visits_Last_Year', ['Visit_History'],
        lambda df: pd.to_numeric(df['Visit_History'], errors='coerce').fillna(0),
    ),
]


def _attempt_feature_recovery(df: pd.DataFrame, sector: str) -> pd.DataFrame | None:
    """
    Try to derive missing features from known proxy columns before
    routing to the universal model fallback.
    Returns an enriched copy of df if at least one feature was recovered,
    or None if nothing could be derived.
    """
    df_cols_lower = {c.lower().replace('_', ''): c for c in df.columns}
    recovered     = df.copy()
    any_recovered = False

    for target_feat, sources, derive_fn in _DERIVATION_RULES:
        target_lower = target_feat.lower().replace('_', '')
        if target_lower in df_cols_lower:
            continue

        src_map = {}
        for src in sources:
            src_lower = src.lower().replace('_', '')
            if src_lower in df_cols_lower:
                src_map[src] = df_cols_lower[src_lower]
            else:
                src_map = {}
                break
        if not src_map:
            continue

        tmp = recovered.rename(columns={v: k for k, v in src_map.items()})
        try:
            recovered[target_feat] = derive_fn(tmp).values
            print(f"  Recovered '{target_feat}' from {sources}")
            any_recovered = True
        except Exception as exc:
            print(f"  Recovery of '{target_feat}' failed: {exc}")

    return recovered if any_recovered else None


# Public alias — sector_pipeline.py and other callers outside this module
# import the public name; the leading-underscore name remains for any
# internal call sites already using it.
attempt_feature_recovery = _attempt_feature_recovery


def compute_coverage_score(
    df_input: pd.DataFrame,
    sector: str,
    mode: str = 'sector',
    green_threshold: float = 0.85,
    yellow_threshold: float = 0.60,
    _suppress_print: bool = False,
) -> dict:
    """
    Compute weighted feature coverage score for the input CSV.

    Coverage Score = Σ(weight_i × quality_i) / Σ(weight_i)

    quality_i = 1  if column is present, <95% null, and non-constant
    quality_i = 0  otherwise

    Returns a dict with keys:
        coverage_score      float
        status              'Green' | 'Yellow' | 'Red'
        prediction_mode     'Full' | 'Fallback' | 'Refused'
        missing_critical    list  (weight ≥ 4 features that failed)
        missing_high_impact list  (weight = 3 features that failed)
        missing_all         list  (all features that failed)
        detail              list[dict]  per-feature breakdown
    """
    weights      = SECTOR_FEATURE_WEIGHTS.get(sector, {c: 1 for c in df_input.columns})
    total_weight = sum(weights.values())

    def _strip(s: str) -> str:
        return s.lower().replace('_', '').replace(' ', '')

    stripped_to_original = {_strip(c): c for c in df_input.columns}

    detail           = []
    earned_weight    = 0.0
    missing_all      = []
    missing_critical = []

    for feat, weight in weights.items():
        orig_col = stripped_to_original.get(_strip(feat))

        if orig_col is None:
            quality, reason = 0, 'absent'
        else:
            col      = df_input[orig_col]
            pct_null = col.isna().mean()
            numeric  = pd.to_numeric(col, errors='coerce')
            n_unique = numeric.dropna().nunique()

            if pct_null >= 0.95:
                quality, reason = 0, f'mostly null ({pct_null*100:.0f}%)'
            elif n_unique <= 1:
                quality, reason = 0, 'constant (no variance)'
            else:
                quality, reason = 1, 'OK'

        earned_weight += weight * quality
        detail.append({'feature': feat, 'weight': weight,
                       'quality': quality, 'reason': reason})
        if quality == 0:
            missing_all.append(feat)
            if weight >= 4:
                missing_critical.append(feat)

    coverage_score = earned_weight / total_weight if total_weight > 0 else 0.0

    if coverage_score >= green_threshold:
        status, prediction_mode = 'Green', 'Full'
    elif coverage_score >= yellow_threshold:
        status, prediction_mode = 'Yellow', 'Fallback'
    else:
        status, prediction_mode = 'Red', 'Refused'

    missing_high_impact = [
        f for f in missing_all
        if f not in missing_critical and weights.get(f, 0) >= 3
    ]

    if not _suppress_print:
        _print_coverage_report(
            coverage_score, status, prediction_mode, sector, mode,
            weights, detail, missing_critical, missing_high_impact, missing_all,
        )

    return {
        'coverage_score'      : round(coverage_score, 4),
        'status'              : status,
        'prediction_mode'     : prediction_mode,
        'missing_critical'    : missing_critical,
        'missing_high_impact' : missing_high_impact,
        'missing_all'         : missing_all,
        'detail'              : detail,
    }


def _print_coverage_report(
    coverage_score, status, prediction_mode, sector, mode,
    weights, detail, missing_critical, missing_high_impact, missing_all,
) -> None:
    sep   = '─' * 60
    icons = {'Green': '✔', 'Yellow': '△', 'Red': '✖'}
    print(f"\n{sep}")
    print(f"  COVERAGE SCORE REPORT  [{mode.upper()} / {sector.upper()}]")
    print(sep)
    print(f"  Weighted coverage score : {coverage_score*100:.1f}%")
    print(f"  Status                  : {icons[status]} {status}")
    print(f"  Prediction mode         : {prediction_mode}")

    if missing_critical:
        print(f"\n  Missing critical features (weight ≥ 4):")
        for f in missing_critical:
            r = next(d['reason'] for d in detail if d['feature'] == f)
            print(f"    [{weights[f]}]  {f}  ({r})")

    if missing_high_impact:
        print(f"\n  Missing high-impact features (weight = 3):")
        for f in missing_high_impact:
            r = next(d['reason'] for d in detail if d['feature'] == f)
            print(f"    [{weights[f]}]  {f}  ({r})")

    low_missing = [f for f in missing_all
                   if f not in missing_critical and f not in missing_high_impact]
    if low_missing:
        print(f"\n  Lower-weight features missing or unusable:")
        for f in low_missing:
            r = next(d['reason'] for d in detail if d['feature'] == f)
            print(f"    [{weights[f]}]  {f}  ({r})")

    if status == 'Green':
        print(f"\n  Using full sector-specific model.")
    elif status == 'Yellow':
        if mode == 'universal':
            print(f"\n  Universal mode selected. Coverage analysis completed.")
            print(f"  Predictions may be less precise — high-impact features unavailable.")
        else:
            print(f"\n  Coverage below 85% — attempting feature recovery...")
            print(f"  If recovery fails, routing to universal model fallback.")
    else:
        if mode == 'universal':
            print(f"\n  Universal mode selected. Coverage critically low.")
            print(f"  Predictions are likely unreliable.")
        else:
            print(f"\n  Coverage below 60% — prediction refused.")
            print(f"  Enrich the input CSV with the critical features listed above.")

    print(sep)
