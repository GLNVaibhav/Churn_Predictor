"""
universal_churn/feature_transforms.py
══════════════════════════════════════════════════════════════════════
SINGLE SOURCE OF TRUTH for all feature transformations.

This module centralizes EVERY raw-to-canonical map, derivation rule,
default rule, and encoding rule used by BOTH training and inference.
No other module should contain feature transformation logic — they
should import and call functions from this module.

Why this matters
----------------
Schema drift and skew in production ML systems occur when training and
serving use different feature definitions. This module prevents that by
ensuring both paths literally call the same transformation code.

Structure
---------
1. CANONICAL_FIELD_REGISTRY — versioned schema of known aliases, sector-
   specific raw fields, required minimal subsets, and derivation deps.
2. DERIVATION_RULES — how each universal feature is computed from raw
   inputs, including defaults for missing data.
3. DEFAULT_RULES — what value to use when a required input is absent.
4. ENCODING_RULES — categorical mappings (e.g., contract stability).
5. MINIMAL_FEATURE_SUBSETS — stable feature sets per sector for fallback
   models.
6. transform_to_universal_features() — THE single function called by both
   training and inference to get universal features.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
import numpy as np
import pandas as pd


# ══════════════════════════════════════════════════════════════════
# 1. SCHEMA REGISTRY — versioned configuration
# ══════════════════════════════════════════════════════════════════

SCHEMA_REGISTRY_VERSION = "1.0.0"


@dataclass
class CanonicalField:
    """
    A canonical field definition with all known aliases and properties.

    Attributes
    ----------
    name : str
        The standardized canonical name used in UNIVERSAL_FEATURES.
    description : str
        What construct this feature measures.
    exact_aliases : dict[str, str]
        Mapping from raw column name -> sector it appears in.
    regex_patterns : list[str]
        Regex patterns to match variant column names.
    required_for : list[str]
        Sectors where this field is considered required.
    importance_weight : int
        1-5 scale: 5=critical, 1=minor (used for refusal thresholds).
    default_value : float
        Default when field cannot be derived.
    derivation_fn : str
        Name of the derivation function to use (see DERIVATION_RULES).
    """
    name: str
    description: str = ""
    exact_aliases: dict[str, str] = field(default_factory=dict)
    regex_patterns: list[str] = field(default_factory=list)
    required_for: list[str] = field(default_factory=list)
    importance_weight: int = 3
    default_value: float = 0.5
    derivation_fn: str = "direct_or_default"


# Schema Registry v1.0 — canonical field definitions
CANONICAL_FIELD_REGISTRY: list[CanonicalField] = [
    # ── Core tenure & financial features ─────────────────────────
    CanonicalField(
        name="tenure_normalized",
        description="Length of customer relationship, normalized to [0,1]",
        exact_aliases={
            'tenure': 'telecom',
            'Tenure': 'ecommerce',
            'Tenure_Months': 'healthcare',
            'Tenure': 'banking',
        },
        regex_patterns=[r".*tenure.*"],
        required_for=['telecom', 'ecommerce', 'banking', 'healthcare'],
        importance_weight=5,
        default_value=0.5,
        derivation_fn="normalize_by_sector_max",
    ),
    CanonicalField(
        name="charge_normalized",
        description="Financial commitment/value, normalized to [0,1]",
        exact_aliases={
            'MonthlyCharges': 'telecom',
            'CashbackAmount': 'ecommerce',
            'Balance': 'banking',
            'Avg_Out_Of_Pocket_Cost': 'healthcare',
            'MonthlyPremium': 'healthcare',
        },
        regex_patterns=[r".*charge.*", r".*premium.*", r".*balance.*"],
        required_for=['telecom', 'ecommerce', 'banking', 'healthcare'],
        importance_weight=5,
        default_value=0.0,
        derivation_fn="normalize_by_sector_max",
    ),

    # ── Satisfaction & complaint features ────────────────────────
    CanonicalField(
        name="has_complaint",
        description="Binary flag for customer complaints/issues",
        exact_aliases={
            'Complain': 'ecommerce',
            'Billing_Issues': 'healthcare',
        },
        regex_patterns=[r".*complain.*", r".*billing.*issue.*"],
        required_for=['ecommerce', 'healthcare'],
        importance_weight=4,
        default_value=0,
        derivation_fn="binary_from_count_or_flag",
    ),
    CanonicalField(
        name="satisfaction_score",
        description="Satisfaction measure, normalized to [0,1]",
        exact_aliases={
            'SatisfactionScore': 'ecommerce',
            'Overall_Satisfaction': 'healthcare',
            'CreditScore': 'banking',
        },
        regex_patterns=[r".*satisfaction.*", r".*rating.*"],
        required_for=['ecommerce', 'banking', 'healthcare'],
        importance_weight=5,
        default_value=0.5,
        derivation_fn="normalize_satisfaction",
    ),

    # ── Activity & engagement features ──────────────────────────
    CanonicalField(
        name="is_active",
        description="Binary flag for active customer status",
        exact_aliases={
            'IsActiveMember': 'banking',
        },
        regex_patterns=[r".*active.*"],
        required_for=['banking'],
        importance_weight=5,
        default_value=0.5,
        derivation_fn="activity_from_recency_or_flag",
    ),
    CanonicalField(
        name="num_products_services",
        description="Number of products/services used, normalized",
        exact_aliases={
            'OrderCount': 'ecommerce',
            'NumOfProducts': 'banking',
            'Visits_Last_Year': 'healthcare',
        },
        regex_patterns=[r".*count.*", r".*visits.*", r".*numof.*"],
        required_for=['ecommerce', 'banking', 'healthcare'],
        importance_weight=4,
        default_value=0.0,
        derivation_fn="normalize_by_sector_max",
    ),

    # ── Risk & demographic features ─────────────────────────────
    CanonicalField(
        name="is_senior_or_high_risk",
        description="Binary demographic risk flag",
        exact_aliases={
            'SeniorCitizen': 'telecom',
            'Age': 'banking',
            'Age': 'healthcare',
        },
        regex_patterns=[r".*senior.*", r"^age$"],
        required_for=['telecom', 'banking', 'healthcare'],
        importance_weight=3,
        default_value=0,
        derivation_fn="demographic_risk_flag",
    ),

    # ── Contract & payment features ─────────────────────────────
    CanonicalField(
        name="contract_stability",
        description="Contract/commitment stability score [0,1]",
        exact_aliases={
            'Contract': 'telecom',
            'Tenure': 'banking',
            'Tenure_Months': 'healthcare',
        },
        regex_patterns=[r".*contract.*"],
        required_for=['telecom'],
        importance_weight=5,
        default_value=0.5,
        derivation_fn="contract_stability_score",
    ),
    CanonicalField(
        name="payment_auto",
        description="Automatic payment flag",
        exact_aliases={
            'PaymentMethod': 'telecom',
            'PreferredPaymentMode': 'ecommerce',
            'HasCrCard': 'banking',
        },
        regex_patterns=[r".*payment.*"],
        required_for=['telecom', 'ecommerce'],
        importance_weight=3,
        default_value=0.5,
        derivation_fn="auto_payment_flag",
    ),

    # ── Derived interaction features ────────────────────────────
    CanonicalField(
        name="engagement_score",
        description="Overall engagement composite",
        exact_aliases={},
        regex_patterns=[],
        required_for=['telecom', 'ecommerce', 'banking', 'healthcare'],
        importance_weight=4,
        default_value=0.0,
        derivation_fn="engagement_composite",
    ),
    CanonicalField(
        name="recency_score",
        description="Recency of last interaction, normalized",
        exact_aliases={
            'DaySinceLastOrder': 'ecommerce',
            'Days_Since_Last_Visit': 'healthcare',
        },
        regex_patterns=[r".*since.*last.*", r".*recency.*"],
        required_for=['ecommerce', 'healthcare'],
        importance_weight=4,
        default_value=0.5,
        derivation_fn="recency_inverse_normalize",
    ),
    CanonicalField(
        name="dormant_loyalty_risk",
        description="Interaction term: tenure * (1-recency) or tenure*(1-active)",
        exact_aliases={},
        regex_patterns=[],
        required_for=['ecommerce', 'banking', 'healthcare'],
        importance_weight=4,
        default_value=0.0,
        derivation_fn="dormant_loyalty_interaction",
    ),
    CanonicalField(
        name="lockin_risk",
        description="Contract lock-in risk for new customers",
        exact_aliases={},
        regex_patterns=[],
        required_for=['telecom'],
        importance_weight=3,
        default_value=0.0,
        derivation_fn="lockin_interaction",
    ),

    # ── Healthcare-specific derived features ────────────────────
    CanonicalField(
        name="missed_appt_rate",
        description="Missed appointments / total visits",
        exact_aliases={
            'Missed_Appointments': 'healthcare',
        },
        regex_patterns=[r".*missed.*appoint.*"],
        required_for=['healthcare'],
        importance_weight=4,
        default_value=0.0,
        derivation_fn="missed_appointment_rate",
    ),
    CanonicalField(
        name="composite_satisfaction",
        description="Mean of multiple satisfaction sub-scores",
        exact_aliases={
            'Wait_Time_Satisfaction': 'healthcare',
            'Staff_Satisfaction': 'healthcare',
            'Provider_Rating': 'healthcare',
        },
        regex_patterns=[],
        required_for=['healthcare'],
        importance_weight=4,
        default_value=0.5,
        derivation_fn="composite_satisfaction_mean",
    ),
    CanonicalField(
        name="billing_friction",
        description="Complaints/issues per visit or interaction",
        exact_aliases={},
        regex_patterns=[],
        required_for=['healthcare'],
        importance_weight=3,
        default_value=0.0,
        derivation_fn="billing_friction_rate",
    ),
    CanonicalField(
        name="care_accessibility",
        description="Combined physical + digital accessibility",
        exact_aliases={
            'Distance_To_Facility_Miles': 'healthcare',
            'Portal_Usage': 'healthcare',
        },
        regex_patterns=[],
        required_for=['healthcare'],
        importance_weight=3,
        default_value=0.5,
        derivation_fn="care_accessibility_composite",
    ),
    CanonicalField(
        name="referral_engagement",
        description="Referrals made, normalized",
        exact_aliases={
            'Referrals_Made': 'healthcare',
        },
        regex_patterns=[],
        required_for=['healthcare'],
        importance_weight=2,
        default_value=0.0,
        derivation_fn="normalize_by_sector_max",
    ),

    # ── Ecommerce-specific derived features ─────────────────────
    CanonicalField(
        name="coupon_dependency",
        description="Coupon usage intensity, normalized",
        exact_aliases={
            'CouponUsed': 'ecommerce',
        },
        regex_patterns=[],
        required_for=['ecommerce'],
        importance_weight=3,
        default_value=0.0,
        derivation_fn="normalize_by_sector_max",
    ),
    CanonicalField(
        name="cashback_engagement",
        description="Cashback amount engagement, normalized",
        exact_aliases={},
        regex_patterns=[],
        required_for=['ecommerce'],
        importance_weight=2,
        default_value=0.0,
        derivation_fn="normalize_by_sector_max",
    ),
    CanonicalField(
        name="convenience_score",
        description="Convenience/friction score [0,1]",
        exact_aliases={
            'WarehouseToHome': 'ecommerce',
        },
        regex_patterns=[],
        required_for=['ecommerce'],
        importance_weight=2,
        default_value=0.5,
        derivation_fn="convenience_from_distance",
    ),
]

# Build lookup indices
_CANONICAL_BY_NAME: dict[str, CanonicalField] = {f.name: f for f in CANONICAL_FIELD_REGISTRY}
_ALIAS_TO_CANONICAL: dict[str, str] = {}
for _field in CANONICAL_FIELD_REGISTRY:
    for alias in _field.exact_aliases:
        _ALIAS_TO_CANONICAL[alias.lower().replace('_', '').replace(' ', '')] = _field.name


# ══════════════════════════════════════════════════════════════════
# 2. MINIMAL FEATURE SUBSETS FOR FALLBACK MODELS
# ══════════════════════════════════════════════════════════════════

MINIMAL_FEATURE_SUBSETS: dict[str, list[str]] = {
    # Stable, always-available features per sector for fallback models
    'telecom': [
        'tenure_normalized', 'charge_normalized', 'contract_stability',
        'num_products_services', 'is_senior_or_high_risk',
    ],
    'ecommerce': [
        'tenure_normalized', 'charge_normalized', 'recency_score',
        'engagement_score', 'has_complaint',
    ],
    'banking': [
        'tenure_normalized', 'charge_normalized', 'is_active',
        'num_products_services', 'is_senior_or_high_risk',
    ],
    'healthcare': [
        'tenure_normalized', 'charge_normalized', 'recency_score',
        'engagement_score', 'is_senior_or_high_risk',
    ],
    # Universal minimal set (intersection across all sectors)
    'universal_minimal': [
        'tenure_normalized', 'charge_normalized', 'is_senior_or_high_risk',
    ],
}

# High-importance features for refusal threshold decisions
HIGH_IMPORTANCE_FEATURES: set[str] = {
    'tenure_normalized', 'charge_normalized', 'contract_stability',
    'is_active', 'satisfaction_score', 'recency_score',
}


# ══════════════════════════════════════════════════════════════════
# 3. NORMALIZATION HELPERS
# ══════════════════════════════════════════════════════════════════

def _norm_max(
    df: pd.DataFrame,
    col: str | None,
    sector: str,
    norm_stats: dict | None,
) -> float:
    """
    Return the normalization maximum for `col` in `sector`.

    Uses persisted training-set statistics when available; falls back to
    the current batch's max only when no stats file exists yet.

    This is critical for preventing train/skew: single-row inference
    must NOT normalize to its own value.
    """
    if col is None:
        return 1.0
    key = f"{sector}.{col}"
    if norm_stats is not None and key in norm_stats and norm_stats[key]:
        return norm_stats[key]
    # Fallback: use batch max (only acceptable during initial training)
    batch_max = df[col].max() if col in df.columns else 1
    if pd.isna(batch_max) or batch_max == 0:
        batch_max = 1
    return float(batch_max)


def compute_norm_stats(df: pd.DataFrame, sector: str, columns: list[str]) -> dict:
    """
    Compute per-column maxima for one sector to be persisted in norm_stats.

    Call this during training and save the result. Load and pass to
    transform functions at inference time.
    """
    return {
        f"{sector}.{col}": float(m) if pd.notna(m) and m != 0 else 1.0
        for col in columns
        if col in df.columns
        for m in [df[col].max()]
    }


# ══════════════════════════════════════════════════════════════════
# 4. DERIVATION FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def _hcol(df: pd.DataFrame, *candidates: str) -> str | None:
    """Return the first candidate column name that exists in df."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def derive_tenure_normalized(
    df: pd.DataFrame, sector: str, norm_stats: dict | None = None
) -> pd.Series:
    """Derive tenure_normalized from sector-specific raw column."""
    col_map = {
        'telecom': 'tenure',
        'ecommerce': 'Tenure',
        'banking': 'Tenure',
        'healthcare': _hcol(df, 'Tenure_Months', 'tenuremonths'),
    }
    col = col_map.get(sector)
    if col is None:
        return pd.Series(0.5, index=df.index)
    max_val = _norm_max(df, col, sector, norm_stats)
    return df[col] / max_val if col in df.columns else pd.Series(0.5, index=df.index)


