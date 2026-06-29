from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, classification_report,
    f1_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import LabelEncoder, StandardScaler
from imblearn.over_sampling import SMOTE

try:
    from xgboost import XGBClassifier
except ImportError as exc:
    raise ImportError("xgboost is required.") from exc

# SHAP is optional: explanation logging (Correction/Suggestion — per-row
# SHAP logs) is skipped with a warning if shap isn't installed, rather
# than making it a hard dependency for the whole pipeline.
try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False

warnings.filterwarnings('ignore')


# ══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════

SECTOR_CONFIG = {
    'telecom': {
        'data_path'    : 'data/telecom/WA_Fn-UseC_-Telco-Customer-Churn.csv',
        'target_col'   : 'Churn',
        'drop_cols'    : ['customerID'],
        'binary_map'   : {'Yes': 1, 'No': 0,
                          'No phone service': 0,
                          'No internet service': 0,
                          'Male': 1, 'Female': 0},
        'ohe_cols'     : ['Contract', 'InternetService', 'PaymentMethod'],
        'scale_cols'   : ['tenure', 'MonthlyCharges', 'TotalCharges'],
        'model_path'   : 'outputs/universal/sector_models/telecom_best.pkl',
        'scaler_path'  : 'outputs/universal/sector_scalers/telecom_scaler.pkl',
        'features_path': 'outputs/universal/sector_features/telecom_features.csv',
    },
    'ecommerce': {
        'data_path'    : 'data/ecommerce/ECommerce.csv',
        'target_col'   : 'Churn',
        'drop_cols'    : ['CustomerID'],
        'binary_map'   : {},
        'ohe_cols'     : [],
        'scale_cols'   : ['Tenure', 'CityTier', 'WarehouseToHome',
                          'HourSpendOnApp', 'NumberOfDeviceRegistered',
                          'SatisfactionScore', 'NumberOfAddress',
                          'Complain', 'OrderAmountHikeFromlastYear',
                          'CouponUsed', 'OrderCount',
                          'DaySinceLastOrder', 'CashbackAmount'],
        'model_path'   : 'outputs/universal/sector_models/ecommerce_best.pkl',
        'scaler_path'  : 'outputs/universal/sector_scalers/ecommerce_scaler.pkl',
        'features_path': 'outputs/universal/sector_features/ecommerce_features.csv',
    },
    'banking': {
        'data_path'    : 'data/banking/Churn_Modelling.csv',
        'target_col'   : 'Exited',
        'drop_cols'    : ['RowNumber', 'CustomerId', 'Surname'],
        # NOTE (fix): Geography/Gender are now handled by proper, PERSISTED
        # LabelEncoders (see _encode) instead of a hard-coded binary_map.
        # The previous static map {'France':0,'Germany':1,'Spain':2} was
        # never saved, so a fresh process or a CSV with categories in a
        # different order/case could silently re-encode differently between
        # training and inference. Encoders are now fit once during fit()
        # and joblib-dumped alongside the model, then reloaded in load().
        'binary_map'   : {'Male': 1, 'Female': 0},
        'label_encode_cols': ['Geography'],
        'ohe_cols'     : [],
        'scale_cols'   : ['CreditScore', 'Age', 'Tenure',
                          'Balance', 'NumOfProducts',
                          'EstimatedSalary'],
        'model_path'   : 'outputs/universal/sector_models/banking_best.pkl',
        'scaler_path'  : 'outputs/universal/sector_scalers/banking_scaler.pkl',
        'features_path': 'outputs/universal/sector_features/banking_features.csv',
    },
    'healthcare': {
        # NOTE (fix v2): updated to match the ACTUAL dataset header
        # supplied by the user:
        # PatientID, Age, Gender, State, Tenure_Months, Specialty,
        # Insurance_Type, Visits_Last_Year, Missed_Appointments,
        # Days_Since_Last_Visit, Overall_Satisfaction,
        # Wait_Time_Satisfaction, Staff_Satisfaction, Provider_Rating,
        # Avg_Out_Of_Pocket_Cost, Billing_Issues, Portal_Usage,
        # Referrals_Made, Distance_To_Facility_Miles, Churned
        'data_path'    : 'data/healthcare/health_churn.csv',
        'target_col'   : 'Churned',
        'drop_cols'    : ['PatientID', 'Last_Interaction_Date'],
        'binary_map'   : {'Yes': 1, 'No': 0, 'Male': 1, 'Female': 0},
        'ohe_cols'     : ['State', 'Specialty', 'Insurance_Type'],
        'scale_cols'   : ['Age', 'Tenure_Months', 'Visits_Last_Year',
                          'Missed_Appointments', 'Days_Since_Last_Visit',
                          'Overall_Satisfaction', 'Wait_Time_Satisfaction',
                          'Staff_Satisfaction', 'Provider_Rating',
                          'Avg_Out_Of_Pocket_Cost', 'Billing_Issues',
                          'Portal_Usage', 'Referrals_Made',
                          'Distance_To_Facility_Miles'],
        'model_path'   : 'outputs/universal/sector_models/healthcare_best.pkl',
        'scaler_path'  : 'outputs/universal/sector_scalers/healthcare_scaler.pkl',
        'features_path': 'outputs/universal/sector_features/healthcare_features.csv',
    },
}

# ── Feature importance weights for coverage scoring ──────────────
# Each value reflects how much predictive signal the feature carries
# in its sector model, based on domain knowledge and SHAP analysis.
# Features that are absent hurt the coverage score proportionally more
# than low-weight features. Quality (non-null, non-constant) is also
# required for a feature to count toward the score.
#
# Scale: 5 = critical  4 = high  3 = medium  2 = low  1 = minor
SECTOR_FEATURE_WEIGHTS: dict[str, dict[str, int]] = {
    'telecom': {
        'Contract'          : 5,   # strongest single churn predictor in telecom
        'tenure'            : 5,
        'MonthlyCharges'    : 5,
        'TotalCharges'      : 4,
        'InternetService'   : 4,
        'TechSupport'       : 3,
        'OnlineSecurity'    : 3,
        'PaymentMethod'     : 3,
        'MultipleLines'     : 2,
        'OnlineBackup'      : 2,
        'DeviceProtection'  : 2,
        'StreamingTV'       : 2,
        'StreamingMovies'   : 2,
        'PaperlessBilling'  : 1,
        'SeniorCitizen'     : 1,
        'Partner'           : 1,
        'Dependents'        : 1,
        'PhoneService'      : 1,
        'gender'            : 1,
    },
    'banking': {
        'NumOfProducts'     : 5,
        'Age'               : 5,
        'Balance'           : 5,
        'IsActiveMember'    : 5,
        'Geography'         : 4,
        'CreditScore'       : 4,
        'Tenure'            : 4,
        'EstimatedSalary'   : 3,
        'HasCrCard'         : 2,
        'Gender'            : 1,
    },
    'ecommerce': {
        'Tenure'                      : 5,
        'Complain'                    : 5,
        'DaySinceLastOrder'           : 5,
        'SatisfactionScore'           : 4,
        'OrderCount'                  : 4,
        'CashbackAmount'              : 4,
        'OrderAmountHikeFromlastYear' : 3,
        'CouponUsed'                  : 3,
        'NumberOfDeviceRegistered'    : 3,
        'HourSpendOnApp'              : 3,
        'WarehouseToHome'             : 2,
        'NumberOfAddress'             : 2,
        'CityTier'                    : 1,
        'PreferredLoginDevice'        : 1,
        'PreferredPaymentMode'        : 1,
        'PreferedOrderCat'            : 1,
        'MaritalStatus'               : 1,
        'Gender'                      : 1,
    },
    'healthcare': {
        'Days_Since_Last_Visit'     : 5,
        'Billing_Issues'            : 5,
        'Overall_Satisfaction'      : 5,
        'Visits_Last_Year'          : 5,
        'Avg_Out_Of_Pocket_Cost'    : 4,
        'Age'                       : 4,
        'Missed_Appointments'       : 4,
        'Wait_Time_Satisfaction'    : 3,
        'Staff_Satisfaction'        : 3,
        'Provider_Rating'           : 3,
        'Distance_To_Facility_Miles': 3,
        'Tenure_Months'             : 3,
        'Portal_Usage'              : 2,
        'Referrals_Made'            : 2,
        'Insurance_Type'            : 2,
        'Specialty'                 : 2,
        'Gender'                    : 1,
        'State'                     : 1,
    },
}

UNIVERSAL_MODEL_PATH   = Path('outputs/universal/universal_xgb_model.pkl')
UNIVERSAL_SCALER_PATH  = Path('outputs/universal/universal_scaler.pkl')
UNIVERSAL_FEATURES_PATH= Path('outputs/universal/universal_features.csv')
UNIVERSAL_LABEL_PATH   = Path('outputs/universal/universal_label_encoders.pkl')

# ══════════════════════════════════════════════════════════════════
# GLOBAL CONCEPT TRANSLATION MAP (SCHEMA AGNOSTICISM — STEP 1)
# Maps known column name variants from any industry into the
# standard internal tokens the sector models were trained on.
# This is the single place to register a new alias — the predict()
# method and predict_universal() both run all incoming columns
# through this map before any encoding or scaling happens.
# ══════════════════════════════════════════════════════════════════
GLOBAL_CONCEPT_MAP = {
    # ── Identity / ID columns ─────────────────────────────────────
    'customerid'          : 'customerid',
    'patientid'           : 'customerid',
    'customer id'         : 'customerid',

    # ── Target column variants ────────────────────────────────────
    'exited'              : 'churn',
    'churned'             : 'churn',

    # ── Banking core columns ──────────────────────────────────────
    'creditscore'         : 'creditscore',
    'numofproducts'       : 'numofproducts',
    'isactivemember'      : 'isactivemember',
    'frequencyofvisits'   : 'isactivemember',   # healthcare proxy
    'estimatedsalary'     : 'estimatedsalary',

    # ── E-commerce / Telecom shared concepts ─────────────────────
    'warehousetohome'     : 'warehousetohome',
    'hourspendonapp'      : 'hourspendonapp',
    'numberofdeviceregistered': 'numberofdeviceregistered',
    'satisfactionscore'   : 'satisfactionscore',
    'daysincelastorder'   : 'daysincelastorder',
    'days_since_last_visit': 'daysincelastorder',  # healthcare analog
    'complain'            : 'complain',
    'customersupportcalls': 'complain',            # healthcare/banking analog
    'billing_issues'      : 'complain',            # healthcare analog

    # ── Financial charge column variants ─────────────────────────
    'cashbackamount'      : 'cashbackamount',
    'monthlycharges'      : 'cashbackamount',      # telecom analog
    'monthlypremium'      : 'cashbackamount',      # healthcare analog
    'avg_out_of_pocket_cost': 'cashbackamount',    # healthcare analog

    # ── Tenure / contract columns ─────────────────────────────────
    'tenure'              : 'tenure',
    'tenure_months'       : 'tenure',
    'contract'            : 'contract',
    'policytype'          : 'contract',            # healthcare analog
}

