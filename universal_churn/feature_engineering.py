"""
universal_churn/feature_engineering.py
────────────────────────────────────────
Universal feature extraction — maps each sector's raw columns to the
common UNIVERSAL_FEATURES space used by the Phase B cross-sector model.

Version 6 note (Concept-First Feature Engineering)
---------------------------------------------------
Target shared pipeline (see PART B of the v5.2 -> v6 milestone spec):

    Raw CSV
      -> resolve_schema()              (schema_resolution.py)
      -> build_canonical_dataframe()   (Chunk 1 — completed)
      -> compute_business_concepts()   (Chunk 2 — completed)
      -> derive_engineered_features()  (Chunk 2 — completed)
      -> normalize_features()          (Chunk 3 — next milestone)
      -> prepare_model_input()         (Chunk 4 — later milestone)

Chunk 3 is the next milestone: extracting normalization into its own
shared stage while preserving saved-model compatibility. Until that
work lands, the public extract_universal_features() and
transform_features_by_sector() contracts remain the live universal
model path and must keep producing identical model inputs.

build_canonical_dataframe() intentionally does not duplicate any
resolution or derivation logic — it composes the already-live,
already-tested primitives from preprocessing.py and
schema_resolution.py rather than reimplementing them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .config import (
    SECTOR_CONFIG, SECTOR_NORM_COLUMNS, UNIVERSAL_FEATURES,
    UNIVERSAL_MODEL_PATH, UNIVERSAL_FEATURES_PATH, UNIVERSAL_NORM_STATS_PATH,
)
from .business_concepts import compute_concept_values, BUSINESS_CONCEPTS
from .preprocessing import (
    sanitize_numerical_columns, normalize_target, derive_temporal_features,
)
from .schema_resolution import resolve_schema, resolution_summary, ColumnResolution


FEATURE_ENGINEERING_VERSION = "6.chunk3.shared-preparation"
FEATURE_PREPARATION_PIPELINE_VERSION = "6.chunk3"
SCHEMA_PIPELINE_VERSION = "6.chunk1"
CONCEPT_PIPELINE_VERSION = "6.chunk2"
NORMALIZATION_VERSION = "legacy-max-v1"
NORMALIZATION_STRATEGY = "legacy_max_normalization"


@dataclass
class FeaturePreparationContext:
    """
    State container passed through the shared feature-preparation stages.

    The context keeps stage outputs together so training and prediction
    wrappers do not pass long bundles of unrelated arguments around.
    DataFrames remain optional because each stage fills its own slot.
    """
    raw_df: pd.DataFrame
    sector: str
    target_col: str | None = None
    norm_stats: dict | None = None
    canonical_df: pd.DataFrame | None = None
    concept_df: pd.DataFrame | None = None
    engineered_df: pd.DataFrame | None = None
    normalized_df: pd.DataFrame | None = None
    model_input_df: pd.DataFrame | None = None
    target: pd.Series | None = None
    resolutions: list[ColumnResolution] = field(default_factory=list)
    concept_confidence: dict[str, float] = field(default_factory=dict)
    schema_manifest: dict = field(default_factory=dict)
    concept_manifest: dict = field(default_factory=dict)
    feature_manifest: dict = field(default_factory=dict)
    normalization_manifest: dict = field(default_factory=dict)
    pipeline_manifest: dict = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════
# VERSION 6 SHARED PIPELINE — STAGE 1: SCHEMA -> CANONICAL FIELDS
# ══════════════════════════════════════════════════════════════════

def build_canonical_dataframe(
    df_raw: pd.DataFrame,
) -> tuple[pd.DataFrame, list[ColumnResolution], dict]:
    """
    Raw CSV -> Canonical Fields (target architecture, step 2).

    Deterministic, sector-agnostic. Composes three already-live steps
    in the fixed order required for reproducible training/inference
    parity:

        1. derive_temporal_features()   — date columns -> numeric
           "days since" columns (preprocessing.py, unchanged).
        2. sanitize_numerical_columns() — strip unit suffixes /
           currency symbols from known-numeric columns
           (preprocessing.py, unchanged).
        3. resolve_schema()             — rename resolvable raw
           columns to canonical field names (schema_resolution.py,
           unchanged).

    This function does not compute business concepts or engineered
    features — it only gets every input, regardless of sector or raw
    column naming, into one canonical shape. Concept computation is
    handled by compute_business_concepts().

    Parameters
    ----------
    df_raw : pd.DataFrame
        The raw input exactly as read from CSV (or already
        deserialized upstream).

    Returns
    -------
    canonical_df : pd.DataFrame
        Copy of df_raw with all deterministically-derivable columns
        added, numeric columns sanitized, and resolvable columns
        renamed to their canonical field names. Unresolved raw
        columns are kept as-is (not dropped) — later stages may still
        consult them for sector-specific logic that hasn't been
        generalised into a canonical field yet.
    resolutions : list[ColumnResolution]
        Per-column resolution record from resolve_schema(), unchanged
        — this is the existing input to coverage.py's confidence
        weighting and is passed through here for callers that need it
        without calling resolve_schema() a second time.
    manifest : dict
        Summary of what this stage did, safe to attach to diagnostics:
        {
            'temporal_columns_derived': [...],
            'resolution_summary': resolution_summary(resolutions),
            'canonical_field_collisions': {canonical_name: n_raw_columns},
        }
    """
    working = df_raw.copy()

    before_cols = set(working.columns)
    working = derive_temporal_features(working)
    temporal_columns_derived = sorted(set(working.columns) - before_cols)

    working = sanitize_numerical_columns(working)

    canonical_df, resolutions = resolve_schema(working)

    # ── Collision guard ──────────────────────────────────────────
    # resolve_schema() can legitimately map several distinct raw
    # columns to the same canonical field (e.g. healthcare's
    # Overall_Satisfaction / Wait_Time_Satisfaction / Staff_Satisfaction
    # all resolve to 'Satisfaction_Raw'). df.rename() then produces a
    # DataFrame with duplicate column names, and canonical_df[name]
    # returns a DataFrame instead of a Series. This was previously
    # silent: concepts.py's _safe_normalize() throws TypeError on a
    # DataFrame input, but coverage.py wraps concept-confidence
    # computation in a broad try/except, so the failure degraded to
    # "concept confidence unavailable" for the affected sector without
    # ever surfacing an error (reproduced against tests/golden_
    # healthcare.csv and tests/golden_ecommerce.csv). Coalescing here
    # — first non-null value across the colliding columns, in original
    # column order — keeps one canonical Series per field, using
    # already-available information rather than dropping it silently.
    duplicated_names = canonical_df.columns[canonical_df.columns.duplicated()].unique().tolist()
    collision_counts: dict[str, int] = {}
    if duplicated_names:
        for name in duplicated_names:
            same_named = canonical_df.loc[:, canonical_df.columns == name]
            collision_counts[name] = same_named.shape[1]
            coalesced = same_named.bfill(axis=1).iloc[:, 0]
            canonical_df = canonical_df.drop(columns=[name])
            canonical_df[name] = coalesced

    manifest = {
        'temporal_columns_derived': temporal_columns_derived,
        'resolution_summary': resolution_summary(resolutions),
        'canonical_field_collisions': collision_counts,
    }

    return canonical_df, resolutions, manifest


# ── Normalization and concept helpers ──────────────────────────────


def _first_series(df: pd.DataFrame, *candidates: str, default: float | str = 0.0) -> pd.Series:
    """Return the first matching column as a Series, or a filled default Series."""
    for candidate in candidates:
        if candidate in df.columns:
            series = df.loc[:, candidate]
            if isinstance(series, pd.DataFrame):
                series = series.bfill(axis=1).iloc[:, 0]
            return series
    return pd.Series(default, index=df.index)


def _numeric_series(df: pd.DataFrame, *candidates: str, default: float = 0.0) -> pd.Series:
    series = _first_series(df, *candidates, default=default)
    return pd.to_numeric(series, errors='coerce').fillna(default)


def _text_series(df: pd.DataFrame, *candidates: str, default: str = '') -> pd.Series:
    series = _first_series(df, *candidates, default=default)
    return series.astype(str).fillna(default)


def _norm_max(
    df: pd.DataFrame,
    sector: str,
    norm_stats: dict | None,
    *candidates: str,
) -> float:
    """
    Return the normalization maximum for the first available candidate.

    The persisted stats are still keyed by the original raw column names,
    so the helper checks every canonical/raw alias in order and falls back
    to the current batch if no training stat exists.
    """
    for candidate in candidates:
        key = f"{sector}.{candidate}"
        if norm_stats is not None and key in norm_stats and norm_stats[key]:
            return float(norm_stats[key])

    for candidate in candidates:
        if candidate in df.columns:
            batch_max = pd.to_numeric(_first_series(df, candidate, default=np.nan), errors='coerce').max()
            if pd.isna(batch_max) or batch_max == 0:
                batch_max = 1
            return float(batch_max)

    return 1.0


def _normalize_by_max(
    df: pd.DataFrame,
    sector: str,
    norm_stats: dict | None,
    *candidates: str,
    default: float = 0.0,
    clip: bool = False,
) -> pd.Series:
    series = _numeric_series(df, *candidates, default=default)
    max_value = _norm_max(df, sector, norm_stats, *candidates)
    if max_value == 0:
        max_value = 1.0
    normalized = series / max_value
    if clip:
        normalized = normalized.clip(0, 1)
    return normalized.fillna(default)


def _boolean_from_text(series: pd.Series, true_values: set[str]) -> pd.Series:
    normalized = series.astype(str).str.strip().str.lower()
    return normalized.isin(true_values).astype(float)


def _contract_stability_score(series: pd.Series) -> pd.Series:
    if series.empty:
        return pd.Series(0.0, index=series.index)
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors='coerce').fillna(0.0).clip(0, 1)
    mapped = series.astype(str).map({
        'Month-to-month': 0.0,
        'One year': 0.5,
        'Two year': 1.0,
    })
    return mapped.fillna(0.0)


def _payment_auto_score(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors='coerce').fillna(0.0).clip(0, 1)
    normalized = series.astype(str).str.strip().str.lower()
    return normalized.str.contains('automatic|credit card|debit card|upi|card', regex=True, na=False).astype(float)


def _service_breadth_score(df: pd.DataFrame) -> pd.Series:
    service_cols = [
        'PhoneService', 'MultipleLines', 'InternetService',
        'OnlineSecurity', 'OnlineBackup', 'DeviceProtection',
        'TechSupport', 'StreamingTV', 'StreamingMovies',
    ]
    flags = []
    for col in service_cols:
        if col in df.columns:
            flags.append(_boolean_from_text(_text_series(df, col), {'yes'}))
        else:
            flags.append(pd.Series(0.0, index=df.index))
    return pd.concat(flags, axis=1).mean(axis=1)


def _average_normalized_scores(
    df: pd.DataFrame,
    sector: str,
    norm_stats: dict | None,
    candidates: list[str],
) -> pd.Series:
    scores = []
    for candidate in candidates:
        if candidate in df.columns:
            scores.append(_normalize_by_max(df, sector, norm_stats, candidate, default=0.0, clip=True))
    if scores:
        return pd.concat(scores, axis=1).mean(axis=1)
    return pd.Series(0.5, index=df.index)


def compute_norm_stats(df: pd.DataFrame, sector: str, columns: list[str]) -> dict:
    """Compute per-column maxima for one sector to be persisted in norm_stats."""
    return {
        f"{sector}.{col}": float(m) if pd.notna(m) and m != 0 else 1.0
        for col in columns
        if col in df.columns
        for m in [pd.to_numeric(df[col], errors='coerce').max()]
    }


def compute_business_concepts(
    canonical_df: pd.DataFrame,
    sector: str,
) -> tuple[pd.DataFrame, dict[str, float], dict]:
    """Resolve the concept layer from canonical fields for diagnostics and downstream reuse."""
    concept_df, concept_confidence = compute_concept_values(canonical_df, sector)
    manifest = {
        'sector': sector,
        'available_concepts': [
            concept_name for concept_name, concept in BUSINESS_CONCEPTS.items()
            if concept.is_available_for(sector)
        ],
        'concept_confidence': concept_confidence,
    }
    return concept_df, concept_confidence, manifest


# ── Feature builder helpers ───────────────────────────────────────


def _neutral_series(index: pd.Index, value: float = 0.5) -> pd.Series:
    """Return a constant Series aligned to the feature matrix index."""
    return pd.Series(value, index=index)


def _zero_series(index: pd.Index) -> pd.Series:
    """Return a zero-filled Series aligned to the feature matrix index."""
    return pd.Series(0.0, index=index)


def _concept_series(
    concept_df: pd.DataFrame | None,
    concept_name: str,
    index: pd.Index,
    default: float = 0.5,
) -> pd.Series:
    """
    Read an already-computed business concept when it is available.

    The feature builders still keep legacy feature math as the source
    of model input truth. Concepts are used for diagnostics-aligned
    defaults and future Chunk 3 normalization boundaries, but not where
    their min-max reconstruction would change persisted model inputs.
    """
    if concept_df is not None and concept_name in concept_df.columns:
        return concept_df[concept_name].reindex(index).fillna(default)
    return _neutral_series(index, default)


def _legacy_max_normalized_feature(
    df: pd.DataFrame,
    sector: str,
    norm_stats: dict | None,
    *candidates: str,
    default: float = 0.0,
    clip: bool = False,
) -> pd.Series:
    """
    Current persisted-model normalization adapter.

    This isolates the legacy "divide by training max" behavior from raw
    feature derivation so a future normalize_features() stage can move
    the same logic without changing outputs.
    """
    return _normalize_by_max(df, sector, norm_stats, *candidates, default=default, clip=clip)


def _build_relationship_features(
    feat: pd.DataFrame,
    canonical_df: pd.DataFrame,
    sector: str,
    norm_stats: dict | None,
    tenure_candidates: tuple[str, ...],
    charge_candidates: tuple[str, ...],
    tenure_default: float = 0.0,
    charge_default: float = 0.0,
) -> None:
    """Populate normalized relationship tenure and recurring value."""
    feat['tenure_normalized'] = _legacy_max_normalized_feature(
        canonical_df, sector, norm_stats, *tenure_candidates, default=tenure_default
    )
    feat['charge_normalized'] = _legacy_max_normalized_feature(
        canonical_df, sector, norm_stats, *charge_candidates, default=charge_default
    )


def _build_satisfaction_features(
    feat: pd.DataFrame,
    canonical_df: pd.DataFrame,
    sector: str,
    norm_stats: dict | None,
    candidates: tuple[str, ...],
    default: float = 0.5,
) -> None:
    """Populate the single-sector satisfaction score."""
    feat['satisfaction_score'] = _legacy_max_normalized_feature(
        canonical_df, sector, norm_stats, *candidates, default=default, clip=True
    )


def _build_engagement_features(
    feat: pd.DataFrame,
    engagement: pd.Series,
) -> None:
    """Keep engagement volume and score aligned."""
    feat['num_products_services'] = engagement
    feat['engagement_score'] = engagement


def _build_payment_feature(
    feat: pd.DataFrame,
    source: pd.Series | float,
    mode: str = 'neutral',
) -> None:
    """Populate payment automation using existing sector-specific semantics."""
    if isinstance(source, pd.Series) and mode == 'contains_automatic':
        feat['payment_auto'] = source.astype(str).str.contains('automatic', case=False, na=False).astype(float)
    elif isinstance(source, pd.Series) and mode == 'preferred_ecommerce':
        feat['payment_auto'] = source.isin(['Credit Card', 'Debit Card', 'UPI']).astype(float)
    elif isinstance(source, pd.Series):
        feat['payment_auto'] = _payment_auto_score(source)
    else:
        feat['payment_auto'] = source


def _build_recency_features(
    feat: pd.DataFrame,
    recency_score: pd.Series | float,
    is_active: pd.Series | float,
) -> None:
    """Populate activity and recency features together."""
    feat['is_active'] = is_active
    feat['recency_score'] = recency_score


def _build_accessibility_features(
    feat: pd.DataFrame,
    convenience_score: pd.Series | float,
    care_accessibility: pd.Series | float | None = None,
) -> None:
    """Populate convenience/accessibility pair with matching defaults."""
    feat['convenience_score'] = convenience_score
    feat['care_accessibility'] = convenience_score if care_accessibility is None else care_accessibility


def _build_billing_features(
    feat: pd.DataFrame,
    has_complaint: pd.Series | float,
    billing_friction: pd.Series | float | None = None,
) -> None:
    """Populate support/billing friction features."""
    feat['has_complaint'] = has_complaint
    feat['billing_friction'] = has_complaint if billing_friction is None else billing_friction


def _ratio_feature(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Return a clipped numerator/denominator ratio with zero fallback."""
    safe_denominator = denominator.replace(0, np.nan)
    return (numerator / safe_denominator).clip(0, 1).fillna(0)


