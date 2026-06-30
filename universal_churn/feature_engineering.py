"""
universal_churn/feature_engineering.py
────────────────────────────────────────
Universal feature extraction — maps each sector's raw columns to the
common UNIVERSAL_FEATURES space used by the Phase B cross-sector model.
"""
from __future__ import annotations

import joblib
import numpy as np
import pandas as pd

from .config import (
    SECTOR_CONFIG, SECTOR_NORM_COLUMNS, UNIVERSAL_FEATURES,
    UNIVERSAL_MODEL_PATH, UNIVERSAL_FEATURES_PATH, UNIVERSAL_NORM_STATS_PATH,
)
from .preprocessing import sanitize_numerical_columns, normalize_target


# ── Normalization helpers ─────────────────────────────────────────

def _norm_max(
    df: pd.DataFrame,
    col: str | None,
    sector: str,
    norm_stats: dict | None,
) -> float:
    """
    Return the normalization maximum for `col` in `sector`.
    Uses persisted training-set statistics when available; falls back to
    the current batch's max (which is incorrect for single-row inference
    but acceptable when no stats file exists yet).
    """
    if col is None:
        return 1.0
    key = f"{sector}.{col}"
    if norm_stats is not None and key in norm_stats and norm_stats[key]:
        return norm_stats[key]
    batch_max = df[col].max() if col in df.columns else 1
    if pd.isna(batch_max) or batch_max == 0:
        batch_max = 1
    return float(batch_max)


def compute_norm_stats(df: pd.DataFrame, sector: str, columns: list[str]) -> dict:
    """Compute per-column maxima for one sector to be persisted in norm_stats."""
    return {
        f"{sector}.{col}": float(m) if pd.notna(m) and m != 0 else 1.0
        for col in columns
        if col in df.columns
        for m in [df[col].max()]
    }


# ── Healthcare helper ─────────────────────────────────────────────

