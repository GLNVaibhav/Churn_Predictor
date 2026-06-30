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


def normalize_target(series: pd.Series) -> pd.Series:
    """
    Single source of truth for binary target normalization across every
    training pipeline (SectorPipeline, train_universal_model, and any
    future pipeline). Accepts a pandas Series of mixed/raw label
    representations and returns a clean int64 Series of {0, 1}.

    Supported representations (case-insensitive, whitespace-trimmed):
        0, 1, "0", "1", "yes", "no", "true", "false", True, False

    Unknown values are NEVER silently coerced — raises ValueError
    listing every unexpected label found, so a genuinely malformed or
    unanticipated label format fails loudly during training rather than
    surfacing later as a cryptic mixed-type error inside scikit-learn.
    """
    if pd.api.types.is_bool_dtype(series):
        return series.astype(int)

    if pd.api.types.is_numeric_dtype(series):
        unique_vals = set(series.dropna().unique())
        unexpected = unique_vals - {0, 1}
        if unexpected:
            raise ValueError(
                f"normalize_target: unexpected numeric label(s) {sorted(unexpected)} "
                f"found in target column. Only 0/1 are supported numeric labels."
            )
        return series.astype(int)

    # Treat as string-like: trim whitespace, lowercase, then map.
    cleaned = series.astype(str).str.strip().str.lower()

    label_map = {
        '0': 0, '1': 1,
        'yes': 1, 'no': 0,
        'true': 1, 'false': 0,
    }

    mapped = cleaned.map(label_map)

    unmapped_mask = mapped.isna() & series.notna()
    if unmapped_mask.any():
        unexpected_labels = sorted(series[unmapped_mask].astype(str).unique())
        raise ValueError(
            f"normalize_target: encountered unsupported target label(s) "
            f"{unexpected_labels}. Supported labels are: "
            f"0, 1, '0', '1', 'Yes', 'No', 'True', 'False' "
            f"(case-insensitive, whitespace-trimmed). "
            f"Update normalize_target() if a new label format is genuinely valid — "
            f"do not coerce it ad hoc elsewhere."
        )

    return mapped.astype(int)


def validate_target_types(y, context: str = "") -> None:
    """
    Lightweight pre-flight check, intended to run immediately before
    every train_test_split(..., stratify=y) call. Confirms the target
    is a single, consistent Python type and dtype before handing it to
    scikit-learn — so a mixed-type target (e.g. some rows still 'Yes'/
    'No' strings, others already int, after a multi-sector concat)
    fails with a clear, actionable message here instead of a cryptic
    "'<' not supported between instances of 'str' and 'int'" deep
    inside NumPy's np.unique() during stratification.

    `y` may be a pandas Series or a numpy array (train_test_split
    accepts either, and callers pass both across this codebase).
    `context` is an optional label (e.g. the calling function's name)
    included in the error message to speed up debugging.
    """
    arr = y.values if isinstance(y, pd.Series) else np.asarray(y)

    python_types = {type(v) for v in arr}
    if len(python_types) > 1:
        type_names = sorted(t.__name__ for t in python_types)
        where = f" ({context})" if context else ""
        raise TypeError(
            f"Target column contains mixed label types: {{{', '.join(type_names)}}}"
            f"{where}. Run normalize_target() first."
        )

    unique_labels = set(arr.tolist())
    if not unique_labels.issubset({0, 1}):
        where = f" ({context})" if context else ""
        raise ValueError(
            f"Target column contains non-binary label(s) {sorted(unique_labels)}"
            f"{where}. Run normalize_target() first."
        )


def apply_sector_threshold(probas: np.ndarray, sector: str) -> np.ndarray:
    """Apply the sector-specific decision threshold to raw probabilities."""
    from .config import SECTOR_THRESHOLDS
    threshold = SECTOR_THRESHOLDS.get(sector, 0.50)
    return (probas >= threshold).astype(int)