def _finalize_universal_features(feat: pd.DataFrame) -> pd.DataFrame:
    """Apply neutral defaults and stable UNIVERSAL_FEATURES ordering."""
    for col in UNIVERSAL_FEATURES:
        if col not in feat.columns:
            feat[col] = 0.5
    return feat[UNIVERSAL_FEATURES]


def _telecom_features(
    canonical_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    norm_stats: dict | None,
    concept_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    feat = pd.DataFrame(index=canonical_df.index)
    _build_relationship_features(
        feat, canonical_df, 'telecom', norm_stats,
        ('Tenure_Raw', 'tenure'), ('Recurring_Cost', 'MonthlyCharges')
    )

    _build_billing_features(feat, 0, 0)
    feat['satisfaction_score'] = _concept_series(concept_df, 'SATISFACTION_SIGNAL', canonical_df.index, default=0.5)
    _build_recency_features(feat, 0.5, 1)
    _build_engagement_features(feat, _service_breadth_score(raw_df))
    feat['is_senior_or_high_risk'] = _numeric_series(canonical_df, 'Demographic_Risk', 'SeniorCitizen', default=0.0)
    feat['has_support'] = _boolean_from_text(_text_series(raw_df, 'TechSupport', default='No'), {'yes'})
    feat['contract_stability'] = _contract_stability_score(_text_series(canonical_df, 'Contract_Commitment', 'Contract', default=''))
    payment_series = _first_series(canonical_df, 'Auto_Payment_Flag', 'PaymentMethod', default='')
    _build_payment_feature(
        feat,
        _text_series(pd.DataFrame({'payment': payment_series}), 'payment', default=''),
        mode='contains_automatic',
    )
    feat['coupon_dependency'] = 0
    feat['cashback_engagement'] = 0
    _build_accessibility_features(feat, feat['contract_stability'], 0.5)
    feat['lockin_risk'] = feat['contract_stability'] * (1 - feat['tenure_normalized'])
    feat['dormant_loyalty_risk'] = 0
    feat['missed_appt_rate'] = 0
    feat['composite_satisfaction'] = feat['satisfaction_score']
    feat['referral_engagement'] = 0
    return feat


def _ecommerce_features(
    canonical_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    norm_stats: dict | None,
    concept_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    feat = pd.DataFrame(index=canonical_df.index)
    _build_relationship_features(
        feat, canonical_df, 'ecommerce', norm_stats,
        ('Tenure_Raw', 'Tenure'), ('Recurring_Cost', 'CashbackAmount')
    )
    has_complaint = _legacy_max_normalized_feature(
        canonical_df, 'ecommerce', norm_stats, 'Support_Contacts', 'Complain', default=0.0, clip=True
    )
    _build_billing_features(feat, has_complaint)
    _build_satisfaction_features(feat, canonical_df, 'ecommerce', norm_stats, ('Satisfaction_Raw', 'SatisfactionScore'))

    is_active_raw = _first_series(canonical_df, 'Activity_Recency', 'DaySinceLastOrder', default=0.0)
    is_active = (pd.to_numeric(is_active_raw, errors='coerce') <= 7).astype(int)
    recency_score = _legacy_max_normalized_feature(
        canonical_df, 'ecommerce', norm_stats, 'Activity_Recency', 'DaySinceLastOrder', default=0.5
    )
    _build_recency_features(feat, recency_score, is_active)
    engagement = _legacy_max_normalized_feature(
        canonical_df, 'ecommerce', norm_stats, 'Engagement_Volume', 'OrderCount', default=0.0
    )
    _build_engagement_features(feat, engagement)
    feat['is_senior_or_high_risk'] = 0
    feat['has_support'] = 0
    feat['contract_stability'] = 0
    payment_series = _first_series(canonical_df, 'Auto_Payment_Flag', 'PreferredPaymentMode', default='')
    _build_payment_feature(
        feat,
        _text_series(pd.DataFrame({'payment': payment_series}), 'payment', default=''),
        mode='preferred_ecommerce',
    )
    feat['coupon_dependency'] = _legacy_max_normalized_feature(
        canonical_df, 'ecommerce', norm_stats, 'CouponUsed', default=0.0
    )
    feat['cashback_engagement'] = feat['charge_normalized']
    convenience_score = 1 - _legacy_max_normalized_feature(
        canonical_df, 'ecommerce', norm_stats, 'WarehouseToHome', default=0.5, clip=True
    )
    _build_accessibility_features(feat, convenience_score)
    feat['dormant_loyalty_risk'] = feat['tenure_normalized'] * feat['recency_score']
    feat['lockin_risk'] = 0
    feat['missed_appt_rate'] = 0
    feat['composite_satisfaction'] = feat['satisfaction_score']
    feat['referral_engagement'] = 0
    return feat


def _banking_features(
    canonical_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    norm_stats: dict | None,
    concept_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    feat = pd.DataFrame(index=canonical_df.index)
    _build_relationship_features(
        feat, canonical_df, 'banking', norm_stats,
        ('Tenure_Raw', 'Tenure'), ('Total_Spend', 'Balance')
    )
    _build_billing_features(feat, 0, 0)
    _build_satisfaction_features(feat, canonical_df, 'banking', norm_stats, ('Satisfaction_Raw', 'CreditScore'))
    is_active = _legacy_max_normalized_feature(
        canonical_df, 'banking', norm_stats, 'Active_Status', 'IsActiveMember', default=0.5, clip=True
    )
    _build_recency_features(feat, is_active, is_active)
    engagement = _legacy_max_normalized_feature(
        canonical_df, 'banking', norm_stats, 'Engagement_Volume', 'NumOfProducts', default=0.0
    ) / 4.0
    _build_engagement_features(feat, engagement)
    feat['is_senior_or_high_risk'] = (_numeric_series(canonical_df, 'Demographic_Risk', 'Age', default=0.0) > 55).astype(int)
    feat['has_support'] = _legacy_max_normalized_feature(
        canonical_df, 'banking', norm_stats, 'Auto_Payment_Flag', 'HasCrCard', default=0.0, clip=True
    )
    feat['contract_stability'] = feat['tenure_normalized']
    _build_payment_feature(feat, 0.5)
    feat['coupon_dependency'] = 0
    feat['cashback_engagement'] = feat['charge_normalized']
    _build_accessibility_features(feat, 0.5)
    feat['dormant_loyalty_risk'] = feat['tenure_normalized'] * (1 - feat['is_active'])
    feat['lockin_risk'] = 0
    feat['missed_appt_rate'] = 0
    feat['composite_satisfaction'] = feat['satisfaction_score']
    feat['referral_engagement'] = 0
    return feat


def _healthcare_features(
    canonical_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    norm_stats: dict | None,
    concept_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    feat = pd.DataFrame(index=canonical_df.index)
    _build_relationship_features(
        feat, canonical_df, 'healthcare', norm_stats,
        ('Tenure_Raw', 'Tenure_Months'),
        ('Recurring_Cost', 'Avg_Out_Of_Pocket_Cost', 'MonthlyPremium'),
        tenure_default=0.5,
    )

    billing_series = _numeric_series(canonical_df, 'Support_Contacts', 'Billing_Issues', default=0.0)
    has_complaint = (billing_series > 0).astype(int)
    _build_billing_features(feat, has_complaint, _zero_series(canonical_df.index))
    _build_satisfaction_features(feat, canonical_df, 'healthcare', norm_stats, ('Satisfaction_Raw', 'Overall_Satisfaction'))

    is_active = (_numeric_series(canonical_df, 'Activity_Recency', 'Days_Since_Last_Visit', default=0.0) <= 90).astype(int)
    recency_score = 1 - _legacy_max_normalized_feature(
        canonical_df, 'healthcare', norm_stats, 'Activity_Recency', 'Days_Since_Last_Visit', default=0.5, clip=True
    )
    _build_recency_features(feat, recency_score, is_active)
    engagement = _legacy_max_normalized_feature(
        canonical_df, 'healthcare', norm_stats, 'Engagement_Volume', 'Visits_Last_Year', 'FrequencyOfVisits', default=0.5
    )
    _build_engagement_features(feat, engagement)
    feat['is_senior_or_high_risk'] = (_numeric_series(canonical_df, 'Demographic_Risk', 'Age', default=0.0) > 65).astype(int)
    feat['has_support'] = _numeric_series(canonical_df, 'Portal_Usage', default=0.0)
    feat['contract_stability'] = feat['tenure_normalized']
    _build_payment_feature(feat, 0.5)
    feat['coupon_dependency'] = 0
    feat['cashback_engagement'] = 0
    dist_norm = _legacy_max_normalized_feature(
        canonical_df, 'healthcare', norm_stats, 'Distance_To_Facility_Miles', default=0.5, clip=True
    )
    portal_norm = _legacy_max_normalized_feature(
        canonical_df, 'healthcare', norm_stats, 'Portal_Usage', default=0.0, clip=True
    )
    _build_accessibility_features(feat, ((1 - dist_norm) + portal_norm).clip(0, 1), 0.5)
    feat['dormant_loyalty_risk'] = feat['tenure_normalized'] * (1 - feat['is_active'])
    feat['lockin_risk'] = 0

    feat['missed_appt_rate'] = (
        _legacy_max_normalized_feature(canonical_df, 'healthcare', norm_stats, 'Missed_Appointments', default=0.0, clip=True)
        if 'Missed_Appointments' in raw_df.columns or 'Missed_Appointments' in canonical_df.columns
        else pd.Series(0.0, index=canonical_df.index)
    )
    visits_series = _numeric_series(canonical_df, 'Engagement_Volume', 'Visits_Last_Year', 'FrequencyOfVisits', default=np.nan)
    if 'Missed_Appointments' in canonical_df.columns and visits_series.notna().any():
        feat['missed_appt_rate'] = _ratio_feature(
            _numeric_series(canonical_df, 'Missed_Appointments', default=0.0),
            visits_series,
        )

    feat['composite_satisfaction'] = _average_normalized_scores(
        raw_df,
        'healthcare',
        norm_stats,
        ['Overall_Satisfaction', 'Wait_Time_Satisfaction', 'Staff_Satisfaction', 'Provider_Rating'],
    )

    if 'Billing_Issues' in canonical_df.columns or 'Billing_Issues' in raw_df.columns:
        total_visits = visits_series.replace(0, np.nan)
        if total_visits.notna().any():
            feat['billing_friction'] = _ratio_feature(
                _numeric_series(canonical_df, 'Billing_Issues', default=0.0),
                visits_series,
            )
        else:
            feat['billing_friction'] = _legacy_max_normalized_feature(
                canonical_df, 'healthcare', norm_stats, 'Billing_Issues', default=0.0, clip=True
            )
    else:
        feat['billing_friction'] = pd.Series(0.0, index=canonical_df.index)

    referral_norm = _legacy_max_normalized_feature(
        canonical_df, 'healthcare', norm_stats, 'Referrals_Made', default=0.0, clip=True
    )
    feat['referral_engagement'] = referral_norm
    return feat


def derive_engineered_features(
    canonical_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    sector: str,
    norm_stats: dict | None = None,
    concept_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Canonical fields + business concepts -> stable universal feature matrix."""
    if sector == 'telecom':
        feat = _telecom_features(canonical_df, raw_df, norm_stats, concept_df)
    elif sector == 'ecommerce':
        feat = _ecommerce_features(canonical_df, raw_df, norm_stats, concept_df)
    elif sector == 'banking':
        feat = _banking_features(canonical_df, raw_df, norm_stats, concept_df)
    elif sector == 'healthcare':
        feat = _healthcare_features(canonical_df, raw_df, norm_stats, concept_df)
    else:
        feat = pd.DataFrame(index=canonical_df.index)
        for col in UNIVERSAL_FEATURES:
            feat[col] = 0.5

    return _finalize_universal_features(feat)


def normalize_features(context: FeaturePreparationContext) -> FeaturePreparationContext:
    """
    Normalize engineered features for model input.

    For Chunk 3 this stage preserves the saved-model compatible legacy
    max-normalized values produced by the Chunk 2 feature builders. The
    explicit stage boundary is now shared by training and prediction and
    is the future home for alternate normalization strategies.
    """
    if context.engineered_df is None:
        raise ValueError("Cannot normalize before engineered features exist.")
    context.normalized_df = _finalize_universal_features(context.engineered_df.copy())
    context.normalization_manifest = {
        'normalization_version': NORMALIZATION_VERSION,
        'normalization_strategy': NORMALIZATION_STRATEGY,
        'feature_count': int(context.normalized_df.shape[1]),
    }
    return context


def prepare_model_input(
    context: FeaturePreparationContext,
    *,
    include_target: bool,
    include_sector: bool,
) -> FeaturePreparationContext:
    """Attach optional target/sector columns and record final model input metadata."""
    if context.normalized_df is None:
        raise ValueError("Cannot prepare model input before normalization.")

    model_input = context.normalized_df.copy()
    target_col_actual = SECTOR_CONFIG.get(context.sector, {}).get('target_col', context.target_col)
    if include_target and target_col_actual in context.raw_df.columns:
        context.target = normalize_target(context.raw_df[target_col_actual])
        model_input['Churn'] = context.target.values
    if include_sector:
        model_input['Sector'] = context.sector

    context.model_input_df = model_input
    context.pipeline_manifest = _build_feature_preparation_manifest(context)
    context.model_input_df.attrs['feature_engineering_manifest'] = context.pipeline_manifest
    return context


def _build_feature_preparation_manifest(context: FeaturePreparationContext) -> dict:
    """Build diagnostics for the full shared feature-preparation run."""
    duplicate_columns_resolved = context.schema_manifest.get('canonical_field_collisions', {})
    feature_count = int(context.normalized_df.shape[1]) if context.normalized_df is not None else 0
    canonical_field_count = int(context.canonical_df.columns.nunique()) if context.canonical_df is not None else 0
    concept_count = int(context.concept_df.shape[1]) if context.concept_df is not None else 0
    return {
        'pipeline_version': FEATURE_PREPARATION_PIPELINE_VERSION,
        'schema_version': SCHEMA_PIPELINE_VERSION,
        'concept_version': CONCEPT_PIPELINE_VERSION,
        'feature_engineering_version': FEATURE_ENGINEERING_VERSION,
        'normalization_version': NORMALIZATION_VERSION,
        'pipeline_stages_completed': [
            'build_canonical_dataframe',
            'compute_business_concepts',
            'derive_engineered_features',
            'normalize_features',
            'prepare_model_input',
        ],
        'feature_count': feature_count,
        'canonical_field_count': canonical_field_count,
        'concept_count': concept_count,
        'normalization_strategy': NORMALIZATION_STRATEGY,
        'schema_resolution': context.schema_manifest,
        'concepts': context.concept_manifest,
        'concept_confidence': context.concept_confidence,
        'resolution_count': len(context.resolutions),
        'number_of_canonical_fields': canonical_field_count,
        'number_of_business_concepts': concept_count,
        'number_of_engineered_features': feature_count,
        'duplicate_columns_resolved': duplicate_columns_resolved,
    }


class FeaturePreparationPipeline:
    """Shared raw-data-to-model-input pipeline for universal training and prediction."""

    def run(
        self,
        raw_df: pd.DataFrame,
        sector: str,
        *,
        target_col: str | None = None,
        norm_stats: dict | None = None,
        include_target: bool = False,
        include_sector: bool = False,
    ) -> FeaturePreparationContext:
        """Execute all shared preparation stages and return the populated context."""
        context = FeaturePreparationContext(
            raw_df=raw_df.copy(),
            sector=sector,
            target_col=target_col,
            norm_stats=norm_stats,
        )
        self._build_canonical(context)
        self._compute_concepts(context)
        self._derive_features(context)
        normalize_features(context)
        prepare_model_input(
            context,
            include_target=include_target,
            include_sector=include_sector,
        )
        return context

    def _build_canonical(self, context: FeaturePreparationContext) -> None:
        canonical_df, resolutions, schema_manifest = build_canonical_dataframe(context.raw_df)
        context.canonical_df = canonical_df
        context.resolutions = resolutions
        context.schema_manifest = schema_manifest

    def _compute_concepts(self, context: FeaturePreparationContext) -> None:
        if context.canonical_df is None:
            raise ValueError("Cannot compute concepts before canonical fields exist.")
        concept_df, concept_confidence, concept_manifest = compute_business_concepts(
            context.canonical_df,
            context.sector,
        )
        context.concept_df = concept_df
        context.concept_confidence = concept_confidence
        context.concept_manifest = concept_manifest

    def _derive_features(self, context: FeaturePreparationContext) -> None:
        if context.canonical_df is None or context.concept_df is None:
            raise ValueError("Cannot derive features before canonical fields and concepts exist.")
        context.engineered_df = derive_engineered_features(
            canonical_df=context.canonical_df,
            raw_df=context.raw_df,
            sector=context.sector,
            norm_stats=context.norm_stats,
            concept_df=context.concept_df,
        )
        context.feature_manifest = {
            'feature_engineering_version': FEATURE_ENGINEERING_VERSION,
            'feature_count': int(context.engineered_df.shape[1]),
        }


def _prepare_training_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the existing training-time raw cleanup before shared preparation."""
    df_working = df.copy()
    if 'TotalCharges' in df_working.columns:
        df_working['TotalCharges'] = pd.to_numeric(
            df_working['TotalCharges'], errors='coerce'
        ).fillna(0)
    for col in df_working.select_dtypes(include='number').columns:
        df_working[col] = df_working[col].fillna(df_working[col].median())
    for col in df_working.select_dtypes(include=['object', 'string']).columns:
        mode = df_working[col].mode()
        df_working[col] = df_working[col].fillna(mode.iloc[0] if not mode.empty else '')
    return df_working


def _prepare_prediction_dataframe(df: pd.DataFrame, sector: str) -> pd.DataFrame:
    """Apply the existing prediction-time raw cleanup before shared preparation."""
    df_working = _prepare_training_dataframe(df)
    df_working = sanitize_numerical_columns(df_working)
    target_col = SECTOR_CONFIG[sector]['target_col']
    if target_col not in df_working.columns:
        df_working[target_col] = 0
    return df_working


def prepare_training_features(
    df: pd.DataFrame,
    sector: str,
    target_col: str,
    norm_stats: dict | None = None,
    norm_columns: list[str] | None = None,
) -> pd.DataFrame:
    """
    Prepare universal training features through the shared pipeline.

    When a mutable norm_stats dict is supplied, it is updated in-place
    with this sector's legacy max-normalization statistics, matching
    the historical train_universal_model behavior.
    """
    prepared_df = _prepare_training_dataframe(df)
    if norm_stats is not None:
        norm_stats.update(compute_norm_stats(
            prepared_df,
            sector,
            norm_columns if norm_columns is not None else SECTOR_NORM_COLUMNS.get(sector, []),
        ))

    context = FeaturePreparationPipeline().run(
        prepared_df,
        sector,
        target_col=target_col,
        norm_stats=norm_stats,
        include_target=True,
        include_sector=True,
    )
    if context.model_input_df is None:
        raise RuntimeError("Feature preparation did not produce training model input.")
    return context.model_input_df


def prepare_prediction_features(df: pd.DataFrame, sector: str) -> pd.DataFrame:
    """Prepare universal prediction features through the shared pipeline."""
    prepared_df = _prepare_prediction_dataframe(df, sector)
    norm_stats = joblib.load(UNIVERSAL_NORM_STATS_PATH) if UNIVERSAL_NORM_STATS_PATH.exists() else None

    context = FeaturePreparationPipeline().run(
        prepared_df,
        sector,
        target_col=SECTOR_CONFIG[sector]['target_col'],
        norm_stats=norm_stats,
        include_target=True,
        include_sector=True,
    )
    if context.model_input_df is None:
        raise RuntimeError("Feature preparation did not produce prediction model input.")

    features = context.model_input_df.copy()
    le_path = str(UNIVERSAL_MODEL_PATH).replace('.pkl', '_le_sector.pkl')
    if Path(le_path).exists():
        le_sector = joblib.load(le_path)
        if sector in set(le_sector.classes_):
            features['Sector_Encoded'] = le_sector.transform([sector])[0]
        else:
            features['Sector_Encoded'] = 0

    model_input = features.drop(columns=['Churn', 'Sector'], errors='ignore')
    if UNIVERSAL_FEATURES_PATH.exists():
        expected_features = pd.read_csv(UNIVERSAL_FEATURES_PATH).iloc[:, 0].tolist()
        for col in expected_features:
            if col not in model_input.columns:
                model_input[col] = 0
        model_input = model_input[expected_features]

    model_input.attrs['feature_engineering_manifest'] = context.pipeline_manifest
    return model_input


def extract_universal_features(
    df: pd.DataFrame,
    sector: str,
    target_col: str,
    norm_stats: dict | None = None,
) -> pd.DataFrame:
    """
    Map sector-specific input into the UNIVERSAL_FEATURES space.

    The public contract stays unchanged, but the implementation now
    stages the data through canonical fields and business concepts
    before building the final engineered feature matrix.
    """
    context = FeaturePreparationPipeline().run(
        df,
        sector,
        target_col=target_col,
        norm_stats=norm_stats,
        include_target=True,
        include_sector=True,
    )
    if context.model_input_df is None:
        raise RuntimeError("Feature preparation did not produce universal features.")
    return context.model_input_df


def transform_features_by_sector(df: pd.DataFrame, sector: str) -> pd.DataFrame:
    """
    Convert an inference DataFrame to the universal model feature matrix.
    Used exclusively by predict_universal() — mirrors extract_universal_features()
    but operates on already-read inference data (no target required).
    """
    return prepare_prediction_features(df, sector)