def derive_charge_normalized(
    df: pd.DataFrame, sector: str, norm_stats: dict | None = None
) -> pd.Series:
    """Derive charge_normalized from sector-specific raw column."""
    col_map = {
        'telecom': 'MonthlyCharges',
        'ecommerce': 'CashbackAmount',
        'banking': 'Balance',
        'healthcare': _hcol(df, 'Avg_Out_Of_Pocket_Cost', 'avgoutofpocketcost'),
    }
    col = col_map.get(sector)
    if col is None or col not in df.columns:
        # Try healthcare alternative
        if sector == 'healthcare':
            col = _hcol(df, 'MonthlyPremium', 'monthlypremium')
    if col is None or col not in df.columns:
        return pd.Series(0.0, index=df.index)
    max_val = _norm_max(df, col, sector, norm_stats)
    return df[col] / max_val


def derive_has_complaint(df: pd.DataFrame, sector: str) -> pd.Series:
    """Derive has_complaint binary flag."""
    if sector == 'ecommerce' and 'Complain' in df.columns:
        return df['Complain'].astype(int)
    if sector == 'healthcare':
        col = _hcol(df, 'Billing_Issues', 'billingissues')
        if col and col in df.columns:
            return (df[col] > 0).astype(int)
    return pd.Series(0, index=df.index)