# ══════════════════════════════════════════════════════════════════
# SECTOR-AWARE DECISION THRESHOLDS
# Different sectors have different costs for false negatives vs
# false positives. A single 0.5 threshold is suboptimal for all.
# These are calibrated from adversarial test findings:
#   Ecommerce: 0.35 — catches silent churners (ADV_ECO_02 case)
#              who sit just under 0.5 due to tenure weight bias
#   Healthcare: 0.65 — prevents false alarms on high-utilization
#               chronic patients (ADV_HCA_02 case) who look risky
#               due to training distribution skew
#   Telecom/Banking: 0.50 — standard threshold, well calibrated
# ══════════════════════════════════════════════════════════════════
SECTOR_THRESHOLDS = {
    'telecom'    : 0.50,
    'ecommerce'  : 0.35,   # lower — catches silent churners
    'banking'    : 0.50,
    'healthcare' : 0.65,   # higher — avoids chronic-patient false alarms
}


def apply_sector_threshold(
    probas: np.ndarray, sector: str
) -> np.ndarray:
    """
    Apply the sector-specific decision threshold to raw probabilities
    and return a binary prediction array (0 or 1).
    Falls back to 0.5 for unknown sectors.
    """
    threshold = SECTOR_THRESHOLDS.get(sector, 0.50)
    return (probas >= threshold).astype(int)


# fix: persisted per-sector normalization maxima, computed once from
# training data, so single-row inference doesn't normalize against
# itself (see _norm_max).
UNIVERSAL_NORM_STATS_PATH = Path('outputs/universal/universal_norm_stats.pkl')


# ══════════════════════════════════════════════════════════════════
# SECTOR AUTO-DETECTION (fix: removes the --sector requirement)
# ══════════════════════════════════════════════════════════════════

# Columns that are distinctive enough to identify a sector on sight.
# Each sector needs at least MIN_SIGNATURE_HITS of its signature columns
# present (case-insensitive, whitespace-insensitive match) to be selected.
# Each sector maps to a LIST of possible signatures (schema variants).
# A sector matches if its input columns hit MIN_SIGNATURE_HITS against
# ANY one of its variants. This is what makes detection genuinely
# schema-agnostic instead of locked to one specific dataset's headers —
# e.g. Healthcare now recognizes both the "PatientID/Specialty/..." and
# the "MedicalCondition/PolicyType/FrequencyOfVisits/..." schemas.
SECTOR_SIGNATURES = {
    'telecom': [
        {'monthlycharges', 'totalcharges', 'contract', 'internetservice',
         'phoneservice', 'multiplelines', 'streamingtv'},
    ],
    'ecommerce': [
        {'cashbackamount', 'daysincelastorder', 'couponused', 'ordercount',
         'warehousetohome', 'hourspendonapp', 'preferredpaymentmode'},
    ],
    'banking': [
        {'rownumber', 'surname', 'creditscore', 'geography',
         'numofproducts', 'hascrcard', 'isactivemember',
         'estimatedsalary', 'exited'},
    ],
    'healthcare': [
        # Variant 1: PatientID-style schema
        {'patientid', 'specialty', 'insurancetype', 'visitslastyear',
         'missedappointments', 'overallsatisfaction',
         'waittimesatisfaction', 'staffsatisfaction', 'providerrating',
         'avgoutofpocketcost', 'billingissues', 'portalusage',
         'referralsmade', 'distancetofacilitymiles', 'churned'},
        # Variant 2: MedicalCondition-style schema
        {'medicalcondition', 'policytype', 'monthlypremium',
         'frequencyofvisits', 'claimhistorycount', 'customersupportcalls'},
    ],
}
MIN_SIGNATURE_HITS = 2


def detect_sector(df: pd.DataFrame) -> str:
    """
    Inspect a DataFrame's column names and return the best-matching
    sector key from SECTOR_CONFIG. Each sector may have multiple known
    schema variants (SECTOR_SIGNATURES values are lists of signature
    sets); a sector's score is the BEST score across its variants, so
    any one matching variant is enough to identify the sector. Raises
    ValueError if no sector scores at least MIN_SIGNATURE_HITS matches,
    or if there's an ambiguous tie at the top score.
    """
    normalized_cols = {c.strip().lower().replace(' ', '').replace('_', '')
                        for c in df.columns}

    scores = {}
    for sector, variants in SECTOR_SIGNATURES.items():
        best_variant_score = 0
        for signature in variants:
            sig_normalized = {s.replace(' ', '').replace('_', '') for s in signature}
            best_variant_score = max(
                best_variant_score, len(normalized_cols & sig_normalized)
            )
        scores[sector] = best_variant_score

    best_sector = max(scores, key=scores.get)
    best_score  = scores[best_sector]

    if best_score < MIN_SIGNATURE_HITS:
        raise ValueError(
            "Could not auto-detect sector from input columns "
            f"(best match: '{best_sector}' with only {best_score} "
            f"signature columns found). Pass --sector explicitly. "
            f"Columns seen: {list(df.columns)}"
        )

    # Check for an ambiguous tie
    top_sectors = [s for s, sc in scores.items() if sc == best_score]
    if len(top_sectors) > 1:
        raise ValueError(
            f"Ambiguous sector match between {top_sectors} "
            f"(each scored {best_score} signature hits). "
            "Pass --sector explicitly to disambiguate."
        )

    return best_sector


# ══════════════════════════════════════════════════════════════════
# PHASE A — SECTOR-SPECIFIC PIPELINE
# ══════════════════════════════════════════════════════════════════

