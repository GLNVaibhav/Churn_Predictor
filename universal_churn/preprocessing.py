"""
universal_churn/preprocessing.py
Input sanitisation and sector auto-detection.
All functions are pure (no side effects on disk or global state).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from .config import SECTOR_SIGNATURES, MIN_SIGNATURE_HITS


def sanitize_numerical_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Strip unit suffixes and currency symbols from columns that must be numeric.
    e.g. '12 months' → 12.0, '₹85.50' → 85.5
    """
    numeric_targets = {
        'tenure', 'monthlycharges', 'totalcharges', 'age',
        'visitslastyear', 'avgoutofpocketcost', 'billingissues',
        'creditscore', 'balance', 'numofproducts', 'satisfactionscore',
        'cashbackamount', 'tenuremonths', 'daysincelastvisit',
        'overallsatisfaction', 'waittimesatisfaction', 'staffsatisfaction',
        'providerrating', 'portalusage', 'referralsmade',
        'distancetofacilitymiles', 'missedappointments', 'daysincelastorder',
        'couponused', 'ordercount', 'warehousetohome', 'hourspendonapp',
        'numberofdeviceregistered', 'numberofaddress',
        'orderamounthikefromlastyear', 'estimatedsalary',
    }

    df_clean = df.copy()
    lower_cols = (
        df_clean.columns.str.lower()
        .str.replace(' ', '', regex=False)
        .str.replace('_', '', regex=False)
    )
    col_mapping = dict(zip(df_clean.columns, lower_cols))

    for original_col, standardized_name in col_mapping.items():
        if standardized_name in numeric_targets:
            raw = df_clean[original_col].astype(object).astype(str).str.strip()
            s_clean = raw.str.replace(r'[^\d\.\-]', '', regex=True)
            s_clean = s_clean.replace('', np.nan)
            df_clean[original_col] = pd.to_numeric(
                s_clean, errors='coerce').astype('float64')

    return df_clean


def derive_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect date columns and derive numeric days-since columns.
    Patterns → derived column:
      lastinteraction/lastvisit/lastappointment/lastcontact/lastseen
          → Days_Since_Last_Visit
      lastorder/lastpurchase → DaySinceLastOrder
    """
    df_out = df.copy()
    today = pd.Timestamp.now().normalize()

    patterns = [
        ('lastinteraction', 'Days_Since_Last_Visit'),
        ('lastvisit', 'Days_Since_Last_Visit'),
        ('lastappointment', 'Days_Since_Last_Visit'),
        ('lastcontact', 'Days_Since_Last_Visit'),
        ('lastseen', 'Days_Since_Last_Visit'),
        ('lastorder', 'DaySinceLastOrder'),
        ('lastpurchase', 'DaySinceLastOrder'),
    ]

    for original_col in df.columns:
        normalized = original_col.lower().replace(' ', '').replace('_', '')
        for pattern, derived_col in patterns:
            if pattern in normalized:
                if derived_col in df_out.columns:
                    break
                try:
                    parsed = pd.to_datetime(
                        df_out[original_col],
                        infer_datetime_format=True,
                        errors='coerce')
                    days = (today - parsed).dt.days.clip(lower=0)
                    if days.notna().any():
                        df_out[derived_col] = days.fillna(days.median())
                        print(f"  [temporal] '{original_col}' → '{derived_col}'")
                except Exception:
                    pass
                break

    return df_out


def detect_sector(df: pd.DataFrame) -> str:
    """
    Inspect a DataFrame's column names and return the best-matching sector key.
    Raises ValueError if no sector reaches MIN_SIGNATURE_HITS or if there's a tie.
    """
    normalized_cols = {
        c.strip().lower().replace(' ', '').replace('_', '')
        for c in df.columns
    }
    scores = {}
    for sector, variants in SECTOR_SIGNATURES.items():
        best = 0
        for signature in variants:
            # FIX: replace '_' with '' (not ' ') so 'visits_last_year' → 'visitslastyear'
            sig_norm = {s.replace(' ', '').replace('_', '') for s in signature}
            best = max(best, len(normalized_cols & sig_norm))
        scores[sector] = best

    best_sector = max(scores, key=scores.get)
    best_score = scores[best_sector]

    if best_score < MIN_SIGNATURE_HITS:
        raise ValueError(
            f"Could not auto-detect sector (best: '{best_sector}' with only "
            f"{best_score} signature columns). Pass --sector explicitly. "
            f"Columns seen: {list(df.columns)}"
        )

    top_sectors = [s for s, sc in scores.items() if sc == best_score]
    if len(top_sectors) > 1:
        raise ValueError(
            f"Ambiguous sector match between {top_sectors} "
            f"(each scored {best_score} hits). Pass --sector explicitly."
        )

    return best_sector


def apply_sector_threshold(probas: np.ndarray, sector: str) -> np.ndarray:
    """Apply the sector-specific decision threshold to raw probabilities."""
    from .config import SECTOR_THRESHOLDS
    threshold = SECTOR_THRESHOLDS.get(sector, 0.50)
    return (probas >= threshold).astype(int)