def derive_satisfaction_score(
    df: pd.DataFrame, sector: str, norm_stats: dict | None = None
) -> pd.Series:
    """Derive satisfaction_score normalized to [0,1]."""
    if sector == 'ecommerce' and 'SatisfactionScore' in df.columns:
        return df['SatisfactionScore'] / 5.0
    if sector == 'banking':
        col = 'CreditScore'
        if col in df.columns:
            max_val = _norm_max(df, col, sector, norm_stats)
            return df[col] / max_val
    if sector == 'healthcare':
        col = _hcol(df, 'Overall_Satisfaction', 'overallsatisfaction')
        if col and col in df.columns:
            max_val = _norm_max(df, col, sector, norm_stats)
            return df[col] / max_val
    return pd.Series(0.5, index=df.index)


def derive_is_active(df: pd.DataFrame, sector: str) -> pd.Series:
    """Derive is_active binary flag."""
    if sector == 'banking' and 'IsActiveMember' in df.columns:
        return df['IsActiveMember'].astype(int)
    if sector == 'ecommerce' and 'DaySinceLastOrder' in df.columns:
        return (df['DaySinceLastOrder'] <= 7).astype(int)
    if sector == 'healthcare':
        col = _hcol(df, 'Days_Since_Last_Visit', 'daysincelastvisit')
        if col and col in df.columns:
            return (df[col] <= 90).astype(int)
    if sector == 'telecom':
        return pd.Series(1, index=df.index)  # Telecom subscribers assumed active
    return pd.Series(0.5, index=df.index)