class SectorPipeline:
    """
    Auto-preprocessing pipeline for a specific sector.
    Handles any CSV with that sector's schema automatically.
    """

    def __init__(self, sector: str, tune_metric: str | None = None):
        """
        tune_metric: if set to 'f1' or 'recall', fit() runs a GridSearchCV
        hyperparameter search optimizing for that metric instead of using
        fixed defaults. Churn datasets are imbalanced — a model can hit
        85% accuracy by predicting "no churn" for everyone — so recall/F1
        are the metrics that actually matter for catching churners.
        """
        if sector not in SECTOR_CONFIG:
            raise ValueError(
                f"Unknown sector '{sector}'. "
                f"Choose from: {list(SECTOR_CONFIG.keys())}"
            )
        if tune_metric is not None and tune_metric not in ('f1', 'recall'):
            raise ValueError("tune_metric must be 'f1', 'recall', or None")
        self.sector = sector
        self.tune_metric = tune_metric
        self.config = SECTOR_CONFIG[sector]
        self.scaler = StandardScaler()
        self.label_encoders: dict[str, LabelEncoder] = {}
        self.feature_names: list[str] = []
        self.model = None

    def _load_data(self) -> pd.DataFrame:
        path = self.config['data_path']
        if not Path(path).exists():
            raise FileNotFoundError(f"Data not found: {path}")
        return pd.read_csv(path)

    def _clean(self, df: pd.DataFrame) -> pd.DataFrame:
        # Drop irrelevant columns
        drop = [c for c in self.config['drop_cols'] if c in df.columns]
        df.drop(columns=drop, inplace=True, errors='ignore')

        # Fix TotalCharges dtype (Telecom specific)
        if 'TotalCharges' in df.columns:
            df['TotalCharges'] = pd.to_numeric(
                df['TotalCharges'], errors='coerce'
            )

        # Fill nulls
        for col in df.select_dtypes(include='number').columns:
            df[col] = df[col].fillna(df[col].median())
        for col in df.select_dtypes(include=['object', 'string']).columns:
            df[col] = df[col].fillna(df[col].mode()[0])

        df = self._add_interaction_features(df)

        return df

    def _add_interaction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Correction B (audit): cross-feature interaction terms so the
        model can see combinations a tree built on independent columns
        tends to miss — e.g. "many unused products" or "complaint offset
        by a cash incentive" rather than evaluating each signal alone.
        New columns are auto-added to scale_cols so they get scaled like
        any other numeric feature; this only runs if the source columns
        for that sector are actually present.
        """
        if self.sector == 'banking' and {'NumOfProducts', 'IsActiveMember'}.issubset(df.columns):
            # Product_Strain: customers holding several unused products
            # they aren't actively engaging with — a fee-frustration signal
            # that NumOfProducts and IsActiveMember don't capture alone.
            df['Product_Strain'] = df['NumOfProducts'] * (1 - df['IsActiveMember'])
            if 'Product_Strain' not in self.config['scale_cols']:
                self.config['scale_cols'].append('Product_Strain')

        if self.sector == 'ecommerce' and {'CashbackAmount', 'Complain'}.issubset(df.columns):
            # Financial_Bribe_Ratio: lets a large cashback incentive
            # offset a recorded complaint instead of the model treating
            # "has_complaint" as an independent, unconditional risk flag.
            df['Financial_Bribe_Ratio'] = df['CashbackAmount'] / (df['Complain'] + 1)
            if 'Financial_Bribe_Ratio' not in self.config['scale_cols']:
                self.config['scale_cols'].append('Financial_Bribe_Ratio')

        if self.sector == 'ecommerce' and {'Tenure', 'DaySinceLastOrder'}.issubset(df.columns):
            # Engagement_Decay (stress-test fix): a long-tenure customer
            # who has gone quiet recently is exactly the case a tree
            # built on independent columns misses — Tenure alone creates
            # a dominant "safe" split early, and the model never revisits
            # that classification even when DaySinceLastOrder spikes.
            # This multiplies the two directly so "high tenure AND long
            # silence" produces one strong combined risk signal instead
            # of two weak independent ones the tree can route around.
            max_tenure = df['Tenure'].max() if df['Tenure'].max() else 1
            max_recency = df['DaySinceLastOrder'].max() if df['DaySinceLastOrder'].max() else 1
            tenure_norm = df['Tenure'] / max_tenure
            recency_norm = df['DaySinceLastOrder'] / max_recency
            df['Engagement_Decay'] = tenure_norm * recency_norm
            if 'Engagement_Decay' not in self.config['scale_cols']:
                self.config['scale_cols'].append('Engagement_Decay')

        if self.sector == 'telecom':
            # Onboarding_Risk (stress-test fix): a brand-new customer who
            # is already calling support repeatedly is a failed-onboarding
            # signal that a long Contract term can otherwise mask — the
            # model saw "Two year" and drove risk near zero, ignoring
            # early friction entirely. Telecom's standard schema only has
            # a TechSupport Yes/No flag, but tolerate a numeric support-
            # contact count column if one is present (some input files,
            # like this stress test, include actual call counts).
            support_count_cols = ['CustomerServiceCalls', 'SupportCalls',
                                   'TechSupportCalls', 'NumSupportCalls']
            support_col = next((c for c in support_count_cols if c in df.columns), None)
            if 'tenure' in df.columns and (support_col or 'TechSupport' in df.columns):
                is_new = (df['tenure'] <= 3).astype(int)
                if support_col:
                    max_calls = df[support_col].max() if df[support_col].max() else 1
                    support_signal = df[support_col] / max_calls
                else:
                    support_signal = (df['TechSupport'] == 'Yes').astype(int)
                df['Onboarding_Risk'] = is_new * support_signal
                if 'Onboarding_Risk' not in self.config['scale_cols']:
                    self.config['scale_cols'].append('Onboarding_Risk')

        return df

    def _encode(self, df: pd.DataFrame, fit: bool = True) -> pd.DataFrame:
        # Columns explicitly flagged for persisted LabelEncoder treatment
        # (fix: previously banking's Geography went through a static,
        # never-saved binary_map; now any column listed in
        # 'label_encode_cols' always gets a real, persisted LabelEncoder
        # with explicit handling of unseen categories at inference time).
        forced_label_cols = set(self.config.get('label_encode_cols', []))

        for col in df.select_dtypes(include=['object', 'string']).columns:
            if col == self.config.get('target_col'):
                continue

            if col in forced_label_cols:
                if fit:
                    le = LabelEncoder()
                    df[col] = le.fit_transform(df[col].astype(str))
                    self.label_encoders[col] = le
                else:
                    if col in self.label_encoders:
                        le = self.label_encoders[col]
                        known = set(le.classes_)
                        df[col] = df[col].astype(str).apply(
                            lambda x: x if x in known else le.classes_[0]
                        )
                        df[col] = le.transform(df[col])
                    else:
                        df[col] = 0
                continue

            mapped = df[col].map(self.config['binary_map'])
            if mapped.notna().all():
                df[col] = mapped
            elif col in self.config['ohe_cols']:
                pass  # handled below
            else:
                # Label encode unknown categoricals
                if fit:
                    le = LabelEncoder()
                    df[col] = le.fit_transform(df[col].astype(str))
                    self.label_encoders[col] = le
                else:
                    if col in self.label_encoders:
                        le = self.label_encoders[col]
                        known = set(le.classes_)
                        df[col] = df[col].astype(str).apply(
                            lambda x: x if x in known else le.classes_[0]
                        )
                        df[col] = le.transform(df[col])
                    else:
                        df[col] = 0

        # One-hot encode multi-class columns
        if self.config['ohe_cols']:
            ohe_present = [
                c for c in self.config['ohe_cols']
                if c in df.columns
            ]
            df = pd.get_dummies(df, columns=ohe_present, drop_first=True)

        return df

    def _encode_target(self, series: pd.Series) -> pd.Series:
        # fix: gate on numeric dtype instead of dtype == 'object'.
        # Newer pandas can label text columns as the 'string' extension
        # dtype rather than 'object', which made the old `if dtype ==
        # 'object'` check silently skip the Yes/No mapping entirely and
        # fall through to astype(int) on raw 'Yes'/'No' text -> crash.
        if pd.api.types.is_numeric_dtype(series):
            return series.astype(int)

        series = series.astype(str).str.strip()
        series = series.map({
            'Yes': 1,
            'No': 0,
            'yes': 1,
            'no': 0,
            'YES': 1,
            'NO': 0
        })
        if series.isna().any():
            unmapped = series.isna().sum()
            raise ValueError(
                f"_encode_target: {unmapped} target value(s) could not be "
                "mapped to 0/1. Check the target column for unexpected "
                "category labels beyond Yes/No."
            )
        return series.astype(int)

    def fit(self) -> 'SectorPipeline':
        """Train the best model for this sector."""
        print(f"\n{'='*50}")
        print(f"  Training pipeline — {self.sector.upper()}")
        print(f"{'='*50}")

        df = self._load_data()
        df = self._clean(df)

        target_col = self.config['target_col']
        y = self._encode_target(df[target_col])

        print("\nTarget classes:")
        print(pd.Series(y).value_counts())
        print("Target dtype:", y.dtype)

        df.drop(columns=[target_col], inplace=True)
        df = self._encode(df, fit=True)

        # Scale numerical columns
        scale_cols = [
            c for c in self.config['scale_cols']
            if c in df.columns
        ]
        df[scale_cols] = self.scaler.fit_transform(df[scale_cols])

        self.feature_names = df.columns.tolist()

        # --- Diagnostics + safety net before SMOTE ---
        # We already fixed the root cause (df[col].fillna(..., inplace=True)
        # silently no-op'ing under pandas copy-on-write), but this guard
        # stays permanently: it makes the pipeline NaN/inf-proof regardless
        # of which preprocessing step a future schema change slips past.
        print("\nChecking dataframe before train/test split...")
        nan_cols = df.columns[df.isna().any()].tolist()
        print("Columns with NaNs:", nan_cols)
        if nan_cols:
            print(df[nan_cols].isna().sum())
        print("Total NaNs:", df.isna().sum().sum())

        df = df.replace([np.inf, -np.inf], np.nan)
        if df.isna().sum().sum() > 0:
            print("WARNING: NaNs still found after preprocessing. Filling remaining with 0.")
            df = df.fillna(0)

        X = df.values

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        print("NaNs in X_train:", np.isnan(X_train.astype(float)).sum())
        print("NaNs in y_train:", pd.Series(y_train).isna().sum())

        # Bug 7 fix: SMOTE interpolates between integer-encoded categorical
        # columns (e.g. Geography=0,1,2) and can produce fractional values
        # like 1.5 that corrupt decision boundaries. Identify the categorical
        # column indices (label-encoded or binary-mapped object cols) so
        # SMOTENC can treat them as categorical instead of continuous.
        cat_col_names = set(self.config.get('label_encode_cols', []))
        # Also treat binary-mapped columns as categorical
        for col in df.columns:
            if col in self.config.get('binary_map', {}):
                cat_col_names.add(col)
        cat_indices = [
            i for i, col in enumerate(df.columns)
            if col in cat_col_names
        ]
        if cat_indices:
            from imblearn.over_sampling import SMOTENC
            smote = SMOTENC(categorical_features=cat_indices, random_state=42)
        else:
            smote = SMOTE(random_state=42)
        X_train_sm, y_train_sm = smote.fit_resample(X_train, y_train)

        if self.tune_metric:
            # Strategic suggestion (audit): churn datasets are imbalanced,
            # so a model can score 85% accuracy by predicting "no churn"
            # for everyone. Optimize the search for recall/F1 instead of
            # the estimator's default scoring.
            print(f"\n  Tuning hyperparameters (scoring='{self.tune_metric}')...")
            # Healthcare note: if tuning for 'roc_auc', expand the grid to
            # cover params that directly affect probability ranking quality
            # (min_child_weight, gamma, subsample) in addition to the
            # standard depth/rate grid used by the other sectors.
            if self.sector == 'healthcare' or self.tune_metric == 'roc_auc':
                param_grid = {
                    'n_estimators'     : [200, 300, 400],
                    'max_depth'        : [3, 4, 5],
                    'learning_rate'    : [0.03, 0.05, 0.1],
                    'min_child_weight' : [3, 5, 7],
                    'gamma'            : [0, 0.1, 0.3],
                    'subsample'        : [0.7, 0.8],
                    'colsample_bytree' : [0.7, 0.8],
                }
            else:
                param_grid = {
                    'n_estimators': [100, 200, 300],
                    'max_depth': [3, 4, 6],
                    'learning_rate': [0.05, 0.1, 0.2],
                }
            # Compute scale_pos_weight from the SMOTE-resampled training set
            # so XGBoost's internal probability calibration reflects the real
            # imbalance ratio rather than the post-SMOTE 50/50 split.
            neg_count = (y_train == 0).sum()
            pos_count = (y_train == 1).sum()
            spw = neg_count / pos_count if pos_count > 0 else 1.0
            base_model = XGBClassifier(
                random_state=42, use_label_encoder=False,
                eval_metric='logloss', verbosity=0,
                scale_pos_weight=spw if self.sector == 'healthcare' else 1,
            )
            search = GridSearchCV(
                base_model, param_grid,
                scoring=self.tune_metric, cv=3,
                n_jobs=-1, verbose=0
            )
            search.fit(X_train_sm, y_train_sm)
            self.model = search.best_estimator_
            print(f"  Best params: {search.best_params_}")
            print(f"  Best CV {self.tune_metric}: {search.best_score_:.4f}")
        else:
            # Healthcare gets dedicated AUC-oriented defaults:
            # - lower max_depth (4→3) to reduce overfitting on a smaller dataset
            # - higher min_child_weight (1→5) to prevent splits on noisy small
            #   patient subgroups, which is the main cause of poor probability
            #   ranking (low ROC-AUC) even when recall looks acceptable
            # - gamma=0.1 requires a minimum loss reduction before splitting,
            #   further discouraging splits that only boost accuracy/recall
            # - scale_pos_weight calibrates probabilities against the real
            #   class ratio so the full [0,1] probability range is used
            #   rather than clustering near the base rate
            if self.sector == 'healthcare':
                neg_count = (y_train == 0).sum()
                pos_count = (y_train == 1).sum()
                spw = neg_count / pos_count if pos_count > 0 else 1.0
                self.model = XGBClassifier(
                    n_estimators=300, learning_rate=0.05,
                    max_depth=3, min_child_weight=5,
                    gamma=0.1, subsample=0.8,
                    colsample_bytree=0.8,
                    scale_pos_weight=spw,
                    random_state=42,
                    use_label_encoder=False,
                    eval_metric='auc', verbosity=0,
                )
            else:
                # Train XGBoost with fixed defaults for other sectors
                self.model = XGBClassifier(
                    n_estimators=200, learning_rate=0.1,
                    max_depth=4, random_state=42,
                    use_label_encoder=False,
                    eval_metric='logloss', verbosity=0,
                )
            self.model.fit(X_train_sm, y_train_sm)

        # Evaluate
        y_pred  = self.model.predict(X_test)
        y_proba = self.model.predict_proba(X_test)[:, 1]

        print(f"  Accuracy  : {accuracy_score(y_test, y_pred):.4f}")
        print(f"  Precision : {precision_score(y_test, y_pred):.4f}")
        print(f"  Recall    : {recall_score(y_test, y_pred):.4f}")
        print(f"  F1        : {f1_score(y_test, y_pred):.4f}")
        print(f"  ROC-AUC   : {roc_auc_score(y_test, y_proba):.4f}")

        # Save
        model_path   = Path(self.config['model_path'])
        scaler_path  = Path(self.config['scaler_path'])
        feature_path = Path(self.config['features_path'])

        model_path.parent.mkdir(parents=True, exist_ok=True)
        scaler_path.parent.mkdir(parents=True, exist_ok=True)
        feature_path.parent.mkdir(parents=True, exist_ok=True)

        joblib.dump(self.model,  model_path)
        joblib.dump(self.scaler, scaler_path)
        # fix: label_encoders dict (now reliably populated for forced
        # label_encode_cols too, e.g. banking's Geography) is always
        # persisted next to the features file so load() can restore it.
        joblib.dump(self.label_encoders, str(feature_path).replace('.csv', '_le.pkl'))
        pd.Series(self.feature_names).to_csv(feature_path, index=False)

        print(f"  Model saved  : {model_path}")
        print(f"  Encoders saved: {str(feature_path).replace('.csv', '_le.pkl')}")
        return self

    def load(self) -> 'SectorPipeline':
        """Load a previously trained sector pipeline."""
        self.model  = joblib.load(self.config['model_path'])
        self.scaler = joblib.load(self.config['scaler_path'])
        feat_path   = self.config['features_path']
        le_path     = feat_path.replace('.csv', '_le.pkl')
        self.feature_names = pd.read_csv(feat_path).iloc[:, 0].tolist()
        if Path(le_path).exists():
            self.label_encoders = joblib.load(le_path)
        else:
            # fix: previously a silent no-op; now warn loudly, since a
            # missing encoder file means any categorical column normally
            # routed through LabelEncoder (e.g. Geography) will fall back
            # to all-zeros at inference — a silent accuracy bug.
            print(
                f"  WARNING: no label-encoder file found at {le_path}. "
                "Categorical columns relying on LabelEncoder will be "
                "encoded as 0 at prediction time, which will degrade "
                "accuracy. Re-run fit() to regenerate it."
            )
        return self

    def predict(self, input_csv: str, explain: bool = False,
                explain_output: str | None = None) -> pd.DataFrame:
        """
        Predict churn for any CSV matching or mapping to this sector's schema.

        Routing:
          Green  (≥85% weighted coverage) → full sector-specific XGBoost
          Yellow (60–85%)                 → universal XGBoost fallback
          Red    (<60%)                   → hard stop, no prediction returned
        """
        df_raw = pd.read_csv(input_csv)
        df_raw = sanitize_numerical_columns(df_raw)
        df_raw = derive_temporal_features(df_raw)

        # ── Coverage scoring ──────────────────────────────────────
        coverage = compute_coverage_score(
            df_input=df_raw,
            sector=self.sector,
            mode='sector',
        )

        # ── Red band: refuse prediction ───────────────────────────
        if coverage['prediction_mode'] == 'Refused':
            critical = coverage['missing_critical']
            msg = (
                f"Prediction refused for sector '{self.sector}': weighted "
                f"coverage score is {coverage['coverage_score']*100:.1f}% "
                f"(threshold 60%). The following high-importance features are "
                f"missing or unusable: {critical}. "
                f"Enrich the input CSV and rerun."
            )
            raise ValueError(msg)

        # ── Yellow band: route to universal model ─────────────────
        if coverage['prediction_mode'] == 'Fallback':
            print(f"\n  Routing to universal model (coverage "
                  f"{coverage['coverage_score']*100:.1f}% < 85%)...")
            results = predict_universal(input_csv, force_sector=self.sector)
            results['Prediction_Model']  = 'XGBoost (Universal)'
            results['Prediction_Mode']   = 'Fallback'
            results['Coverage_Score']    = f"{coverage['coverage_score']*100:.1f}%"
            results['Coverage_Status']   = coverage['status']
            results['Coverage_Warning']  = (
                f"Sector model skipped — coverage "
                f"{coverage['coverage_score']*100:.1f}% below 85% threshold. "
                f"Missing critical features: {coverage['missing_critical']}"
            )
            return results

        # ── Green band: full sector model ─────────────────────────
        # 1. Create lowercase+stripped map for flexible column matching
        df_lower = df_raw.copy()
        df_lower.columns = (df_lower.columns.str.lower()
                            .str.replace(' ', '', regex=False)
                            .str.replace('_', '', regex=False))

        normalized_global_map = {
            k.replace('_', '').replace(' ', ''): v
            for k, v in GLOBAL_CONCEPT_MAP.items()
        }
        df_lower.rename(columns=normalized_global_map, inplace=True)

        # 2. Map back to trained sector column signatures
        target_cols_pool = (
            self.feature_names
            + self.config.get('scale_cols', [])
            + [self.config['target_col']]
            + self.config['drop_cols']
            + self.config.get('ohe_cols', [])
            + self.config.get('label_encode_cols', [])
        )
        target_lower_map = {
            t.lower().replace('_', '').replace(' ', ''): t
            for t in target_cols_pool
        }
        rename_to_target = {}
        for col_idx, col_name in enumerate(df_raw.columns):
            translated_lower  = df_lower.columns[col_idx]
            translated_stripped = translated_lower.replace('_', '').replace(' ', '')
            matched = False
            for target_col in target_cols_pool:
                if translated_lower == target_col.lower():
                    rename_to_target[col_name] = target_col
                    matched = True
                    break
            if not matched and translated_stripped in target_lower_map:
                rename_to_target[col_name] = target_lower_map[translated_stripped]
                matched = True
            if not matched:
                rename_to_target[col_name] = col_name

        df_mapped = df_raw.rename(columns=rename_to_target)

        # Preserve customer ID column
        id_cols = ['customerID', 'CustomerID', 'Customer ID', 'CustomerId',
                   'RowNumber', 'PatientID', 'patientid']
        id_series = None
        for col in df_raw.columns:
            if col in id_cols:
                id_series = df_raw[col].copy()
                break

        df = self._clean(df_mapped)
        df = self._encode(df, fit=False)

        # Align to trained feature set
        for col in self.feature_names:
            if col not in df.columns:
                if hasattr(self.scaler, 'mean_') and col in self.config.get('scale_cols', []):
                    idx = list(self.config['scale_cols']).index(col)
                    df[col] = self.scaler.mean_[idx]
                else:
                    df[col] = 0
        df = df[self.feature_names]

        # Scale
        if hasattr(self.scaler, 'feature_names_in_'):
            scale_cols = [c for c in self.scaler.feature_names_in_ if c in df.columns]
        else:
            scale_cols = [c for c in self.config['scale_cols'] if c in df.columns]
        if scale_cols:
            df[scale_cols] = self.scaler.transform(df[scale_cols])

        X      = df.values
        preds  = self.model.predict(X)
        probas = self.model.predict_proba(X)[:, 1]

        verify_prediction_variance(probas)

        results = pd.DataFrame()
        results['CustomerID']       = (id_series.values if id_series is not None
                                       else [f"UNK_{i}" for i in range(len(df))])
        results['Predicted_Churn']  = pd.Series(preds).map({0: 'No', 1: 'Yes'})
        results['Churn_Probability'] = probas.round(4)
        results['Risk_Level']       = np.select(
            [probas >= 0.70, probas >= 0.40], ['High', 'Medium'], default='Low'
        )
        results['Prediction_Model'] = f"{self.sector.capitalize()} XGBoost (Sector-Specific)"
        results['Prediction_Mode']  = 'Full'
        results['Coverage_Score']   = f"{coverage['coverage_score']*100:.1f}%"
        results['Coverage_Status']  = coverage['status']
        results['Coverage_Warning'] = (
            '' if not coverage['missing_all']
            else f"Low-weight features missing: {coverage['missing_all']}"
        )

        if explain:
            id_col   = results['CustomerID'].values
            log_path = explain_output or f"outputs/shap_logs/{self.sector}_shap_log.csv"
            write_shap_log(self.model, df, self.feature_names, id_col, log_path)

        return results

# ══════════════════════════════════════════════════════════════════
# PHASE B — UNIVERSAL CROSS-SECTOR MODEL
# ══════════════════════════════════════════════════════════════════

# Common features that exist (or can be derived) across all sectors.
# See module-level "RESEARCH / LIMITATIONS NOTE" above — this mapping
# is a documented, subjective modeling choice, not a validated one.
UNIVERSAL_FEATURES = [
    'tenure_normalized',       # tenure / max_tenure per sector
    'charge_normalized',       # monthly cost / max cost per sector
    'has_complaint',           # complaint flag (0/1)
    'satisfaction_score',      # 1-5 scale, normalized
    'is_active',               # active member / recent purchase flag
    'num_products_services',   # number of products/services used
    'is_senior_or_high_risk',  # senior citizen / high BMI / high risk flag
    'has_support',             # tech support / online security / support flag
    'contract_stability',      # 0=no contract, 0.5=short, 1=long term
    'payment_auto',            # automatic payment = 1, manual = 0
    # --- added: previously Ecommerce signal was over-compressed into
    # num_products_services/charge_normalized alone. These 5 give it (and
    # the other sectors, via documented analogs) more resolution instead
    # of collapsing loyalty/incentive/recency/friction into one number.
    'engagement_score',        # order/usage frequency, normalized
    'coupon_dependency',       # reliance on discounts/incentives to stay
    'cashback_engagement',     # financial-incentive engagement
    'recency_score',           # how recently the customer was active
    'convenience_score',       # friction/inconvenience, inverted (1=easy)
    # --- added per adversarial-test audit: explicit interaction terms
    # for two blind spots a tree model tends to miss when it locks onto
    # one dominant feature (long tenure / long contract) and stops
    # weighting a contradicting recent signal:
    'lockin_risk',             # new customer + long-term contract
    'dormant_loyalty_risk',    # long-tenured but recently inactive
    # --- healthcare ROC-AUC improvement: rich schema columns previously
    # collapsed or silently dropped. Distinct features give the model
    # genuine ranking signal instead of an under-resolved feature set.
    'missed_appt_rate',        # missed appointments / total visits (0-1)
    'composite_satisfaction',  # average of all satisfaction sub-scores
    'billing_friction',        # billing_issues / visits (issue rate)
    'care_accessibility',      # 1 - distance_normalized + portal_usage
    'referral_engagement',     # referrals_made / max_referrals
]


def _norm_max(df: pd.DataFrame, col: str, sector: str, norm_stats: dict | None) -> float:
    """
    fix: previously every normalization did `df[col] / df[col].max()`
    against whatever batch happened to be passed in. At inference time
    a single-row (or small-batch) upload makes that row's own value its
    own max, so e.g. CashbackAmount=300 always normalizes to 1.0 — "the
    highest cashback ever seen" — regardless of whether 300 is actually
    high relative to the training distribution. norm_stats (computed
    once from the TRAINING data and persisted) is now used as the
    reference scale whenever available; falls back to the current
    batch's max only if no persisted stat exists for this column (e.g.
    when not yet trained, or a code path calls this before maxima have
    been computed) and prints a one-time-per-call warning so the
    fallback is visible rather than silent.
    """
    key = f"{sector}.{col}"
    if norm_stats is not None and key in norm_stats and norm_stats[key]:
        return norm_stats[key]
    batch_max = df[col].max() if col in df.columns else 1
    if norm_stats is not None and (batch_max == 0 or pd.isna(batch_max)):
        batch_max = 1
    return batch_max if batch_max else 1


def compute_norm_stats(df: pd.DataFrame, sector: str, columns: list[str]) -> dict:
    """
    Compute and key the per-column maxima needed by extract_universal_features
    for one sector, to be merged into the persisted norm_stats dict.
    """
    stats = {}
    for col in columns:
        if col in df.columns:
            m = df[col].max()
            stats[f"{sector}.{col}"] = float(m) if pd.notna(m) and m != 0 else 1.0
    return stats


# Raw columns each sector's extractor normalizes by their max — used to
# pre-compute and persist training-set maxima (see compute_norm_stats).
SECTOR_NORM_COLUMNS = {
    'telecom': ['tenure', 'MonthlyCharges'],
    'ecommerce': ['Tenure', 'CashbackAmount', 'OrderCount', 'CouponUsed',
                  'DaySinceLastOrder', 'WarehouseToHome'],
    'banking': ['Tenure', 'Balance', 'CreditScore'],
    'healthcare': ['Tenure_Months', 'Avg_Out_Of_Pocket_Cost',
                   'Overall_Satisfaction', 'Visits_Last_Year',
                   'Days_Since_Last_Visit', 'Distance_To_Facility_Miles',
                   # satisfaction sub-scores (composite_satisfaction)
                   'Wait_Time_Satisfaction', 'Staff_Satisfaction', 'Provider_Rating',
                   # missed appointment rate
                   'Missed_Appointments',
                   # billing friction
                   'Billing_Issues',
                   # referral engagement
                   'Referrals_Made', 'Portal_Usage',
                   # schema-2 variant columns
                   'FrequencyOfVisits', 'MonthlyPremium',
                   'ClaimHistoryCount', 'CustomerSupportCalls'],
}


def extract_universal_features(
    df: pd.DataFrame,
    sector: str,
    target_col: str,
    norm_stats: dict | None = None,
) -> pd.DataFrame:
    """
    Extract universal features from any sector's dataset, mapping
    sector-specific columns to a common feature space.

    norm_stats: optional dict of persisted {'sector.column': max_value}
    pairs (see compute_norm_stats / _norm_max). Pass this at inference
    time so normalization is anchored to the TRAINING distribution
    rather than whatever batch is currently being scored — without it,
    a single-row prediction trivially normalizes its own value to 1.0.

    LIMITATION: these mappings are best-effort analogues chosen by the
    author, not features validated to measure the same underlying
    construct across sectors (see module docstring). Treat cross-sector
    comparisons made from these features as directional, not precise.
    """
    feat = pd.DataFrame(index=df.index)

    if sector == 'telecom':
        max_tenure = _norm_max(df, 'tenure', sector, norm_stats)
        max_charge = _norm_max(df, 'MonthlyCharges', sector, norm_stats)
        feat['tenure_normalized']      = df['tenure'] / max_tenure if 'tenure' in df.columns else 0
        feat['charge_normalized']      = df['MonthlyCharges'] / max_charge if 'MonthlyCharges' in df.columns else 0
        feat['has_complaint']          = 0
        feat['satisfaction_score']     = 0.5
        # fix: telecom rows are presumed-active subscribers (this is a
        # real characteristic of the dataset, not a placeholder), so 1
        # here is left as-is — unlike recency_score below, which WAS a
        # placeholder masquerading as a real signal.
        feat['is_active']              = 1

        # fix: tolerate minimal Telecom schemas that omit some service
        # columns (MultipleLines, OnlineSecurity, etc.) — default any
        # missing service column to 'No' rather than KeyError'ing.
        service_cols = [
            'PhoneService', 'MultipleLines', 'InternetService',
            'OnlineSecurity', 'OnlineBackup', 'DeviceProtection',
            'TechSupport', 'StreamingTV', 'StreamingMovies'
        ]
        for col in service_cols:
            if col not in df.columns:
                df[col] = 'No'
        feat['num_products_services']  = (
            df[service_cols]
            .apply(lambda row: (row == 'Yes').sum(), axis=1)
            / len(service_cols)
        )

        feat['is_senior_or_high_risk'] = df['SeniorCitizen'] if 'SeniorCitizen' in df.columns else 0
        feat['has_support']            = (df['TechSupport'] == 'Yes').astype(int) if 'TechSupport' in df.columns else 0
        feat['contract_stability']     = df['Contract'].map({
            'Month-to-month': 0.0,
            'One year': 0.5,
            'Two year': 1.0
        }).fillna(0) if 'Contract' in df.columns else 0
        feat['payment_auto']           = df['PaymentMethod'].str.contains(
            'automatic', case=False, na=False
        ).astype(int) if 'PaymentMethod' in df.columns else 0

        # --- new universal features (telecom analogs) ---
        # No direct order/coupon/cashback/distance analogs exist in
        # Telecom. fix: recency_score was hardcoded to 1 ("most recent
        # possible"), which overstates a concept Telecom doesn't actually
        # track — 0.5 honestly represents "no comparable information"
        # rather than implying best-possible recency.
        feat['engagement_score']       = feat['num_products_services']
        feat['coupon_dependency']      = 0
        feat['cashback_engagement']    = 0
        feat['recency_score']          = 0.5  # no "last order" concept — neutral, not "best"
        feat['convenience_score']      = feat['contract_stability']

        # fix (adversarial audit): "new customer + long contract" was
        # being read as low-risk on contract length alone, ignoring that
        # the commitment is untested. Telecom has no "days since last
        # order" concept, so dormant_loyalty_risk has no analog here.
        feat['lockin_risk']            = feat['contract_stability'] * (1 - feat['tenure_normalized'])
        feat['dormant_loyalty_risk']   = 0
        # New healthcare-specific features — neutral defaults for telecom
        feat['missed_appt_rate']       = 0
        feat['composite_satisfaction'] = feat['satisfaction_score']
        feat['billing_friction']       = 0
        feat['care_accessibility']     = 0.5
        feat['referral_engagement']    = 0

    elif sector == 'ecommerce':
        max_tenure  = _norm_max(df, 'Tenure', sector, norm_stats)
        max_cash    = _norm_max(df, 'CashbackAmount', sector, norm_stats)
        max_orders  = _norm_max(df, 'OrderCount', sector, norm_stats)
        max_coupon  = _norm_max(df, 'CouponUsed', sector, norm_stats)
        max_recency = _norm_max(df, 'DaySinceLastOrder', sector, norm_stats)
        max_dist    = _norm_max(df, 'WarehouseToHome', sector, norm_stats)

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
            ['Credit Card','Debit Card','UPI']
        ).astype(int) if 'PreferredPaymentMode' in df.columns else 0

        # --- new universal features: real Ecommerce churn signals,
        # previously over-compressed into num_products_services alone ---
        feat['engagement_score']       = df['OrderCount'] / max_orders if 'OrderCount' in df.columns else 0
        feat['coupon_dependency']      = df['CouponUsed'] / max_coupon if 'CouponUsed' in df.columns else 0
        feat['cashback_engagement']    = df['CashbackAmount'] / max_cash if 'CashbackAmount' in df.columns else 0
        feat['recency_score']          = df['DaySinceLastOrder'] / max_recency if 'DaySinceLastOrder' in df.columns else 0.5
        feat['convenience_score']      = 1 - (df['WarehouseToHome'] / max_dist) if 'WarehouseToHome' in df.columns else 0.5

        # fix (adversarial audit): a 4-year-tenure customer who hasn't
        # ordered in 90 days is exactly the case where high tenure was
        # masking real disengagement. This makes that combination an
        # explicit, multiplicative signal instead of relying on the tree
        # to discover it via a deep split. Ecommerce has no contract
        # concept, so lockin_risk has no analog here.
        feat['dormant_loyalty_risk']   = feat['tenure_normalized'] * feat['recency_score']
        feat['lockin_risk']            = 0
        # New healthcare-specific features — neutral defaults for ecommerce
        feat['missed_appt_rate']       = 0
        feat['composite_satisfaction'] = feat['satisfaction_score']
        feat['billing_friction']       = feat['has_complaint']  # complaint as friction proxy
        feat['care_accessibility']     = feat['convenience_score']
        feat['referral_engagement']    = 0

    elif sector == 'banking':
        max_tenure = _norm_max(df, 'Tenure', sector, norm_stats)
        max_balance = _norm_max(df, 'Balance', sector, norm_stats)
        max_credit = _norm_max(df, 'CreditScore', sector, norm_stats)

        feat['tenure_normalized']      = df['Tenure'] / max_tenure if 'Tenure' in df.columns else 0
        feat['charge_normalized']      = df['Balance'] / max_balance if 'Balance' in df.columns else 0
        feat['has_complaint']          = 0
        feat['satisfaction_score']     = df['CreditScore'] / max_credit if 'CreditScore' in df.columns else 0.5
        feat['is_active']              = df['IsActiveMember'] if 'IsActiveMember' in df.columns else 0.5
        feat['num_products_services']  = df['NumOfProducts'] / 4.0 if 'NumOfProducts' in df.columns else 0
        feat['is_senior_or_high_risk'] = (df['Age'] > 55).astype(int) if 'Age' in df.columns else 0
        feat['has_support']            = df['HasCrCard'] if 'HasCrCard' in df.columns else 0
        feat['contract_stability']     = df['Tenure'] / max_tenure if 'Tenure' in df.columns else 0
        # fix: payment_auto was hardcoded to 1 for every banking row —
        # an unfounded "best possible" assumption with no supporting
        # column. 0.5 honestly reflects "no comparable information".
        feat['payment_auto']           = 0.5

        # --- new universal features (banking analogs) ---
        # No coupon/cashback/warehouse-distance concept in banking;
        # engagement reuses product usage, recency reuses active-member
        # flag, convenience defaults neutral (no equivalent friction metric).
        feat['engagement_score']       = feat['num_products_services']
        feat['coupon_dependency']      = 0
        feat['cashback_engagement']    = feat['charge_normalized']  # balance as financial-engagement proxy
        feat['recency_score']          = feat['is_active']
        feat['convenience_score']      = 0.5

        # fix (adversarial audit): long-tenured account holder who has
        # gone inactive (IsActiveMember=0) is the banking analog of the
        # Ecommerce dormant-loyalist case. No separate contract concept
        # exists in banking beyond tenure, so lockin_risk has no analog.
        feat['dormant_loyalty_risk']   = feat['tenure_normalized'] * (1 - feat['is_active'])
        feat['lockin_risk']            = 0
        # New healthcare-specific features — neutral defaults for banking
        feat['missed_appt_rate']       = 0
        feat['composite_satisfaction'] = feat['satisfaction_score']
        feat['billing_friction']       = 0
        feat['care_accessibility']     = 0.5
        feat['referral_engagement']    = 0

    elif sector == 'healthcare':
        # Column names may arrive in their original mixed-case spaced form
        # (e.g. "Visits Last Year") OR already lowercased+stripped by the
        # column normalization pass (e.g. "visitslastyear"). Check both so
        # the correct schema branch is entered regardless of how the caller
        # processed the DataFrame before passing it here.
        _has_tenure  = any(c in df.columns for c in ('Tenure_Months',  'tenuremonths',  'Tenure Months'))
        _has_visits  = any(c in df.columns for c in ('Visits_Last_Year', 'visitslastyear', 'Visits Last Year'))
        _has_premium = any(c in df.columns for c in ('MonthlyPremium', 'monthlypremium'))
        _has_freq    = any(c in df.columns for c in ('FrequencyOfVisits', 'frequencyofvisits'))

        # Helper: find first matching column regardless of name variant
        def _hcol(df, *candidates):
            for c in candidates:
                if c in df.columns:
                    return c
            return None

        if _has_tenure or _has_visits:
            c_tenure  = _hcol(df, 'Tenure_Months',  'tenuremonths',  'Tenure Months')
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

            # --- core universal features ---
            feat['tenure_normalized']      = df[c_tenure]  / max_tenure if c_tenure  else 0.5
            feat['charge_normalized']      = df[c_cost]    / max_cost   if c_cost    else 0
            feat['has_complaint']          = (df[c_billing] > 0).astype(int) if c_billing else 0
            feat['satisfaction_score']     = df[c_sat]     / max_sat    if c_sat     else 0.5
            feat['is_active']              = (df[c_lastv] <= 90).astype(int) if c_lastv else 0.5
            feat['num_products_services']  = df[c_visits]  / max_visits if c_visits  else 0.5
            feat['is_senior_or_high_risk'] = (df[c_age] > 65).astype(int) if c_age else 0
            feat['has_support']            = df[c_portal]  if c_portal else 0
            feat['contract_stability']     = df[c_tenure]  / max_tenure if c_tenure  else 0.5
            feat['payment_auto']           = 0.5
            feat['engagement_score']       = feat['num_products_services']
            feat['coupon_dependency']      = 0
            feat['cashback_engagement']    = 0
            feat['recency_score']          = 1 - (df[c_lastv] / max_lastv) if c_lastv else 0.5
            feat['convenience_score']      = 1 - (df[c_dist]  / max_dist)  if c_dist  else 0.5
            feat['dormant_loyalty_risk']   = feat['tenure_normalized'] * (1 - feat['is_active'])
            feat['lockin_risk']            = 0

            # --- new healthcare ROC-AUC features ---
            # missed_appt_rate: ratio of missed to total visits. Saturates
            # at 1.0. Patients who frequently miss are signalling low
            # commitment before formal churn; using rate (not raw count)
            # normalises across patients with different total visit volumes.
            if c_missed and c_visits:
                total = df[c_visits].replace(0, np.nan)
                feat['missed_appt_rate'] = (df[c_missed] / total).clip(0, 1).fillna(0)
            elif c_missed:
                feat['missed_appt_rate'] = (df[c_missed] / max_visits).clip(0, 1)
            else:
                feat['missed_appt_rate'] = pd.Series(0.0, index=df.index)

            # composite_satisfaction: mean of all available sub-scores
            # rather than just one field. Divergence between sub-scores
            # (e.g. overall=4, staff=1) is a disengagement signal that a
            # single overall score masks.
            sat_scores = []
            if c_sat:    sat_scores.append(df[c_sat]    / max_sat)
            if c_wait:   sat_scores.append(df[c_wait]   / max_wait)
            if c_staff:  sat_scores.append(df[c_staff]  / max_staff)
            if c_rating: sat_scores.append(df[c_rating] / max_rating)
            if sat_scores:
                feat['composite_satisfaction'] = pd.concat(sat_scores, axis=1).mean(axis=1)
            else:
                feat['composite_satisfaction'] = feat['satisfaction_score']

            # billing_friction: complaints per visit. A single complaint
            # across 20 visits is very different from 3 across 3 visits.
            if c_billing and c_visits:
                total = df[c_visits].replace(0, np.nan)
                feat['billing_friction'] = (df[c_billing] / total).clip(0, 1).fillna(0)
            elif c_billing:
                feat['billing_friction'] = (df[c_billing] / max_billing).clip(0, 1)
            else:
                feat['billing_friction'] = pd.Series(0.0, index=df.index)

            # care_accessibility: combines physical friction (distance)
            # with digital offset (portal reduces friction). Range [0, 1];
            # higher = more accessible. Low accessibility + low portal
            # usage = maximum disengagement risk.
            dist_norm   = (df[c_dist] / max_dist).clip(0, 1) if c_dist   else pd.Series(0.5, index=df.index)
            portal_norm = df[c_portal].clip(0, 1)             if c_portal else pd.Series(0.0, index=df.index)
            feat['care_accessibility'] = ((1 - dist_norm) + portal_norm).clip(0, 1)

            # referral_engagement: normalized referrals. Long-tenured
            # patients with zero referrals are a distinct disengagement
            # signal not captured by any existing feature.
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
            feat['is_senior_or_high_risk'] = (df[c_age] > 65).astype(int) if c_age else 0
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
            # New features for schema-2 (partial analogs where available)
            feat['missed_appt_rate']       = 0
            feat['composite_satisfaction'] = feat['satisfaction_score']
            feat['billing_friction']       = (df[c_calls] / max_calls).clip(0, 1) if c_calls else 0
            feat['care_accessibility']     = 0.5
            feat['referral_engagement']    = 0

        else:
            for col in UNIVERSAL_FEATURES:
                feat[col] = 0.5
    y = df[target_col].astype(str).str.strip()
    y = y.map({
        'Yes': 1, 'No': 0,
        'yes': 1, 'no': 0,
        'YES': 1, 'NO': 0,
        '1': 1, '0': 0,
    })
    y = pd.to_numeric(y, errors='coerce').fillna(0).astype(int)

    feat['Churn'] = y.values
    feat['Sector'] = sector

    return feat


def train_universal_model(tune_metric: str | None = None) -> None:
    """
    Phase B: Merge all 4 sectors into universal feature space
    and train one XGBoost model on everything.

    tune_metric: if 'f1' or 'recall', runs GridSearchCV optimizing for
    that metric instead of training with fixed hyperparameters.
    """
    print("\n" + "="*55)
    print("  PHASE B — Training Universal Cross-Sector Model")
    print("="*55)

    all_data = []
    norm_stats: dict = {}

    for sector, config in SECTOR_CONFIG.items():
        path = config['data_path']
        if not Path(path).exists():
            print(f"  Skipping {sector} — data not found at {path}")
            continue

        print(f"  Loading {sector}...")
        df = pd.read_csv(path)

        # Fix TotalCharges for telecom
        if 'TotalCharges' in df.columns:
            df['TotalCharges'] = pd.to_numeric(
                df['TotalCharges'], errors='coerce'
            ).fillna(0)

        # Fill nulls
        for col in df.select_dtypes(include='number').columns:
            df[col] = df[col].fillna(df[col].median())
        for col in df.select_dtypes(include=['object', 'string']).columns:
            df[col] = df[col].fillna(df[col].mode()[0])

        # fix: compute and persist this sector's normalization maxima
        # from the TRAINING data before extraction, so inference-time
        # normalization has a stable reference scale instead of
        # normalizing each new batch against itself.
        norm_stats.update(
            compute_norm_stats(df, sector, SECTOR_NORM_COLUMNS.get(sector, []))
        )

        feat_df = extract_universal_features(
            df, sector, config['target_col'], norm_stats=norm_stats
        )
        all_data.append(feat_df)
        print(f"  {sector}: {len(feat_df)} rows extracted")

    if not all_data:
        raise RuntimeError("No sector data found. Check data paths.")

    combined = pd.concat(all_data, ignore_index=True)
    print(f"\n  Combined dataset: {combined.shape[0]} rows")
    print(f"  Churn rate      : {combined['Churn'].mean()*100:.1f}%")

    print("\n  Per-sector churn rate BEFORE balancing:")
    print(combined.groupby('Sector')['Churn'].agg(['mean', 'count']))

    # fix: per-sector class balancing — root cause of the audit's
    # "Healthcare predicted Churn for almost everyone" bug. Sector_Encoded
    # is a literal input feature; if one sector's raw churn rate is far
    # from 50% (e.g. Healthcare's 1,367 vs 633), the tree learns
    # "Sector_Encoded == healthcare" as a cheap shortcut for "prior risk
    # is high" instead of relying on the actual behavioral features. The
    # single global SMOTE pass after concatenation does NOT fix this — it
    # balances the overall 0/1 ratio, but each sector's internal skew
    # (and its correlation with Sector_Encoded) survives untouched.
    # Balancing each sector to ~50/50 BEFORE concatenation removes that
    # shortcut: Sector_Encoded can no longer predict Churn on its own, so
    # the model is forced back onto genuine behavioral signal regardless
    # of sector.
    balanced_parts = []
    for sec_name, group in combined.groupby('Sector'):
        counts = group['Churn'].value_counts()
        if len(counts) < 2:
            balanced_parts.append(group)
            continue
        majority_n = counts.max()
        minority_class = counts.idxmin()
        minority = group[group['Churn'] == minority_class]
        majority = group[group['Churn'] != minority_class]
        # simple random oversample of the minority class within this
        # sector up to the majority count (kept simple/fast here since
        # this runs on already-engineered, low-dimensional features;
        # SMOTE is still applied globally afterward for the real
        # synthetic-sample diversity).
        minority_resampled = minority.sample(
            n=majority_n, replace=True, random_state=42
        )
        balanced_parts.append(pd.concat([majority, minority_resampled]))

    combined = pd.concat(balanced_parts, ignore_index=True)
    print("\n  Per-sector churn rate AFTER balancing:")
    print(combined.groupby('Sector')['Churn'].agg(['mean', 'count']))

    # Encode sector column
    le_sector = LabelEncoder()
    combined['Sector_Encoded'] = le_sector.fit_transform(combined['Sector'])
    combined.drop(columns=['Sector'], inplace=True)

    combined = combined.replace([np.inf, -np.inf], np.nan)
    nan_total = combined.isna().sum().sum()
    print(f"  Total NaNs before fill: {nan_total}")
    if nan_total > 0:
        print("  WARNING: NaNs found in combined dataset. Filling with 0.")
        combined = combined.fillna(0)

    X = combined.drop(columns=['Churn'])
    y = combined['Churn'].values

    feature_names = X.columns.tolist()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test  = scaler.transform(X_test)

    smote = SMOTE(random_state=42)
    X_train_sm, y_train_sm = smote.fit_resample(X_train, y_train)

    if tune_metric:
        print(f"\n  Tuning universal model hyperparameters (scoring='{tune_metric}')...")
        param_grid = {
            'n_estimators': [200, 300, 400],
            'max_depth': [4, 5, 6],
            'learning_rate': [0.03, 0.05, 0.1],
            'subsample': [0.8, 1.0],
            'colsample_bytree': [0.8, 1.0],
        }
        base_model = XGBClassifier(
            random_state=42, use_label_encoder=False,
            eval_metric='logloss', verbosity=0
        )
        search = GridSearchCV(
            base_model, param_grid,
            scoring=tune_metric, cv=3,
            n_jobs=-1, verbose=0
        )
        search.fit(X_train_sm, y_train_sm)
        model = search.best_estimator_
        print(f"  Best params: {search.best_params_}")
        print(f"  Best CV {tune_metric}: {search.best_score_:.4f}")
    else:
        print("\n  Training XGBoost universal model...")
        model = XGBClassifier(
            n_estimators=300, learning_rate=0.05,
            max_depth=5, subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            use_label_encoder=False,
            eval_metric='logloss',
            verbosity=0
        )
        model.fit(X_train_sm, y_train_sm)

    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    print("\n  Universal Model — Test Set Results:")
    print(f"  Accuracy  : {accuracy_score(y_test, y_pred):.4f}")
    print(f"  Precision : {precision_score(y_test, y_pred):.4f}")
    print(f"  Recall    : {recall_score(y_test, y_pred):.4f}")
    print(f"  F1        : {f1_score(y_test, y_pred):.4f}")
    print(f"  ROC-AUC   : {roc_auc_score(y_test, y_proba):.4f}")
    print()
    print(classification_report(
        y_test, y_pred,
        target_names=['No Churn', 'Churn']
    ))

    UNIVERSAL_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model,         UNIVERSAL_MODEL_PATH)
    joblib.dump(scaler,        UNIVERSAL_SCALER_PATH)
    joblib.dump(le_sector,     str(UNIVERSAL_MODEL_PATH).replace('.pkl','_le_sector.pkl'))
    joblib.dump(norm_stats,    UNIVERSAL_NORM_STATS_PATH)
    pd.Series(feature_names).to_csv(UNIVERSAL_FEATURES_PATH, index=False)

    print(f"  Universal model saved : {UNIVERSAL_MODEL_PATH}")
    print(f"  Universal scaler saved: {UNIVERSAL_SCALER_PATH}")
    print(f"  Norm stats saved      : {UNIVERSAL_NORM_STATS_PATH}")


def verify_prediction_variance(probabilities: np.ndarray, threshold: float = 1e-4) -> None:
    """
    Diagnostic guard against silent flatlining (every row getting ~the
    same probability), which is the symptom of a schema-misalignment
    bug — missing/garbled columns get filled with 0, the feature matrix
    carries no real signal, and XGBoost just emits its base score for
    every row. Only meaningful with >1 row; a single-row prediction has
    no variance by definition and is not itself evidence of a bug.
    """
    if len(probabilities) > 1 and np.std(probabilities) < threshold:
        raise RuntimeError(
            "CRITICAL WARNING: Model outputs show ~zero variance "
            f"(std={np.std(probabilities):.6f} < {threshold}). This usually "
            "means the input features are misaligned with what the model "
            "was trained on (e.g. missing/renamed columns silently filled "
            "with 0), not that every customer genuinely has the same risk. "
            "Inspect the aligned feature matrix before trusting these "
            "predictions."
        )


def compute_coverage_score(
    df_input: pd.DataFrame,
    sector: str,
    mode: str = 'sector',
    green_threshold: float = 0.85,
    yellow_threshold: float = 0.60,
) -> dict:
    """
    Compute a weighted feature coverage score for the input CSV and
    determine which model should be used for prediction.

    Coverage Score = sum(weight_i × quality_i) / sum(weight_i)

    where quality_i = 1 if the feature is:
        • present in the input CSV  (column exists, after alias normalisation)
        • non-null                  (< 95% null values)
        • non-constant              (more than one unique non-null value)
    and quality_i = 0 otherwise.

    Routing bands
    ─────────────
    Green  ≥ 85%  →  Full sector-specific XGBoost  (Prediction_Mode = 'Full')
    Yellow 60–85% →  Universal XGBoost fallback     (Prediction_Mode = 'Fallback')
    Red    < 60%  →  Hard stop, no prediction       (Prediction_Mode = 'Refused')

    Returns
    ───────
    coverage_score   float   weighted score in [0, 1]
    status           str     'Green' | 'Yellow' | 'Red'
    prediction_mode  str     'Full' | 'Fallback' | 'Refused'
    missing_critical list    weight≥4 features that failed quality check
    missing_all      list    all features that failed quality check
    detail           list[dict]  per-feature breakdown for logging
    """
    weights = SECTOR_FEATURE_WEIGHTS.get(sector, {})
    if not weights:
        # Unknown sector — treat all present columns as weight-1
        weights = {c: 1 for c in df_input.columns}

    total_weight = sum(weights.values())

    # Normalise input column names once for O(1) lookup
    def _strip(s: str) -> str:
        return s.lower().replace('_', '').replace(' ', '')

    stripped_to_original = {_strip(c): c for c in df_input.columns}

    detail          = []
    earned_weight   = 0.0
    missing_all     = []
    missing_critical = []

    for feat, weight in weights.items():
        feat_stripped = _strip(feat)
        orig_col      = stripped_to_original.get(feat_stripped)

        if orig_col is None:
            quality  = 0
            reason   = 'absent'
        else:
            col = df_input[orig_col]
            pct_null = col.isna().mean()
            numeric  = pd.to_numeric(col, errors='coerce')
            n_unique = numeric.dropna().nunique()

            if pct_null >= 0.95:
                quality = 0
                reason  = f'mostly null ({pct_null*100:.0f}%)'
            elif n_unique <= 1:
                quality = 0
                reason  = 'constant (no variance)'
            else:
                quality = 1
                reason  = 'OK'

        earned_weight += weight * quality
        detail.append({
            'feature' : feat,
            'weight'  : weight,
            'quality' : quality,
            'reason'  : reason,
        })
        if quality == 0:
            missing_all.append(feat)
            if weight >= 4:
                missing_critical.append(feat)

    coverage_score = earned_weight / total_weight if total_weight > 0 else 0.0

    if coverage_score >= green_threshold:
        status          = 'Green'
        prediction_mode = 'Full'
    elif coverage_score >= yellow_threshold:
        status          = 'Yellow'
        prediction_mode = 'Fallback'
    else:
        status          = 'Red'
        prediction_mode = 'Refused'

    # ── Print report ──────────────────────────────────────────────
    sep   = '─' * 60
    icons = {'Green': '✔', 'Yellow': '△', 'Red': '✖'}
    print(f"\n{sep}")
    print(f"  COVERAGE SCORE REPORT  [{mode.upper()} / {sector.upper()}]")
    print(sep)
    print(f"  Weighted coverage score : {coverage_score*100:.1f}%")
    print(f"  Status                  : {icons[status]} {status}")
    print(f"  Prediction mode         : {prediction_mode}")

    if missing_critical:
        print(f"\n  High-weight features missing or unusable (weight ≥ 4):")
        for f in missing_critical:
            w = weights[f]
            r = next(d['reason'] for d in detail if d['feature'] == f)
            print(f"    [{w}]  {f}  ({r})")

    low_missing = [f for f in missing_all if f not in missing_critical]
    if low_missing:
        print(f"\n  Lower-weight features missing or unusable:")
        for f in low_missing:
            w = weights[f]
            r = next(d['reason'] for d in detail if d['feature'] == f)
            print(f"    [{w}]  {f}  ({r})")

    if status == 'Green':
        print(f"\n  Using full sector-specific model.")
    elif status == 'Yellow':
        print(f"\n  Coverage below 85% — routing to universal model fallback.")
        print(f"  Predictions will be less precise than the sector model.")
    else:
        print(f"\n  Coverage below 60% — prediction refused.")
        print(f"  Enrich the input CSV with the critical features listed above.")

    print(sep)

    return {
        'coverage_score'    : round(coverage_score, 4),
        'status'            : status,
        'prediction_mode'   : prediction_mode,
        'missing_critical'  : missing_critical,
        'missing_all'       : missing_all,
        'detail'            : detail,
    }


def write_shap_log(
    model,
    X_df: pd.DataFrame,
    feature_names: list[str],
    id_values: np.ndarray | None,
    output_path: str,
    top_n: int = 3,
) -> None:
    """
    Strategic suggestion (audit): per-row SHAP explanation log so a
    business analyst can see exactly which features pushed an individual
    customer's churn probability up or down, instead of treating the
    model as a black box. Writes one row per customer with their top_n
    highest-magnitude contributing features and signed SHAP values.

    Degrades gracefully (prints a warning, writes nothing) if shap isn't
    installed — this is an enhancement, not a hard dependency for the
    rest of the pipeline.
    """
    if not SHAP_AVAILABLE:
        print(
            "  WARNING: shap is not installed — skipping explanation log. "
            "Run `pip install shap` to enable --explain."
        )
        return

    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_df[feature_names])
    except Exception as exc:
        print(f"  WARNING: SHAP explanation failed ({exc}); skipping log.")
        return

    rows = []
    for i in range(len(X_df)):
        row_shap = shap_values[i]
        # Top-N features by absolute contribution, signed
        order = np.argsort(-np.abs(row_shap))[:top_n]
        record = {
            'CustomerID': id_values[i] if id_values is not None else i
        }
        for rank, idx in enumerate(order, start=1):
            record[f'top{rank}_feature'] = feature_names[idx]
            record[f'top{rank}_shap_value'] = round(float(row_shap[idx]), 4)
        rows.append(record)

    log_df = pd.DataFrame(rows)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    log_df.to_csv(output_path, index=False)
    print(f"  SHAP explanation log saved: {output_path}")


def transform_features_by_sector(df: pd.DataFrame, sector: str) -> pd.DataFrame:
    """
    Convert an inference DataFrame into the universal model feature matrix.
    The universal model was trained from extract_universal_features(), so
    this helper mirrors that path with a dummy target when scoring files
    that do not contain an actual churn label.
    """
    config = SECTOR_CONFIG[sector]
    df_working = df.copy()

    if 'TotalCharges' in df_working.columns:
        df_working['TotalCharges'] = pd.to_numeric(
            df_working['TotalCharges'], errors='coerce'
        ).fillna(0)

    for col in df_working.select_dtypes(include='number').columns:
        df_working[col] = df_working[col].fillna(df_working[col].median())
    for col in df_working.select_dtypes(include=['object', 'string']).columns:
        mode = df_working[col].mode()
        fill_value = mode.iloc[0] if not mode.empty else ''
        df_working[col] = df_working[col].fillna(fill_value)

    # Last-line-of-defence: re-run numeric coercion on df_working using
    # standardized (lowercased, stripped) column names so that any dirty
    # string values that slipped through the earlier sanitize pass (e.g.
    # due to pandas StringDtype preventing assignment) are cleaned before
    # the arithmetic in extract_universal_features runs.
    df_working = sanitize_numerical_columns(df_working)

    target_col = config['target_col']
    if target_col not in df_working.columns:
        df_working[target_col] = 0

    norm_stats = None
    if UNIVERSAL_NORM_STATS_PATH.exists():
        norm_stats = joblib.load(UNIVERSAL_NORM_STATS_PATH)

    features = extract_universal_features(
        df_working, sector, target_col, norm_stats=norm_stats
    )

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


def derive_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect date columns (last interaction, last visit, last order, etc.)
    and derive numeric gap-in-days columns from them so feature extraction
    can use recency/activity signals even when the raw CSV has a date field
    instead of a pre-computed days-since column.

    Looks for columns whose lowercased+stripped name contains any of:
      'lastinteraction', 'lastvisit', 'lastorder', 'lastseen',
      'lastcontact', 'lastpurchase', 'lastappointment'
    and derives 'Days_Since_Last_Visit' (healthcare/universal) or
    'DaySinceLastOrder' (ecommerce) from them.

    Reference date: today (at pipeline run time).  Negative values
    (future dates) are clamped to 0.
    """
    df_out = df.copy()
    today  = pd.Timestamp.now().normalize()

    # Map of normalized column-name substrings → derived column name to add
    patterns = [
        ('lastinteraction', 'Days_Since_Last_Visit'),
        ('lastvisit',       'Days_Since_Last_Visit'),
        ('lastappointment', 'Days_Since_Last_Visit'),
        ('lastcontact',     'Days_Since_Last_Visit'),
        ('lastseen',        'Days_Since_Last_Visit'),
        ('lastorder',       'DaySinceLastOrder'),
        ('lastpurchase',    'DaySinceLastOrder'),
    ]

    for original_col in df.columns:
        normalized = original_col.lower().replace(' ', '').replace('_', '')
        for pattern, derived_col in patterns:
            if pattern in normalized:
                # Only derive if the target column doesn't already exist
                if derived_col in df_out.columns:
                    break
                try:
                    parsed = pd.to_datetime(df_out[original_col], infer_datetime_format=True, errors='coerce')
                    days   = (today - parsed).dt.days.clip(lower=0)
                    if days.notna().any():
                        df_out[derived_col] = days.fillna(days.median())
                        print(f"  [temporal] '{original_col}' → '{derived_col}' "
                              f"(range: {int(days.min())}–{int(days.max())} days)")
                except Exception:
                    pass  # unparseable date column — leave as-is
                break

    return df_out


