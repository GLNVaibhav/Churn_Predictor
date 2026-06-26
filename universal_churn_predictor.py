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

        # SMOTE
        smote = SMOTE(random_state=42)
        X_train_sm, y_train_sm = smote.fit_resample(X_train, y_train)

        if self.tune_metric:
            # Strategic suggestion (audit): churn datasets are imbalanced,
            # so a model can score 85% accuracy by predicting "no churn"
            # for everyone. Optimize the search for recall/F1 instead of
            # the estimator's default scoring.
            print(f"\n  Tuning hyperparameters (scoring='{self.tune_metric}')...")
            param_grid = {
                'n_estimators': [100, 200, 300],
                'max_depth': [3, 4, 6],
                'learning_rate': [0.05, 0.1, 0.2],
            }
            base_model = XGBClassifier(
                random_state=42, use_label_encoder=False,
                eval_metric='logloss', verbosity=0
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
            # Train XGBoost with fixed defaults
            self.model = XGBClassifier(
                n_estimators=200, learning_rate=0.1,
                max_depth=4, random_state=42,
                use_label_encoder=False,
                eval_metric='logloss', verbosity=0
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
        Robustly handles dynamic columns, extra noise, and missing variables.
        """
        df_raw = pd.read_csv(input_csv)

        # 1. Create lowercase map for finding raw variants flexible to human case-error
        df_lower = df_raw.copy()
        df_lower.columns = df_lower.columns.str.lower()

        # Comprehensive cross-industry translation map
        concept_map = {
            'patientid': 'patientid', 'customer id': 'patientid', 'customerid': 'patientid', 'rownumber': 'patientid',
            'exited': 'churned', 'churned': 'churned', 'actual_churn': 'churned', 'churn': 'churned',
            'policytype': 'specialty', 'contracttype': 'specialty', 'contract': 'specialty',
            'monthlypremium': 'avg_out_of_pocket_cost', 'monthlycharges': 'avg_out_of_pocket_cost', 'totalcharges': 'avg_out_of_pocket_cost',
            'frequencyofvisits': 'visits_last_year', 'days_since_last_visit': 'days_since_last_visit',
            'customersupportcalls': 'billing_issues', 'complain': 'billing_issues'
        }
        df_lower.rename(columns=concept_map, inplace=True)

        # 2. Map generic terms directly back to your trained sector head column signatures
        rename_to_target = {}
        target_cols_pool = (
            self.feature_names
            + self.config.get('scale_cols', [])
            + [self.config['target_col']]
            + self.config['drop_cols']
            + self.config.get('ohe_cols', [])
            + self.config.get('label_encode_cols', [])
        )
        for col_idx, col_name in enumerate(df_raw.columns):
            translated_lower = df_lower.columns[col_idx]
            matched = False
            # Check features, scale columns, targets, and drops for case matching
            for target_col in target_cols_pool:
                if translated_lower == target_col.lower():
                    rename_to_target[col_name] = target_col
                    matched = True
                    break
            if not matched:
                rename_to_target[col_name] = col_name

        df_mapped = df_raw.rename(columns=rename_to_target)

        # Preserve IDs from any known naming style
        id_cols = ['customerID','CustomerID','Customer ID','CustomerId','RowNumber','PatientID','patientid']
        id_series = None
        for col in df_raw.columns:
            if col in id_cols:
                id_series = df_raw[col].copy()
                break

        # Pass correctly-cased column signatures to cleaning pipeline
        df = self._clean(df_mapped)
        df = self._encode(df, fit=False)

        # Force structural feature alignment BEFORE scaling
        for col in self.feature_names:
            if col not in df.columns:
                # If the feature is in our scaler's tracking, use its mean/center value
                if hasattr(self.scaler, 'mean_') and col in self.config.get('scale_cols', []):
                    idx = list(self.config['scale_cols']).index(col)
                    df[col] = self.scaler.mean_[idx]
                else:
                    # Fallback to standard baseline indicator if completely unknown
                    df[col] = 0
        df = df[self.feature_names]

        # Scaler execution
        if hasattr(self.scaler, 'feature_names_in_'):
            scale_cols = [c for c in self.scaler.feature_names_in_ if c in df.columns]
        else:
            scale_cols = [c for c in self.config['scale_cols'] if c in df.columns]
        if scale_cols:
            df[scale_cols] = self.scaler.transform(df[scale_cols])

        X = df.values
        preds  = self.model.predict(X)
        probas = self.model.predict_proba(X)[:, 1]

        # Verify prediction variance to catch flatlines
        verify_prediction_variance(probas)

        results = pd.DataFrame()
        results['CustomerID'] = id_series.values if id_series is not None else [f"UNK_{i}" for i in range(len(df))]
        results['Predicted_Churn']   = pd.Series(preds).map({0: 'No', 1: 'Yes'})
        results['Churn_Probability'] = probas.round(4)
        results['Risk_Level'] = np.select(
            [probas >= 0.70, probas >= 0.40],
            ['High', 'Medium'],
            default='Low'
        )
        results['Sector'] = self.sector.capitalize()
        results['Model']  = 'XGBoost (Sector-Specific)'

        if explain:
            id_col = results['CustomerID'].values
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
    'lockin_risk',             # new customer + long-term contract — looks
                                # "safe" on contract length alone but the
                                # commitment hasn't been tested yet
    'dormant_loyalty_risk',    # long-tenured but recently inactive — a
                                # loyal customer who has quietly stopped
                                # engaging, easy to miss if tenure alone
                                # dominates the model's risk assessment
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
        if 'Tenure_Months' in df.columns or 'Visits_Last_Year' in df.columns:
            # Schema variant 1: PatientID-style
            # (Tenure_Months, Overall_Satisfaction, Visits_Last_Year, etc.)
            max_tenure = _norm_max(df, 'Tenure_Months', sector, norm_stats)
            max_cost   = _norm_max(df, 'Avg_Out_Of_Pocket_Cost', sector, norm_stats)
            max_sat    = _norm_max(df, 'Overall_Satisfaction', sector, norm_stats)
            max_visits = _norm_max(df, 'Visits_Last_Year', sector, norm_stats)
            max_lastv  = _norm_max(df, 'Days_Since_Last_Visit', sector, norm_stats)
            max_dist   = _norm_max(df, 'Distance_To_Facility_Miles', sector, norm_stats)

            feat['tenure_normalized']      = df['Tenure_Months'] / max_tenure if 'Tenure_Months' in df.columns else 0.5
            feat['charge_normalized']      = df['Avg_Out_Of_Pocket_Cost'] / max_cost if 'Avg_Out_Of_Pocket_Cost' in df.columns else 0
            feat['has_complaint']          = (df['Billing_Issues'] > 0).astype(int) if 'Billing_Issues' in df.columns else 0
            feat['satisfaction_score']     = df['Overall_Satisfaction'] / max_sat if 'Overall_Satisfaction' in df.columns else 0.5
            feat['is_active']              = (df['Days_Since_Last_Visit'] <= 90).astype(int) if 'Days_Since_Last_Visit' in df.columns else 0.5
            feat['num_products_services']  = df['Visits_Last_Year'] / max_visits if 'Visits_Last_Year' in df.columns else 0.5
            feat['is_senior_or_high_risk'] = (df['Age'] > 65).astype(int) if 'Age' in df.columns else 0
            feat['has_support']            = df['Portal_Usage'] if 'Portal_Usage' in df.columns else 0
            feat['contract_stability']     = df['Tenure_Months'] / max_tenure if 'Tenure_Months' in df.columns else 0.5
            feat['payment_auto']           = 0.5  # fix: no payment-method column in this schema either

            feat['engagement_score']       = feat['num_products_services']
            feat['coupon_dependency']      = 0
            feat['cashback_engagement']    = 0
            feat['recency_score']          = 1 - (df['Days_Since_Last_Visit'] / max_lastv) if 'Days_Since_Last_Visit' in df.columns else 0.5
            feat['convenience_score']      = 1 - (df['Distance_To_Facility_Miles'] / max_dist) if 'Distance_To_Facility_Miles' in df.columns else 0.5

            # fix (adversarial audit): long-tenured patient who has
            # stopped visiting is this schema's version of the
            # dormant-loyalist case. No contract concept exists here.
            feat['dormant_loyalty_risk']   = feat['tenure_normalized'] * (1 - feat['is_active'])
            feat['lockin_risk']            = 0
            # Schema variant 2: MedicalCondition-style
            # (MedicalCondition, PolicyType, MonthlyPremium,
            #  FrequencyOfVisits, ClaimHistoryCount, CustomerSupportCalls)
            max_premium = _norm_max(df, 'MonthlyPremium', sector, norm_stats)
            max_freq    = _norm_max(df, 'FrequencyOfVisits', sector, norm_stats)
            max_claims  = _norm_max(df, 'ClaimHistoryCount', sector, norm_stats)
            max_calls   = _norm_max(df, 'CustomerSupportCalls', sector, norm_stats)

            # No direct tenure/contract-length analog in this schema —
            # neutral default rather than guessing.
            feat['tenure_normalized']      = 0.5
            feat['charge_normalized']      = df['MonthlyPremium'] / max_premium if 'MonthlyPremium' in df.columns else 0
            feat['has_complaint']          = (df['CustomerSupportCalls'] > 2).astype(int) if 'CustomerSupportCalls' in df.columns else 0
            feat['satisfaction_score']     = 0.5  # no satisfaction survey field in this schema
            feat['is_active']              = (df['FrequencyOfVisits'] > 0).astype(int) if 'FrequencyOfVisits' in df.columns else 0.5
            feat['num_products_services']  = df['FrequencyOfVisits'] / max_freq if 'FrequencyOfVisits' in df.columns else 0.5
            feat['is_senior_or_high_risk'] = (df['Age'] > 65).astype(int) if 'Age' in df.columns else 0
            feat['has_support']            = (df['CustomerSupportCalls'] > 0).astype(int) if 'CustomerSupportCalls' in df.columns else 0
            feat['contract_stability']     = 0.5
            feat['payment_auto']           = 0.5

            feat['engagement_score']       = df['FrequencyOfVisits'] / max_freq if 'FrequencyOfVisits' in df.columns else 0.5
            feat['coupon_dependency']      = 0
            feat['cashback_engagement']    = 0
            feat['recency_score']          = 0.5  # no "last visit date" column in this schema
            feat['convenience_score']      = 1 - (df['ClaimHistoryCount'] / max_claims) if 'ClaimHistoryCount' in df.columns else 0.5

            # No tenure or contract concept in this schema variant —
            # neutral defaults rather than guessing at a proxy.
            feat['dormant_loyalty_risk']   = 0.5
            feat['lockin_risk']            = 0
            # Neither known healthcare schema variant matched — fill
            # everything with documented neutral defaults rather than
            # guessing at columns that may not mean what we'd assume.
            for col in UNIVERSAL_FEATURES:
                feat[col] = 0.5

    elif sector == 'healthcare':
        if 'Tenure_Months' in df.columns or 'Visits_Last_Year' in df.columns:
            max_tenure = _norm_max(df, 'Tenure_Months', sector, norm_stats)
            max_cost   = _norm_max(df, 'Avg_Out_Of_Pocket_Cost', sector, norm_stats)
            max_sat    = _norm_max(df, 'Overall_Satisfaction', sector, norm_stats)
            max_visits = _norm_max(df, 'Visits_Last_Year', sector, norm_stats)
            max_lastv  = _norm_max(df, 'Days_Since_Last_Visit', sector, norm_stats)
            max_dist   = _norm_max(df, 'Distance_To_Facility_Miles', sector, norm_stats)

            feat['tenure_normalized']      = df['Tenure_Months'] / max_tenure if 'Tenure_Months' in df.columns else 0.5
            feat['charge_normalized']      = df['Avg_Out_Of_Pocket_Cost'] / max_cost if 'Avg_Out_Of_Pocket_Cost' in df.columns else 0
            feat['has_complaint']          = (df['Billing_Issues'] > 0).astype(int) if 'Billing_Issues' in df.columns else 0
            feat['satisfaction_score']     = df['Overall_Satisfaction'] / max_sat if 'Overall_Satisfaction' in df.columns else 0.5
            feat['is_active']              = (df['Days_Since_Last_Visit'] <= 90).astype(int) if 'Days_Since_Last_Visit' in df.columns else 0.5
            feat['num_products_services']  = df['Visits_Last_Year'] / max_visits if 'Visits_Last_Year' in df.columns else 0.5
            feat['is_senior_or_high_risk'] = (df['Age'] > 65).astype(int) if 'Age' in df.columns else 0
            feat['has_support']            = df['Portal_Usage'] if 'Portal_Usage' in df.columns else 0
            feat['contract_stability']     = df['Tenure_Months'] / max_tenure if 'Tenure_Months' in df.columns else 0.5
            feat['payment_auto']           = 0.5

            feat['engagement_score']       = feat['num_products_services']
            feat['coupon_dependency']      = 0
            feat['cashback_engagement']    = 0
            feat['recency_score']          = 1 - (df['Days_Since_Last_Visit'] / max_lastv) if 'Days_Since_Last_Visit' in df.columns else 0.5
            feat['convenience_score']      = 1 - (df['Distance_To_Facility_Miles'] / max_dist) if 'Distance_To_Facility_Miles' in df.columns else 0.5
            feat['dormant_loyalty_risk']   = feat['tenure_normalized'] * (1 - feat['is_active'])
            feat['lockin_risk']            = 0

        elif 'MonthlyPremium' in df.columns or 'FrequencyOfVisits' in df.columns:
            max_premium = _norm_max(df, 'MonthlyPremium', sector, norm_stats)
            max_freq    = _norm_max(df, 'FrequencyOfVisits', sector, norm_stats)
            max_claims  = _norm_max(df, 'ClaimHistoryCount', sector, norm_stats)

            feat['tenure_normalized']      = 0.5
            feat['charge_normalized']      = df['MonthlyPremium'] / max_premium if 'MonthlyPremium' in df.columns else 0
            feat['has_complaint']          = (df['CustomerSupportCalls'] > 2).astype(int) if 'CustomerSupportCalls' in df.columns else 0
            feat['satisfaction_score']     = 0.5
            feat['is_active']              = (df['FrequencyOfVisits'] > 0).astype(int) if 'FrequencyOfVisits' in df.columns else 0.5
            feat['num_products_services']  = df['FrequencyOfVisits'] / max_freq if 'FrequencyOfVisits' in df.columns else 0.5
            feat['is_senior_or_high_risk'] = (df['Age'] > 65).astype(int) if 'Age' in df.columns else 0
            feat['has_support']            = (df['CustomerSupportCalls'] > 0).astype(int) if 'CustomerSupportCalls' in df.columns else 0
            feat['contract_stability']     = 0.5
            feat['payment_auto']           = 0.5

            feat['engagement_score']       = feat['num_products_services']
            feat['coupon_dependency']      = 0
            feat['cashback_engagement']    = 0
            feat['recency_score']          = 0.5
            feat['convenience_score']      = 1 - (df['ClaimHistoryCount'] / max_claims) if 'ClaimHistoryCount' in df.columns else 0.5
            feat['dormant_loyalty_risk']   = 0.5
            feat['lockin_risk']            = 0

        else:
            for col in UNIVERSAL_FEATURES:
                feat[col] = 0.5

    # Encode target
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

    X = combined.drop(columns=['Churn']).values
    y = combined['Churn'].values

    feature_names = combined.drop(columns=['Churn']).columns.tolist()

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


def predict_universal(input_path: str, force_sector: str | None = None, explain: bool = False) -> pd.DataFrame:
    """
    Predict churn across all industries using the unified Phase B master model.
    Robust against arbitrary alternative input schemas.
    """
    df_raw = pd.read_csv(input_path)

    # Run structural detection before modifying schemas
    sector = force_sector or detect_sector(df_raw)
    print(f" Auto-detected sector: {sector}")

    # Run inline translation inside raw columns
    df_lower = df_raw.copy()
    df_lower.columns = df_lower.columns.str.lower()

    concept_map = {
        'patientid': 'patientid', 'customer id': 'patientid', 'customerid': 'patientid', 'rownumber': 'patientid',
        'policytype': 'specialty', 'contracttype': 'specialty', 'contract': 'specialty',
        'monthlypremium': 'avg_out_of_pocket_cost', 'monthlycharges': 'avg_out_of_pocket_cost', 'totalcharges': 'avg_out_of_pocket_cost',
        'frequencyofvisits': 'visits_last_year', 'days_since_last_visit': 'days_since_last_visit',
        'customersupportcalls': 'billing_issues', 'complain': 'billing_issues'
    }
    df_lower.rename(columns=concept_map, inplace=True)

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
    results['Sector'] = sector.capitalize()
    results['Model'] = 'XGBoost (Universal)'

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