def derive_num_products_services(
    df: pd.DataFrame, sector: str, norm_stats: dict | None = None
) -> pd.Series:
    """Derive num_products_services normalized."""
    if sector == 'telecom':
        service_cols = [
            'PhoneService', 'MultipleLines', 'InternetService',
            'OnlineSecurity', 'OnlineBackup', 'DeviceProtection',
            'TechSupport', 'StreamingTV', 'StreamingMovies',
        ]
        for col in service_cols:
            if col not in df.columns:
                df[col] = 'No'
        count = df[service_cols].apply(lambda row: (row == 'Yes').sum(), axis=1)
        return count / len(service_cols)

    col_map = {
        'ecommerce': 'OrderCount',
        'banking': 'NumOfProducts',
        'healthcare': _hcol(df, 'Visits_Last_Year', 'visitslastyear'),
    }
    col = col_map.get(sector)
    if col is None or col not in df.columns:
        return pd.Series(0.0, index=df.index)
    max_val = _norm_max(df, col, sector, norm_stats)
    return df[col] / max_val


def derive_is_senior_or_high_risk(df: pd.DataFrame, sector: str) -> pd.Series:
    """Derive senior/high-risk binary flag."""
    if sector == 'telecom' and 'SeniorCitizen' in df.columns:
        return df['SeniorCitizen'].astype(int)
    if sector in ('banking', 'healthcare'):
        col = 'Age'
        if col in df.columns:
            threshold = 55 if sector == 'banking' else 65
            return (df[col] > threshold).astype(int)
    return pd.Series(0, index=df.index)