def sanitize_numerical_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans raw human strings like '12 months', '₹85.50', '120 USD',
    and '14 visits' into clean, processable floats before any feature
    extraction or normalization runs.

    Works by matching each column's lowercased/stripped name against a
    known list of columns that must be numeric across all sector variants,
    then stripping everything except digits, decimal points, and minus
    signs before casting to float.
    """
    numeric_targets = {
        'tenure', 'monthlycharges', 'totalcharges',
        'age', 'visitslastyear', 'avgoutofpocketcost', 'billingissues',
        'creditscore', 'balance', 'numofproducts',
        'satisfactionscore', 'cashbackamount',
        # additional healthcare / ecommerce variants
        'tenuremonths', 'daysincelastvisit', 'overallsatisfaction',
        'waittimesatisfaction', 'staffsatisfaction', 'providerrating',
        'portalusage', 'referralsmade', 'distancetofacilitymiles',
        'missedappointments', 'daysincelastorder', 'couponused',
        'ordercount', 'cashbackamount', 'warehousetohome',
        'hourspendonapp', 'numberofdeviceregistered', 'numberofaddress',
        'orderamounthikefromlastyear', 'estimatedsalary',
    }

    df_clean = df.copy()
    lower_cols = (
        df_clean.columns
        .str.lower()
        .str.replace(' ', '', regex=False)
        .str.replace('_', '', regex=False)
    )
    col_mapping = dict(zip(df_clean.columns, lower_cols))

    for original_col, standardized_name in col_mapping.items():
        if standardized_name in numeric_targets:
            # Cast to Python object dtype first so StringDtype (pandas 3+
            # future.infer_string default) doesn't block numeric assignment.
            raw = df_clean[original_col].astype(object).astype(str).str.strip()
            # Strip currency symbols, unit words, and anything non-numeric
            # (keeps digits, decimal dot, and leading minus sign)
            s_clean = raw.str.replace(r'[^\d\.\-]', '', regex=True)
            s_clean = s_clean.replace('', np.nan)
            # Assign as plain float64 to guarantee downstream arithmetic works
            df_clean[original_col] = pd.to_numeric(s_clean, errors='coerce').astype('float64')

    return df_clean


def predict_universal(input_path: str, force_sector: str | None = None, explain: bool = False) -> pd.DataFrame:
    """
    Predict churn across all industries using the unified Phase B master model.
    Robust against arbitrary alternative input schemas.
    """
    df_raw = pd.read_csv(input_path)

    # Strip unit suffixes and currency symbols from numeric columns before
    # any sector detection or feature extraction runs, so strings like
    # "12 months" or "₹120" don't crash normalization arithmetic.
    df_raw = sanitize_numerical_columns(df_raw)

    # Parse any date column (Last_Interaction_Date, etc.) into a numeric
    # days-since column so recency signal isn't silently lost when the
    # CSV has a date instead of a pre-computed gap.
    df_raw = derive_temporal_features(df_raw)

    # Coverage scoring — use detected sector once known; pre-check with
    # raw columns to surface a warning before heavy feature extraction.
    _sector_for_coverage = force_sector if force_sector else detect_sector(df_raw)
    _coverage = compute_coverage_score(
        df_input=df_raw,
        sector=_sector_for_coverage,
        mode='universal',
    )

    # Run structural detection before modifying schemas
    sector = force_sector or detect_sector(df_raw)
    print(f" Auto-detected sector: {sector}")

    # Run inline translation inside raw columns
    df_lower = df_raw.copy()
    # Bug 6 fix: strip spaces and underscores so "Monthly Charges" matches "monthlycharges"
    df_lower.columns = df_lower.columns.str.lower().str.replace(' ', '', regex=False).str.replace('_', '', regex=False)

    # Use the global concept map (sector-neutral) instead of a hardcoded healthcare map
    # that incorrectly renamed Telecom/Ecommerce columns to healthcare terms (Bug 4 fix)
    normalized_global_map = {
        k.replace('_', '').replace(' ', ''): v
        for k, v in GLOBAL_CONCEPT_MAP.items()
    }
    df_lower.rename(columns=normalized_global_map, inplace=True)

    config = SECTOR_CONFIG[sector]
    target_cols_pool = config['scale_cols'] + [config['target_col']] + config['drop_cols'] + config.get('ohe_cols', [])

    rename_to_target = {}
    for col_idx, col_name in enumerate(df_raw.columns):
        translated_lower = df_lower.columns[col_idx]
        matched = False
        for target_col in target_cols_pool:
            if translated_lower == target_col.lower():
                rename_to_target[col_name] = target_col
                matched = True
                break
        if not matched:
            rename_to_target[col_name] = col_name

    df_mapped = df_raw.rename(columns=rename_to_target)

    # Call your pre-built cross-sector pipeline engine
    X_processed = transform_features_by_sector(df_mapped, sector)

    # Load scaling and prediction matrix properties
    scaler = joblib.load("outputs/universal/universal_scaler.pkl")
    model = joblib.load("outputs/universal/universal_xgb_model.pkl")

    # Enforce feature names check against scaler properties
    if hasattr(scaler, 'feature_names_in_'):
        expected_features = scaler.feature_names_in_
        for col in expected_features:
            if col not in X_processed.columns:
                X_processed[col] = 0
        X_processed = X_processed[expected_features]
        X_scaled = scaler.transform(X_processed)
    else:
        X_scaled = scaler.transform(X_processed)

    probas = model.predict_proba(X_scaled)[:, 1]
    preds = model.predict(X_scaled)

    # Variance check
    verify_prediction_variance(probas)

    results = pd.DataFrame()
    id_cols = ['customerID','CustomerID','Customer ID','CustomerId','PatientID','patientid']
    id_series = None
    for col in df_raw.columns:
        if col in id_cols:
            id_series = df_raw[col]
            break

    results['CustomerID'] = id_series.values if id_series is not None else [f"UNK_{i}" for i in range(len(df_raw))]
    results['Predicted_Churn'] = pd.Series(preds).map({0: 'No', 1: 'Yes'})
    results['Churn_Probability'] = probas.round(4)
    results['Risk_Level'] = np.select([probas >= 0.70, probas >= 0.40], ['High', 'Medium'], default='Low')
    results['Sector']           = sector.capitalize()
    results['Model']            = 'XGBoost (Universal)'
    results['Prediction_Model'] = 'XGBoost (Universal)'
    results['Prediction_Mode']  = 'Universal'
    results['Coverage_Score']   = f"{_coverage['coverage_score']*100:.1f}%"
    results['Coverage_Status']  = _coverage['status']
    results['Coverage_Warning'] = (
        '' if not _coverage['missing_critical']
        else f"Missing critical features: {_coverage['missing_critical']}"
    )

    return results

# ══════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Universal schema-agnostic churn predictor."
    )
    parser.add_argument(
        '--mode',
        choices=['train_sector', 'train_universal',
                 'sector', 'universal', 'train_all', 'list_heads'],
        default='train_all',
        help=(
            "train_all       : train all sector models + universal model\n"
            "train_sector    : train one sector model\n"
            "train_universal : train universal cross-sector model\n"
            "sector          : predict using sector-specific model "
            "(sector auto-detected if --sector omitted)\n"
            "universal       : predict using universal model "
            "(sector auto-detected if --sector omitted)\n"
            "list_heads      : show the multi-head model architecture "
            "(one isolated XGBoost model file per sector) and whether "
            "each head is currently trained\n"
        )
    )
    parser.add_argument('--sector', type=str, default=None,
                        help="Optional sector override: telecom/ecommerce/"
                             "banking/healthcare. If omitted in 'sector' or "
                             "'universal' mode, it is auto-detected from "
                             "the input CSV's columns.")
    parser.add_argument('--input',  type=str, default=None,
                        help="Path to new customer CSV for prediction")
    parser.add_argument('--output', type=str,
                        default='outputs/results/universal_predictions.csv')
    parser.add_argument('--tune', type=str, default=None,
                        choices=['f1', 'recall'],
                        help="Optimize training hyperparameters via "
                             "GridSearchCV for this metric instead of "
                             "fixed defaults (train_sector/train_all/"
                             "train_universal modes). Recommended for "
                             "imbalanced churn data over plain accuracy.")
    parser.add_argument('--explain', action='store_true',
                        help="Write a per-row SHAP explanation log "
                             "alongside predictions (sector/universal "
                             "modes). Requires `pip install shap`.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.mode == 'train_all':
        print("\nTraining all sector pipelines...")
        for sector in SECTOR_CONFIG:
            try:
                SectorPipeline(sector, tune_metric=args.tune).fit()
            except FileNotFoundError as e:
                print(f"  Skipping {sector}: {e}")
        train_universal_model(tune_metric=args.tune)

    elif args.mode == 'train_sector':
        if not args.sector:
            raise ValueError("--sector required for train_sector mode")
        SectorPipeline(args.sector, tune_metric=args.tune).fit()

    elif args.mode == 'train_universal':
        train_universal_model(tune_metric=args.tune)

    elif args.mode == 'sector':
        if not args.input:
            raise ValueError("--input required for sector mode")
        sector = args.sector
        if not sector:
            # fix: auto-detect sector from the input CSV's columns
            probe_df = pd.read_csv(args.input)
            sector = detect_sector(probe_df)
            print(f"  Auto-detected sector: {sector}")
        pipeline = SectorPipeline(sector).load()
        results  = pipeline.predict(args.input, explain=args.explain)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(args.output, index=False)
        print(f"\nResults saved to: {args.output}")
        print(results.to_string(index=False))

    elif args.mode == 'universal':
        if not args.input:
            raise ValueError("--input required for universal mode")
        results = predict_universal(args.input, args.sector, explain=args.explain)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(args.output, index=False)
        print(f"\nResults saved to: {args.output}")
        print(results.to_string(index=False))

    elif args.mode == 'list_heads':
        # Strategic suggestion (audit): "move to sector-specific model
        # heads / multi-task architecture". Phase A already *is* this —
        # SectorPipeline trains and persists one fully independent
        # XGBoost model file per sector (telecom_best.pkl, banking_best.pkl,
        # etc.), routed to by detect_sector(). This mode just makes that
        # architecture visible instead of leaving it implicit.
        print("\nMulti-head model architecture (one isolated head per sector):")
        print(f"{'Sector':<12} {'Model file':<55} {'Trained?'}")
        print("-" * 85)
        for sector, config in SECTOR_CONFIG.items():
            model_file = config['model_path']
            trained = "Yes" if Path(model_file).exists() else "No"
            print(f"{sector:<12} {model_file:<55} {trained}")
        print(
            "\nEach head is trained independently (--mode train_sector "
            "--sector <name>) and routed to automatically by column-"
            "signature detection (--mode sector, no --sector needed).\n"
            "The 'universal' mode (Phase B) is a separate, single shared "
            "model and is not part of this multi-head set."
        )


if __name__ == "__main__":
    main()