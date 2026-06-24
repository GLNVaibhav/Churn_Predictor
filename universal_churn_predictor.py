"""
universal_churn_predictor.py
=============================
Schema-agnostic churn prediction system.

Phase A: Routes any CSV to the correct sector model automatically
         (sector is now AUTO-DETECTED from column signatures — no
         --sector flag needed for prediction)
Phase B: Universal cross-sector model predicts from any input

Usage:
    # Phase A - auto-route to sector model (sector auto-detected)
    python universal_churn_predictor.py --mode sector --input new_customers.csv

    # Phase A - force a specific sector (optional override)
    python universal_churn_predictor.py --mode sector --input new_customers.csv --sector telecom

    # Phase B - universal model prediction (sector still auto-detected
    # internally so the universal feature-mapper knows which columns mean what)
    python universal_churn_predictor.py --mode universal --input new_customers.csv

    # Train universal model first
    python universal_churn_predictor.py --mode train_universal


RESEARCH / LIMITATIONS NOTE
----------------------------
The "universal" cross-sector model (Phase B) works by hand-mapping each
sector's raw columns onto 10 common features (see UNIVERSAL_FEATURES and
extract_universal_features()). This mapping is a SUBJECTIVE MODELING
CHOICE, not a learned or statistically validated transformation:

  * e.g. "satisfaction_score" is approximated from CreditScore for
    banking and from an explicit survey field for e-commerce — these
    are not measuring the same underlying construct.
  * "is_senior_or_high_risk" mixes age, BMI, and (implicitly) nothing
    for sectors with no obvious analogue, defaulting to 0.
  * Several features are sector-specific placeholders (e.g.
    contract_stability = 0 for ecommerce/healthcare) because no
    directly comparable field exists in that schema.

These choices were made to keep the feature space small and tractable,
but they introduce construct-validity risk: the universal model may be
learning patterns driven by how a feature was *approximated* for a
sector rather than genuine cross-sector churn behavior. Anyone using
Phase B for decisions beyond an internal proof-of-concept should treat
the universal feature engineering as a documented assumption requiring
domain review, not a ground truth.
"""

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
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from imblearn.over_sampling import SMOTE

try:
    from xgboost import XGBClassifier
except ImportError as exc:
    raise ImportError("xgboost is required.") from exc

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
# SECTOR AUTO-DETECTION (fix: removes the --sector requirement)
# ══════════════════════════════════════════════════════════════════

# Columns that are distinctive enough to identify a sector on sight.
# Each sector needs at least MIN_SIGNATURE_HITS of its signature columns
# present (case-insensitive, whitespace-insensitive match) to be selected.
SECTOR_SIGNATURES = {
    'telecom': {
        'monthlycharges', 'totalcharges', 'contract', 'internetservice',
        'phoneservice', 'multiplelines', 'streamingtv',
    },
    'ecommerce': {
        'cashbackamount', 'daysincelastorder', 'couponused', 'ordercount',
        'warehousetohome', 'hourspendonapp', 'preferredpaymentmode',
    },
    'banking': {
        'rownumber', 'surname', 'creditscore', 'geography',
        'numofproducts', 'hascrcard', 'isactivemember',
        'estimatedsalary', 'exited',
    },
    'healthcare': {
        'patientid', 'specialty', 'insurancetype', 'visitslastyear',
        'missedappointments', 'overallsatisfaction',
        'waittimesatisfaction', 'staffsatisfaction', 'providerrating',
        'avgoutofpocketcost', 'billingissues', 'portalusage',
        'referralsmade', 'distancetofacilitymiles', 'churned',
    },
}
MIN_SIGNATURE_HITS = 2