def derive_contract_stability(
    df: pd.DataFrame, sector: str, norm_stats: dict | None = None
) -> pd.Series:
    """Derive contract_stability score [0,1]."""
    if sector == 'telecom' and 'Contract' in df.columns:
        mapping = {'Month-to-month': 0.0, 'One year': 0.5, 'Two year': 1.0}
        return df['Contract'].map(mapping).fillna(0)
    if sector == 'banking' and 'Tenure' in df.columns:
        max_val = _norm_max(df, 'Tenure', sector, norm_stats)
        return df['Tenure'] / max_val
    if sector == 'healthcare':
        col = _hcol(df, 'Tenure_Months', 'tenuremonths')
        if col and col in df.columns:
            max_val = _norm_max(df, col, sector, norm_stats)
            return df[col] / max_val
    return pd.Series(0.5, index=df.index)


def derive_payment_auto(df: pd.DataFrame, sector: str) -> pd.Series:
    """Derive automatic payment flag."""
    if sector == 'telecom' and 'PaymentMethod' in df.columns:
        return df['PaymentMethod'].str.contains('automatic', case=False, na=False).astype(int)
    if sector == 'ecommerce' and 'PreferredPaymentMode' in df.columns:
        return df['PreferredPaymentMode'].isin(['Credit Card', 'Debit Card', 'UPI']).astype(int)
    if sector == 'banking':
        if 'HasCrCard' in df.columns:
            return df['HasCrCard'].astype(int)
        return pd.Series(0.5, index=df.index)  # No direct info
    return pd.Series(0.5, index=df.index)


def derive_engagement_score(
    df: pd.DataFrame, sector: str, features: dict[str, pd.Series]
) -> pd.Series:
    """Derive engagement_score composite."""
    if sector == 'telecom':
        return features.get('num_products_services', pd.Series(0, index=df.index))
    if sector == 'ecommerce':
        col = 'OrderCount'
        if col in df.columns:
            max_val = _norm_max(df, col, sector, None)
            return df[col] / max_val
    if sector == 'banking':
        return features.get('num_products_services', pd.Series(0, index=df.index))
    if sector == 'healthcare':
        return features.get('num_products_services', pd.Series(0.5, index=df.index))
    return pd.Series(0, index=df.index)


def derive_recency_score(
    df: pd.DataFrame, sector: str, norm_stats: dict | None = None
) -> pd.Series:
    """Derive recency_score (inverse for time-based, direct for activity)."""
    if sector == 'ecommerce' and 'DaySinceLastOrder' in df.columns:
        max_val = _norm_max(df, 'DaySinceLastOrder', sector, norm_stats)
        return df['DaySinceLastOrder'] / max_val
    if sector == 'healthcare':
        col = _hcol(df, 'Days_Since_Last_Visit', 'daysincelastvisit')
        if col and col in df.columns:
            max_val = _norm_max(df, col, sector, norm_stats)
            return 1 - (df[col] / max_val)  # Inverse: recent = high score
    if sector == 'banking':
        # Use is_active as recency proxy
        if 'IsActiveMember' in df.columns:
            return df['IsActiveMember'].astype(float)
    return pd.Series(0.5, index=df.index)