def _hcol(df: pd.DataFrame, *candidates: str) -> str | None:
    """Return the first candidate column name that exists in df."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


# ── Universal feature extraction ──────────────────────────────────

def extract_universal_features(
    df: pd.DataFrame,
    sector: str,
    target_col: str,
    norm_stats: dict | None = None,
) -> pd.DataFrame:
    """
    Map sector-specific raw columns into the UNIVERSAL_FEATURES space.
    Returns a DataFrame indexed like `df` with one column per feature.
    """
    feat = pd.DataFrame(index=df.index)

    if sector == 'telecom':
        max_tenure = _norm_max(df, 'tenure', sector, norm_stats)
        max_charge = _norm_max(df, 'MonthlyCharges', sector, norm_stats)

        feat['tenure_normalized']      = df['tenure'] / max_tenure if 'tenure' in df.columns else 0
        feat['charge_normalized']      = df['MonthlyCharges'] / max_charge if 'MonthlyCharges' in df.columns else 0
        feat['has_complaint']          = 0
        feat['satisfaction_score']     = 0.5
        feat['is_active']              = 1

        service_cols = [
            'PhoneService', 'MultipleLines', 'InternetService',
            'OnlineSecurity', 'OnlineBackup', 'DeviceProtection',
            'TechSupport', 'StreamingTV', 'StreamingMovies',
        ]
        for col in service_cols:
            if col not in df.columns:
                df[col] = 'No'
        feat['num_products_services']  = (
            df[service_cols].apply(lambda row: (row == 'Yes').sum(), axis=1)
            / len(service_cols)
        )
        feat['is_senior_or_high_risk'] = df['SeniorCitizen'] if 'SeniorCitizen' in df.columns else 0
        feat['has_support']            = (df['TechSupport'] == 'Yes').astype(int) if 'TechSupport' in df.columns else 0
        feat['contract_stability']     = df['Contract'].map(
            {'Month-to-month': 0.0, 'One year': 0.5, 'Two year': 1.0}
        ).fillna(0) if 'Contract' in df.columns else 0
        feat['payment_auto']           = df['PaymentMethod'].str.contains(
            'automatic', case=False, na=False
        ).astype(int) if 'PaymentMethod' in df.columns else 0

        feat['engagement_score']       = feat['num_products_services']
        feat['coupon_dependency']      = 0
        feat['cashback_engagement']    = 0
        feat['recency_score']          = 0.5
        feat['convenience_score']      = feat['contract_stability']
        feat['lockin_risk']            = feat['contract_stability'] * (1 - feat['tenure_normalized'])
        feat['dormant_loyalty_risk']   = 0
        feat['missed_appt_rate']       = 0
        feat['composite_satisfaction'] = feat['satisfaction_score']
        feat['billing_friction']       = 0
        feat['care_accessibility']     = 0.5
        feat['referral_engagement']    = 0

    elif sector == 'ecommerce':
        max_tenure  = _norm_max(df, 'Tenure',           sector, norm_stats)
        max_cash    = _norm_max(df, 'CashbackAmount',   sector, norm_stats)
        max_orders  = _norm_max(df, 'OrderCount',       sector, norm_stats)
        max_coupon  = _norm_max(df, 'CouponUsed',       sector, norm_stats)
        max_recency = _norm_max(df, 'DaySinceLastOrder', sector, norm_stats)
        max_dist    = _norm_max(df, 'WarehouseToHome',  sector, norm_stats)

        feat['tenure_normalized']      = df['Tenure'] / max_tenure if 'Tenure' in df.columns else 0
        feat['charge_normalized']      = df['CashbackAmount'] / max_cash if 'CashbackAmount' in df.columns else 0
        feat['has_complaint']          = df['Complain'] if 'Complain' in df.columns else 0
        feat['satisfaction_score']     = df['SatisfactionScore'] / 5.0 if 'SatisfactionScore' in df.columns else 0.5
        feat['is_active']              = (df['DaySinceLastOrder'] <= 7).astype(int) if 'DaySinceLastOrder' in df.columns else 0.5
        feat['num_products_services']  = df['OrderCount'] / max_orders if 'OrderCount' in df.columns else 0
        feat['is_senior_or_high_risk'] = 0
        feat['has_support']            = 0
        feat['contract_stability']     = 0
        feat['payment_auto']           = df['PreferredPaymentMode'].isin(
            ['Credit Card', 'Debit Card', 'UPI']
        ).astype(int) if 'PreferredPaymentMode' in df.columns else 0

        feat['engagement_score']       = df['OrderCount'] / max_orders if 'OrderCount' in df.columns else 0
        feat['coupon_dependency']      = df['CouponUsed'] / max_coupon if 'CouponUsed' in df.columns else 0
        feat['cashback_engagement']    = df['CashbackAmount'] / max_cash if 'CashbackAmount' in df.columns else 0
        feat['recency_score']          = df['DaySinceLastOrder'] / max_recency if 'DaySinceLastOrder' in df.columns else 0.5
        feat['convenience_score']      = 1 - (df['WarehouseToHome'] / max_dist) if 'WarehouseToHome' in df.columns else 0.5
        feat['dormant_loyalty_risk']   = feat['tenure_normalized'] * feat['recency_score']
        feat['lockin_risk']            = 0
        feat['missed_appt_rate']       = 0
        feat['composite_satisfaction'] = feat['satisfaction_score']
        feat['billing_friction']       = feat['has_complaint']
        feat['care_accessibility']     = feat['convenience_score']
        feat['referral_engagement']    = 0

    elif sector == 'banking':
        max_tenure  = _norm_max(df, 'Tenure',      sector, norm_stats)
        max_balance = _norm_max(df, 'Balance',     sector, norm_stats)
        max_credit  = _norm_max(df, 'CreditScore', sector, norm_stats)

        feat['tenure_normalized']      = df['Tenure'] / max_tenure if 'Tenure' in df.columns else 0
        feat['charge_normalized']      = df['Balance'] / max_balance if 'Balance' in df.columns else 0
        feat['has_complaint']          = 0
        feat['satisfaction_score']     = df['CreditScore'] / max_credit if 'CreditScore' in df.columns else 0.5
        feat['is_active']              = df['IsActiveMember'] if 'IsActiveMember' in df.columns else 0.5
        feat['num_products_services']  = df['NumOfProducts'] / 4.0 if 'NumOfProducts' in df.columns else 0
        feat['is_senior_or_high_risk'] = (df['Age'] > 55).astype(int) if 'Age' in df.columns else 0
        feat['has_support']            = df['HasCrCard'] if 'HasCrCard' in df.columns else 0
        feat['contract_stability']     = df['Tenure'] / max_tenure if 'Tenure' in df.columns else 0
        feat['payment_auto']           = 0.5

        feat['engagement_score']       = feat['num_products_services']
        feat['coupon_dependency']      = 0
        feat['cashback_engagement']    = feat['charge_normalized']
        feat['recency_score']          = feat['is_active']
        feat['convenience_score']      = 0.5
        feat['dormant_loyalty_risk']   = feat['tenure_normalized'] * (1 - feat['is_active'])
        feat['lockin_risk']            = 0
        feat['missed_appt_rate']       = 0
        feat['composite_satisfaction'] = feat['satisfaction_score']
        feat['billing_friction']       = 0
        feat['care_accessibility']     = 0.5
        feat['referral_engagement']    = 0

    elif sector == 'healthcare':
        _has_tenure  = any(c in df.columns for c in ('Tenure_Months', 'tenuremonths'))
        _has_visits  = any(c in df.columns for c in ('Visits_Last_Year', 'visitslastyear', 'Visits Last Year'))
        _has_premium = any(c in df.columns for c in ('MonthlyPremium', 'monthlypremium'))
        _has_freq    = any(c in df.columns for c in ('FrequencyOfVisits', 'frequencyofvisits'))

        if _has_tenure or _has_visits:
            c_tenure  = _hcol(df, 'Tenure_Months', 'tenuremonths')
            c_cost    = _hcol(df, 'Avg_Out_Of_Pocket_Cost', 'avgoutofpocketcost', 'Avg Out Of Pocket Cost')
            c_sat     = _hcol(df, 'Overall_Satisfaction', 'overallsatisfaction')
            c_wait    = _hcol(df, 'Wait_Time_Satisfaction', 'waittimesatisfaction')
            c_staff   = _hcol(df, 'Staff_Satisfaction', 'staffsatisfaction')
            c_rating  = _hcol(df, 'Provider_Rating', 'providerrating')
            c_visits  = _hcol(df, 'Visits_Last_Year', 'visitslastyear', 'Visits Last Year')
            c_missed  = _hcol(df, 'Missed_Appointments', 'missedappointments')
            c_lastv   = _hcol(df, 'Days_Since_Last_Visit', 'daysincelastvisit')
            c_dist    = _hcol(df, 'Distance_To_Facility_Miles', 'distancetofacilitymiles')
            c_billing = _hcol(df, 'Billing_Issues', 'billingissues', 'Billing Issues')
            c_portal  = _hcol(df, 'Portal_Usage', 'portalusage')
            c_refs    = _hcol(df, 'Referrals_Made', 'referralsmade')
            c_age     = _hcol(df, 'Age', 'age')

            max_tenure  = _norm_max(df, c_tenure,  sector, norm_stats) if c_tenure  else 1
            max_cost    = _norm_max(df, c_cost,    sector, norm_stats) if c_cost    else 1
            max_sat     = _norm_max(df, c_sat,     sector, norm_stats) if c_sat     else 1
            max_wait    = _norm_max(df, c_wait,    sector, norm_stats) if c_wait    else 1
            max_staff   = _norm_max(df, c_staff,   sector, norm_stats) if c_staff   else 1
            max_rating  = _norm_max(df, c_rating,  sector, norm_stats) if c_rating  else 1
            max_visits  = _norm_max(df, c_visits,  sector, norm_stats) if c_visits  else 1
            max_lastv   = _norm_max(df, c_lastv,   sector, norm_stats) if c_lastv   else 1
            max_dist    = _norm_max(df, c_dist,    sector, norm_stats) if c_dist    else 1
            max_billing = _norm_max(df, c_billing, sector, norm_stats) if c_billing else 1
            max_refs    = _norm_max(df, c_refs,    sector, norm_stats) if c_refs    else 1

            feat['tenure_normalized']      = df[c_tenure]  / max_tenure if c_tenure  else 0.5
            feat['charge_normalized']      = df[c_cost]    / max_cost   if c_cost    else 0
            feat['has_complaint']          = (df[c_billing] > 0).astype(int) if c_billing else 0
            feat['satisfaction_score']     = df[c_sat]     / max_sat    if c_sat     else 0.5
            feat['is_active']              = (df[c_lastv] <= 90).astype(int) if c_lastv else 0.5
            feat['num_products_services']  = df[c_visits]  / max_visits if c_visits  else 0.5
            feat['is_senior_or_high_risk'] = (df[c_age] > 65).astype(int) if c_age  else 0
            feat['has_support']            = df[c_portal]  if c_portal  else 0
            feat['contract_stability']     = df[c_tenure]  / max_tenure if c_tenure  else 0.5
            feat['payment_auto']           = 0.5
            feat['engagement_score']       = feat['num_products_services']
            feat['coupon_dependency']      = 0
            feat['cashback_engagement']    = 0
            feat['recency_score']          = 1 - (df[c_lastv] / max_lastv) if c_lastv else 0.5
            feat['convenience_score']      = 1 - (df[c_dist]  / max_dist)  if c_dist  else 0.5
            feat['dormant_loyalty_risk']   = feat['tenure_normalized'] * (1 - feat['is_active'])
            feat['lockin_risk']            = 0

            # New healthcare-specific features
            if c_missed and c_visits:
                total = df[c_visits].replace(0, np.nan)
                feat['missed_appt_rate'] = (df[c_missed] / total).clip(0, 1).fillna(0)
            elif c_missed:
                feat['missed_appt_rate'] = (df[c_missed] / max_visits).clip(0, 1)
            else:
                feat['missed_appt_rate'] = pd.Series(0.0, index=df.index)

            sat_scores = []
            if c_sat:    sat_scores.append(df[c_sat]    / max_sat)
            if c_wait:   sat_scores.append(df[c_wait]   / max_wait)
            if c_staff:  sat_scores.append(df[c_staff]  / max_staff)
            if c_rating: sat_scores.append(df[c_rating] / max_rating)
            feat['composite_satisfaction'] = (
                pd.concat(sat_scores, axis=1).mean(axis=1) if sat_scores
                else feat['satisfaction_score']
            )

            if c_billing and c_visits:
                total = df[c_visits].replace(0, np.nan)
                feat['billing_friction'] = (df[c_billing] / total).clip(0, 1).fillna(0)
            elif c_billing:
                feat['billing_friction'] = (df[c_billing] / max_billing).clip(0, 1)
            else:
                feat['billing_friction'] = pd.Series(0.0, index=df.index)

            dist_norm   = (df[c_dist] / max_dist).clip(0, 1) if c_dist   else pd.Series(0.5, index=df.index)
            portal_norm = df[c_portal].clip(0, 1)             if c_portal else pd.Series(0.0, index=df.index)
            feat['care_accessibility']  = ((1 - dist_norm) + portal_norm).clip(0, 1)
            feat['referral_engagement'] = (df[c_refs] / max_refs).clip(0, 1) if c_refs else 0

        elif _has_premium or _has_freq:
            c_premium = _hcol(df, 'MonthlyPremium', 'monthlypremium')
            c_freq    = _hcol(df, 'FrequencyOfVisits', 'frequencyofvisits')
            c_claims  = _hcol(df, 'ClaimHistoryCount', 'claimhistorycount')
            c_calls   = _hcol(df, 'CustomerSupportCalls', 'customersupportcalls')
            c_age     = _hcol(df, 'Age', 'age')

            max_premium = _norm_max(df, c_premium, sector, norm_stats) if c_premium else 1
            max_freq    = _norm_max(df, c_freq,    sector, norm_stats) if c_freq    else 1
            max_claims  = _norm_max(df, c_claims,  sector, norm_stats) if c_claims  else 1
            max_calls   = _norm_max(df, c_calls,   sector, norm_stats) if c_calls   else 1

            feat['tenure_normalized']      = 0.5
            feat['charge_normalized']      = df[c_premium] / max_premium if c_premium else 0
            feat['has_complaint']          = (df[c_calls] > 2).astype(int) if c_calls else 0
            feat['satisfaction_score']     = 0.5
            feat['is_active']              = (df[c_freq] > 0).astype(int) if c_freq else 0.5
            feat['num_products_services']  = df[c_freq] / max_freq if c_freq else 0.5
            feat['is_senior_or_high_risk'] = (df[c_age] > 65).astype(int) if c_age  else 0
            feat['has_support']            = (df[c_calls] > 0).astype(int) if c_calls else 0
            feat['contract_stability']     = 0.5
            feat['payment_auto']           = 0.5
            feat['engagement_score']       = feat['num_products_services']
            feat['coupon_dependency']      = 0
            feat['cashback_engagement']    = 0
            feat['recency_score']          = 0.5
            feat['convenience_score']      = 1 - (df[c_claims] / max_claims) if c_claims else 0.5
            feat['dormant_loyalty_risk']   = 0.5
            feat['lockin_risk']            = 0
            feat['missed_appt_rate']       = 0
            feat['composite_satisfaction'] = feat['satisfaction_score']
            feat['billing_friction']       = (df[c_calls] / max_calls).clip(0, 1) if c_calls else 0
            feat['care_accessibility']     = 0.5
            feat['referral_engagement']    = 0
        else:
            for col in UNIVERSAL_FEATURES:
                feat[col] = 0.5

    # Encode target
    # fix: previously copied the raw target column verbatim
    # (feat['Churn'] = df[target_col_actual].values), so whatever raw
    # representation each sector's source CSV happened to use (e.g.
    # "Yes"/"No" strings for one sector, already-int 0/1 for another)
    # flowed straight into the per-sector feature table. Once
    # train_universal_model() concatenated all sectors' tables, the
    # combined Churn column contained mixed Python types, which crashed
    # train_test_split(..., stratify=y) deep inside NumPy's np.unique().
    # normalize_target() is the single shared source of truth for label
    # normalization (also used by SectorPipeline and
    # train_universal_model) — every extracted feature table now always
    # contains a canonical Churn ∈ {0, 1}, regardless of how the source
    # sector originally encoded it.
    target_col_actual = SECTOR_CONFIG.get(sector, {}).get('target_col', target_col)
    if target_col_actual in df.columns:
        feat['Churn'] = normalize_target(df[target_col_actual]).values
    feat['Sector'] = sector

    return feat


def transform_features_by_sector(df: pd.DataFrame, sector: str) -> pd.DataFrame:
    """
    Convert an inference DataFrame to the universal model feature matrix.
    Used exclusively by predict_universal() — mirrors extract_universal_features()
    but operates on already-read inference data (no target required).
    """
    config     = SECTOR_CONFIG[sector]
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

    df_working = sanitize_numerical_columns(df_working)

    target_col = config['target_col']
    if target_col not in df_working.columns:
        df_working[target_col] = 0

    norm_stats = None
    if UNIVERSAL_NORM_STATS_PATH.exists():
        norm_stats = joblib.load(UNIVERSAL_NORM_STATS_PATH)

    features = extract_universal_features(df_working, sector, target_col, norm_stats=norm_stats)

    le_path = str(UNIVERSAL_MODEL_PATH).replace('.pkl', '_le_sector.pkl')
    if Path(le_path).exists():
        le_sector = joblib.load(le_path)
        if sector in set(le_sector.classes_):
            features['Sector_Encoded'] = le_sector.transform([sector])[0]
        else:
            features['Sector_Encoded'] = 0

    X_processed = features.drop(columns=['Churn', 'Sector'], errors='ignore')

    if UNIVERSAL_FEATURES_PATH.exists():
        expected_features = pd.read_csv(UNIVERSAL_FEATURES_PATH).iloc[:, 0].tolist()
        for col in expected_features:
            if col not in X_processed.columns:
                X_processed[col] = 0
        X_processed = X_processed[expected_features]

    return X_processed


from pathlib import Path  # noqa: E402 — needed by transform_features_by_sector