def detect_sector(df: pd.DataFrame) -> str:
    """
    Inspect a DataFrame's column names and return the best-matching
    sector key from SECTOR_CONFIG. Raises ValueError if no sector
    scores at least MIN_SIGNATURE_HITS matches, or if there's an
    ambiguous tie at the top score.
    """
    normalized_cols = {c.strip().lower().replace(' ', '').replace('_', '')
                        for c in df.columns}

    scores = {}
    for sector, signature in SECTOR_SIGNATURES.items():
        sig_normalized = {s.replace(' ', '').replace('_', '') for s in signature}
        scores[sector] = len(normalized_cols & sig_normalized)

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

    def __init__(self, sector: str):
        if sector not in SECTOR_CONFIG:
            raise ValueError(
                f"Unknown sector '{sector}'. "
                f"Choose from: {list(SECTOR_CONFIG.keys())}"
            )
        self.sector = sector
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

        # Train XGBoost as universal best
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

    def predict(self, input_csv: str) -> pd.DataFrame:
        """
        Predict churn for any CSV matching this sector's schema.
        Handles missing columns, extra columns, and unknown categories.
        """
        df_raw = pd.read_csv(input_csv)

        # Preserve IDs
        id_cols = ['customerID','CustomerID','Customer ID',
                   'CustomerId','RowNumber','PatientID']
        id_series = None
        for col in id_cols:
            if col in df_raw.columns:
                id_series = df_raw[col].copy()
                df_raw.drop(columns=[col], inplace=True)
                break

        # Drop target if present
        target = self.config['target_col']
        if target in df_raw.columns:
            df_raw.drop(columns=[target], inplace=True)

        # Drop expected churn label if present
        if 'Expected_Churn' in df_raw.columns:
            df_raw.drop(columns=['Expected_Churn'], inplace=True)

        df = self._clean(df_raw.copy())
        df = self._encode(df, fit=False)

        # Scale
        scale_cols = [
            c for c in self.config['scale_cols']
            if c in df.columns
        ]
        df[scale_cols] = self.scaler.transform(df[scale_cols])

        # Align to training features
        for col in self.feature_names:
            if col not in df.columns:
                df[col] = 0
        df = df[self.feature_names]

        X = df.values
        preds  = self.model.predict(X)
        probas = self.model.predict_proba(X)[:, 1]

        results = pd.DataFrame()
        if id_series is not None:
            results['CustomerID'] = id_series.values
        results['Predicted_Churn']   = pd.Series(preds).map({0: 'No', 1: 'Yes'})
        results['Churn_Probability'] = probas.round(4)
        results['Risk_Level'] = np.select(
            [probas >= 0.70, probas >= 0.40],
            ['High', 'Medium'],
            default='Low'
        )
        results['Sector'] = self.sector.capitalize()
        results['Model']  = 'XGBoost (Sector-Specific)'

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
]