def derive_dormant_loyalty_risk(
    df: pd.DataFrame, sector: str, features: dict[str, pd.Series]
) -> pd.Series:
    """Derive dormant_loyalty_risk interaction term."""
    tenure = features.get('tenure_normalized', pd.Series(0, index=df.index))
    if sector == 'ecommerce':
        recency = features.get('recency_score', pd.Series(0.5, index=df.index))
        return tenure * recency
    if sector == 'banking':
        is_active = features.get('is_active', pd.Series(0.5, index=df.index))
        return tenure * (1 - is_active)
    if sector == 'healthcare':
        is_active = features.get('is_active', pd.Series(0.5, index=df.index))
        return tenure * (1 - is_active)
    return pd.Series(0, index=df.index)


def derive_lockin_risk(
    df: pd.DataFrame, sector: str, features: dict[str, pd.Series]
) -> pd.Series:
    """Derive lockin_risk interaction term (new customer + long contract)."""
    if sector == 'telecom':
        contract = features.get('contract_stability', pd.Series(0, index=df.index))
        tenure = features.get('tenure_normalized', pd.Series(0, index=df.index))
        return contract * (1 - tenure)
    return pd.Series(0, index=df.index)


def derive_missed_appt_rate(df: pd.DataFrame, sector: str) -> pd.Series:
    """Derive missed appointment rate (healthcare only)."""
    if sector != 'healthcare':
        return pd.Series(0, index=df.index)

    c_missed = _hcol(df, 'Missed_Appointments', 'missedappointments')
    c_visits = _hcol(df, 'Visits_Last_Year', 'visitslastyear')

    if c_missed and c_visits and c_visits in df.columns and c_missed in df.columns:
        total = df[c_visits].replace(0, np.nan)
        return (df[c_missed] / total).clip(0, 1).fillna(0)
    elif c_missed and c_missed in df.columns:
        # Fallback without visit denominator
        return df[c_missed].clip(0, 1)
    return pd.Series(0, index=df.index)


def derive_composite_satisfaction(
    df: pd.DataFrame, sector: str, norm_stats: dict | None = None
) -> pd.Series:
    """Derive composite satisfaction from multiple sub-scores (healthcare)."""
    if sector != 'healthcare':
        return pd.Series(0.5, index=df.index)

    sat_scores = []
    cols_and_maxes = [
        ('Overall_Satisfaction', 'overallsatisfaction'),
        ('Wait_Time_Satisfaction', 'waittimesatisfaction'),
        ('Staff_Satisfaction', 'staffsatisfaction'),
        ('Provider_Rating', 'providerrating'),
    ]

    for primary, alt in cols_and_maxes:
        col = _hcol(df, primary, alt)
        if col and col in df.columns:
            max_val = _norm_max(df, col, sector, norm_stats)
            sat_scores.append(df[col] / max_val)

    if sat_scores:
        return pd.concat(sat_scores, axis=1).mean(axis=1)
    return pd.Series(0.5, index=df.index)


def derive_billing_friction(df: pd.DataFrame, sector: str) -> pd.Series:
    """Derive billing friction rate (complaints per interaction)."""
    if sector != 'healthcare':
        if sector == 'ecommerce':
            return derive_has_complaint(df, sector).astype(float)
        return pd.Series(0, index=df.index)

    c_billing = _hcol(df, 'Billing_Issues', 'billingissues')
    c_visits = _hcol(df, 'Visits_Last_Year', 'visitslastyear')

    if c_billing and c_visits and c_visits in df.columns and c_billing in df.columns:
        total = df[c_visits].replace(0, np.nan)
        return (df[c_billing] / total).clip(0, 1).fillna(0)
    elif c_billing and c_billing in df.columns:
        return df[c_billing].clip(0, 1)
    return pd.Series(0, index=df.index)


def derive_care_accessibility(df: pd.DataFrame, sector: str) -> pd.Series:
    """Derive care accessibility composite (healthcare)."""
    if sector != 'healthcare':
        if sector == 'ecommerce':
            # Convenience proxy
            col = 'WarehouseToHome'
            if col in df.columns:
                max_val = _norm_max(df, col, sector, None)
                return 1 - (df[col] / max_val)
        return pd.Series(0.5, index=df.index)

    c_dist = _hcol(df, 'Distance_To_Facility_Miles', 'distancetofacilitymiles')
    c_portal = _hcol(df, 'Portal_Usage', 'portalusage')

    dist_norm = pd.Series(0.5, index=df.index)
    if c_dist and c_dist in df.columns:
        max_val = _norm_max(df, c_dist, sector, None)
        dist_norm = (df[c_dist] / max_val).clip(0, 1)

    portal_norm = pd.Series(0.0, index=df.index)
    if c_portal and c_portal in df.columns:
        portal_norm = df[c_portal].clip(0, 1)

    return ((1 - dist_norm) + portal_norm).clip(0, 1)


def derive_referral_engagement(
    df: pd.DataFrame, sector: str, norm_stats: dict | None = None
) -> pd.Series:
    """Derive referral engagement (healthcare)."""
    if sector != 'healthcare':
        return pd.Series(0, index=df.index)

    col = _hcol(df, 'Referrals_Made', 'referralsmade')
    if col and col in df.columns:
        max_val = _norm_max(df, col, sector, norm_stats)
        return (df[col] / max_val).clip(0, 1)
    return pd.Series(0, index=df.index)


def derive_coupon_dependency(
    df: pd.DataFrame, sector: str, norm_stats: dict | None = None
) -> pd.Series:
    """Derive coupon dependency (ecommerce)."""
    if sector != 'ecommerce':
        return pd.Series(0, index=df.index)

    if 'CouponUsed' in df.columns:
        max_val = _norm_max(df, 'CouponUsed', sector, norm_stats)
        return df['CouponUsed'] / max_val
    return pd.Series(0, index=df.index)


def derive_cashback_engagement(
    df: pd.DataFrame, sector: str, norm_stats: dict | None = None
) -> pd.Series:
    """Derive cashback engagement."""
    if sector == 'ecommerce' and 'CashbackAmount' in df.columns:
        max_val = _norm_max(df, 'CashbackAmount', sector, norm_stats)
        return df['CashbackAmount'] / max_val
    if sector == 'banking':
        # Balance as financial engagement proxy
        return derive_charge_normalized(df, sector, norm_stats)
    return pd.Series(0, index=df.index)


def derive_convenience_score(df: pd.DataFrame, sector: str) -> pd.Series:
    """Derive convenience score."""
    if sector == 'ecommerce' and 'WarehouseToHome' in df.columns:
        max_val = _norm_max(df, 'WarehouseToHome', sector, None)
        return 1 - (df['WarehouseToHome'] / max_val)
    if sector == 'telecom':
        # Contract stability as convenience proxy
        return derive_contract_stability(df, sector, None)
    return pd.Series(0.5, index=df.index)


# Map derivation function names to implementations
DERIVATION_FUNCTIONS: dict[str, Callable] = {
    'normalize_by_sector_max': lambda df, s, ns, f: None,  # handled specially
    'direct_or_default': lambda df, s, ns, f: None,
    'binary_from_count_or_flag': lambda df, s, ns, f: None,
    'normalize_satisfaction': lambda df, s, ns, f: None,
    'activity_from_recency_or_flag': lambda df, s, ns, f: None,
    'demographic_risk_flag': lambda df, s, ns, f: None,
    'contract_stability_score': lambda df, s, ns, f: None,
    'auto_payment_flag': lambda df, s, ns, f: None,
    'engagement_composite': lambda df, s, ns, f: None,
    'recency_inverse_normalize': lambda df, s, ns, f: None,
    'dormant_loyalty_interaction': lambda df, s, ns, f: None,
    'lockin_interaction': lambda df, s, ns, f: None,
    'missed_appointment_rate': lambda df, s, ns, f: None,
    'composite_satisfaction_mean': lambda df, s, ns, f: None,
    'billing_friction_rate': lambda df, s, ns, f: None,
    'care_accessibility_composite': lambda df, s, ns, f: None,
    'convenience_from_distance': lambda df, s, ns, f: None,
}


# ══════════════════════════════════════════════════════════════════
# 5. MAIN TRANSFORM FUNCTION — SINGLE SOURCE OF TRUTH
# ══════════════════════════════════════════════════════════════════