def extract_universal_features(
    df: pd.DataFrame,
    sector: str,
    target_col: str
) -> pd.DataFrame:
    """
    Extract 10 universal features from any sector's dataset.
    Maps sector-specific columns to a common feature space.

    LIMITATION: these mappings are best-effort analogues chosen by the
    author, not features validated to measure the same underlying
    construct across sectors (see module docstring). Treat cross-sector
    comparisons made from these features as directional, not precise.
    """
    feat = pd.DataFrame(index=df.index)

    if sector == 'telecom':
        max_tenure = df['tenure'].max() if 'tenure' in df.columns else 1
        feat['tenure_normalized']      = df['tenure'] / max_tenure if 'tenure' in df.columns else 0
        feat['charge_normalized']      = df['MonthlyCharges'] / df['MonthlyCharges'].max() if 'MonthlyCharges' in df.columns else 0
        feat['has_complaint']          = 0
        feat['satisfaction_score']     = 0.5
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

    elif sector == 'ecommerce':
        max_tenure = df['Tenure'].max() if 'Tenure' in df.columns else 1
        feat['tenure_normalized']      = df['Tenure'] / max_tenure if 'Tenure' in df.columns else 0
        feat['charge_normalized']      = df['CashbackAmount'] / df['CashbackAmount'].max() if 'CashbackAmount' in df.columns else 0
        feat['has_complaint']          = df['Complain'] if 'Complain' in df.columns else 0
        feat['satisfaction_score']     = df['SatisfactionScore'] / 5.0 if 'SatisfactionScore' in df.columns else 0.5
        feat['is_active']              = (df['DaySinceLastOrder'] <= 7).astype(int) if 'DaySinceLastOrder' in df.columns else 0.5
        feat['num_products_services']  = df['OrderCount'] / df['OrderCount'].max() if 'OrderCount' in df.columns else 0
        feat['is_senior_or_high_risk'] = 0
        feat['has_support']            = 0
        feat['contract_stability']     = 0
        feat['payment_auto']           = df['PreferredPaymentMode'].isin(
            ['Credit Card','Debit Card','UPI']
        ).astype(int) if 'PreferredPaymentMode' in df.columns else 0

    elif sector == 'banking':
        max_tenure = df['Tenure'].max() if 'Tenure' in df.columns else 1
        feat['tenure_normalized']      = df['Tenure'] / max_tenure if 'Tenure' in df.columns else 0
        feat['charge_normalized']      = df['Balance'] / df['Balance'].max() if 'Balance' in df.columns else 0
        feat['has_complaint']          = 0
        feat['satisfaction_score']     = df['CreditScore'] / df['CreditScore'].max() if 'CreditScore' in df.columns else 0.5
        feat['is_active']              = df['IsActiveMember'] if 'IsActiveMember' in df.columns else 0.5
        feat['num_products_services']  = df['NumOfProducts'] / 4.0 if 'NumOfProducts' in df.columns else 0
        feat['is_senior_or_high_risk'] = (df['Age'] > 55).astype(int) if 'Age' in df.columns else 0
        feat['has_support']            = df['HasCrCard'] if 'HasCrCard' in df.columns else 0
        feat['contract_stability']     = df['Tenure'] / max_tenure if 'Tenure' in df.columns else 0
        feat['payment_auto']           = 1

    elif sector == 'healthcare':
        # fix v2: mapped to the ACTUAL healthcare column names
        # (Tenure_Months, Overall_Satisfaction, Visits_Last_Year, etc.)
        feat['tenure_normalized']      = df['Tenure_Months'] / df['Tenure_Months'].max() if 'Tenure_Months' in df.columns else 0.5
        feat['charge_normalized']      = df['Avg_Out_Of_Pocket_Cost'] / df['Avg_Out_Of_Pocket_Cost'].max() if 'Avg_Out_Of_Pocket_Cost' in df.columns else 0
        feat['has_complaint']          = (df['Billing_Issues'] > 0).astype(int) if 'Billing_Issues' in df.columns else 0
        feat['satisfaction_score']     = df['Overall_Satisfaction'] / df['Overall_Satisfaction'].max() if 'Overall_Satisfaction' in df.columns else 0.5
        feat['is_active']              = (df['Days_Since_Last_Visit'] <= 90).astype(int) if 'Days_Since_Last_Visit' in df.columns else 0.5
        feat['num_products_services']  = df['Visits_Last_Year'] / df['Visits_Last_Year'].max() if 'Visits_Last_Year' in df.columns else 0.5
        feat['is_senior_or_high_risk'] = (df['Age'] > 65).astype(int) if 'Age' in df.columns else 0
        feat['has_support']            = df['Portal_Usage'] if 'Portal_Usage' in df.columns else 0
        feat['contract_stability']     = df['Tenure_Months'] / df['Tenure_Months'].max() if 'Tenure_Months' in df.columns else 0.5
        feat['payment_auto']           = 0

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


def train_universal_model() -> None:
    """
    Phase B: Merge all 4 sectors into universal feature space
    and train one XGBoost model on everything.
    """
    print("\n" + "="*55)
    print("  PHASE B — Training Universal Cross-Sector Model")
    print("="*55)

    all_data = []

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

        feat_df = extract_universal_features(
            df, sector, config['target_col']
        )
        all_data.append(feat_df)
        print(f"  {sector}: {len(feat_df)} rows extracted")

    if not all_data:
        raise RuntimeError("No sector data found. Check data paths.")

    combined = pd.concat(all_data, ignore_index=True)
    print(f"\n  Combined dataset: {combined.shape[0]} rows")
    print(f"  Churn rate      : {combined['Churn'].mean()*100:.1f}%")

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
    pd.Series(feature_names).to_csv(UNIVERSAL_FEATURES_PATH, index=False)

    print(f"  Universal model saved : {UNIVERSAL_MODEL_PATH}")
    print(f"  Universal scaler saved: {UNIVERSAL_SCALER_PATH}")