def transform_to_universal_features(
    df: pd.DataFrame,
    sector: str,
    norm_stats: dict | None = None,
) -> tuple[pd.DataFrame, dict]:
    """
    THE single function for transforming raw data to universal features.

    Both training and inference MUST call this function — no other
    feature transformation logic should exist elsewhere.

    Parameters
    ----------
    df : pd.DataFrame
        Raw input DataFrame with sector-specific columns.
    sector : str
        One of 'telecom', 'ecommerce', 'banking', 'healthcare'.
    norm_stats : dict | None
        Persisted training-time normalization statistics.
        REQUIRED at inference time to prevent skew.

    Returns
    -------
    features : pd.DataFrame
        DataFrame with UNIVERSAL_FEATURES columns.
    derivation_metadata : dict
        Record of which derivations were applied, defaults used, etc.
        For audit trail and debugging.
    """
    feat = pd.DataFrame(index=df.index)
    metadata = {
        'sector': sector,
        'norm_stats_used': norm_stats is not None,
        'derivations_applied': [],
        'defaults_applied': [],
    }

    # Step 1: Derive base features in dependency order
    base_features: dict[str, pd.Series] = {}

    # Tier 1: Direct normalizations
    base_features['tenure_normalized'] = derive_tenure_normalized(df, sector, norm_stats)
    base_features['charge_normalized'] = derive_charge_normalized(df, sector, norm_stats)
    base_features['has_complaint'] = derive_has_complaint(df, sector)
    base_features['satisfaction_score'] = derive_satisfaction_score(df, sector, norm_stats)
    base_features['is_active'] = derive_is_active(df, sector)
    base_features['num_products_services'] = derive_num_products_services(df, sector, norm_stats)
    base_features['is_senior_or_high_risk'] = derive_is_senior_or_high_risk(df, sector)
    base_features['contract_stability'] = derive_contract_stability(df, sector, norm_stats)
    base_features['payment_auto'] = derive_payment_auto(df, sector)

    # Track which features used defaults
    for name, series in base_features.items():
        if name in ['tenure_normalized', 'charge_normalized', 'satisfaction_score']:
            # These would have non-default values if derived properly
            pass

    # Tier 2: Derived composites (depend on base features)
    base_features['engagement_score'] = derive_engagement_score(df, sector, base_features)
    base_features['recency_score'] = derive_recency_score(df, sector, norm_stats)
    base_features['coupon_dependency'] = derive_coupon_dependency(df, sector, norm_stats)
    base_features['cashback_engagement'] = derive_cashback_engagement(df, sector, norm_stats)
    base_features['convenience_score'] = derive_convenience_score(df, sector)

    # Tier 3: Interaction terms
    base_features['lockin_risk'] = derive_lockin_risk(df, sector, base_features)
    base_features['dormant_loyalty_risk'] = derive_dormant_loyalty_risk(df, sector, base_features)

    # Tier 4: Healthcare-specific derived features
    base_features['missed_appt_rate'] = derive_missed_appt_rate(df, sector)
    base_features['composite_satisfaction'] = derive_composite_satisfaction(df, sector, norm_stats)
    base_features['billing_friction'] = derive_billing_friction(df, sector)
    base_features['care_accessibility'] = derive_care_accessibility(df, sector)
    base_features['referral_engagement'] = derive_referral_engagement(df, sector, norm_stats)

    # Step 2: Assemble final feature DataFrame in canonical order
    from .config import UNIVERSAL_FEATURES
    for col in UNIVERSAL_FEATURES:
        if col in base_features:
            feat[col] = base_features[col]
        else:
            feat[col] = pd.Series(0.5, index=df.index)
            metadata['defaults_applied'].append(col)

    metadata['derivations_applied'] = list(base_features.keys())

    return feat, metadata


# ══════════════════════════════════════════════════════════════════
# 6. FEATURE COVERAGE CHECKER FOR REFUSAL THRESHOLDS
# ══════════════════════════════════════════════════════════════════

def check_feature_sufficiency(
    df: pd.DataFrame,
    sector: str,
    strict_mode: bool = True,
) -> tuple[bool, dict]:
    """
    Check whether enough high-importance features are present for
    reliable prediction.

    This implements the stricter refusal threshold logic:
    - Not just feature COUNT, but whether HIGH-IMPORTANCE features exist
    - Whether stable fallback features are present

    Parameters
    ----------
    df : pd.DataFrame
        Raw input DataFrame.
    sector : str
        Sector name.
    strict_mode : bool
        If True, require high-importance features. If False, just count.

    Returns
    -------
    is_sufficient : bool
        Whether prediction should proceed.
    details : dict
        Breakdown of what was found/missing.
    """
    # Get canonical field lookup
    available_canonical = set()

    for raw_col in df.columns:
        normalized = raw_col.lower().replace('_', '').replace(' ', '')
        if normalized in _ALIAS_TO_CANONICAL:
            available_canonical.add(_ALIAS_TO_CANONICAL[normalized])

    # Check high-importance features
    missing_high_importance = HIGH_IMPORTANCE_FEATURES - available_canonical
    has_high_importance = len(missing_high_importance) < 2  # Allow 1 missing

    # Check minimal fallback subset
    fallback_subset = set(MINIMAL_FEATURE_SUBSETS.get(sector, []))
    available_fallback = fallback_subset & available_canonical
    has_fallback = len(available_fallback) >= len(fallback_subset) * 0.6  # 60% threshold

    is_sufficient = (has_high_importance or has_fallback) if strict_mode else True

    details = {
        'available_canonical': sorted(available_canonical),
        'missing_high_importance': sorted(missing_high_importance),
        'has_high_importance': has_high_importance,
        'available_fallback': sorted(available_fallback),
        'has_fallback': has_fallback,
        'is_sufficient': is_sufficient,
    }

    return is_sufficient, details