def predict_universal(input_csv: str, sector: str | None = None) -> pd.DataFrame:
    """
    Phase B prediction: use universal model on any new input.
    `sector` is now optional — if not provided, it is auto-detected
    from the input CSV's column signature (fix: removes the
    requirement to pass --sector for universal mode too).
    """
    if not UNIVERSAL_MODEL_PATH.exists():
        raise FileNotFoundError(
            "Universal model not found. "
            "Run: python universal_churn_predictor.py --mode train_universal"
        )

    model      = joblib.load(UNIVERSAL_MODEL_PATH)
    scaler     = joblib.load(UNIVERSAL_SCALER_PATH)
    le_sector  = joblib.load(str(UNIVERSAL_MODEL_PATH).replace('.pkl','_le_sector.pkl'))
    feat_names = pd.read_csv(UNIVERSAL_FEATURES_PATH).iloc[:, 0].tolist()

    df = pd.read_csv(input_csv)

    if sector is None:
        sector = detect_sector(df)
        print(f"  Auto-detected sector: {sector}")

    # Preserve IDs
    id_cols = ['customerID','CustomerID','Customer ID','CustomerId','RowNumber','PatientID']
    id_series = None
    for col in id_cols:
        if col in df.columns:
            id_series = df[col].copy()
            df.drop(columns=[col], inplace=True)
            break

    # Drop known non-feature columns
    drop_cols = ['Expected_Churn', 'Churn', 'Exited', 'Churned']
    df.drop(columns=[c for c in drop_cols if c in df.columns],
            inplace=True)

    # Fix TotalCharges
    if 'TotalCharges' in df.columns:
        df['TotalCharges'] = pd.to_numeric(
            df['TotalCharges'], errors='coerce'
        ).fillna(0)

    # Fill nulls
    for col in df.select_dtypes(include='number').columns:
        df[col] = df[col].fillna(df[col].median())
    for col in df.select_dtypes(include=['object', 'string']).columns:
        df[col] = df[col].fillna(df[col].mode()[0])

    # Create dummy target for feature extraction
    df['__target__'] = 0
    feat_df = extract_universal_features(df, sector, '__target__')
    feat_df.drop(columns=['Churn'], inplace=True)

    # Encode sector
    try:
        feat_df['Sector_Encoded'] = le_sector.transform([sector])[0]
    except Exception:
        feat_df['Sector_Encoded'] = 0

    feat_df.drop(columns=['Sector'], errors='ignore', inplace=True)

    # Align to training features
    for col in feat_names:
        if col not in feat_df.columns:
            feat_df[col] = 0
    feat_df = feat_df[feat_names]

    X = scaler.transform(feat_df.values)
    preds  = model.predict(X)
    probas = model.predict_proba(X)[:, 1]

    results = pd.DataFrame()
    if id_series is not None:
        results['CustomerID'] = id_series.values
    results['Predicted_Churn']   = pd.Series(preds).map({0: 'No', 1: 'Yes'})
    results['Churn_Probability'] = probas.round(4)
    results['Risk_Level'] = np.select(
        [probas >= 0.70, probas >= 0.40],
        ['High', 'Medium'],
        default='Low'
    )
    results['Sector'] = sector.capitalize()
    results['Model']  = 'XGBoost (Universal)'

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
                 'sector', 'universal', 'train_all'],
        default='train_all',
        help=(
            "train_all       : train all sector models + universal model\n"
            "train_sector    : train one sector model\n"
            "train_universal : train universal cross-sector model\n"
            "sector          : predict using sector-specific model "
            "(sector auto-detected if --sector omitted)\n"
            "universal       : predict using universal model "
            "(sector auto-detected if --sector omitted)\n"
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.mode == 'train_all':
        print("\nTraining all sector pipelines...")
        for sector in SECTOR_CONFIG:
            try:
                SectorPipeline(sector).fit()
            except FileNotFoundError as e:
                print(f"  Skipping {sector}: {e}")
        train_universal_model()

    elif args.mode == 'train_sector':
        if not args.sector:
            raise ValueError("--sector required for train_sector mode")
        SectorPipeline(args.sector).fit()

    elif args.mode == 'train_universal':
        train_universal_model()

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
        results  = pipeline.predict(args.input)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(args.output, index=False)
        print(f"\nResults saved to: {args.output}")
        print(results.to_string(index=False))

    elif args.mode == 'universal':
        if not args.input:
            raise ValueError("--input required for universal mode")
        results = predict_universal(args.input, args.sector)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(args.output, index=False)
        print(f"\nResults saved to: {args.output}")
        print(results.to_string(index=False))


if __name__ == "__main__":
    main()