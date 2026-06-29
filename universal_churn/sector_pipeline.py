"""
universal_churn/sector_pipeline.py
SectorPipeline: per-sector XGBoost model (Phase A).
"""
from __future__ import annotations
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE, SMOTENC
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from xgboost import XGBClassifier
from .config import SECTOR_CONFIG, GLOBAL_CONCEPT_MAP
from .coverage import compute_coverage_score, attempt_feature_recovery
from .explainability import write_shap_log, summarize_shap_directions
from .preprocessing import sanitize_numerical_columns, derive_temporal_features
from .reporting import attach_common_metadata
from .utils import verify_prediction_variance


class SectorPipeline:
    """Train and serve a sector-specific churn model."""

    def __init__(self, sector: str, tune_metric: str | None = None) -> None:
        if sector not in SECTOR_CONFIG:
            raise ValueError(f"Unknown sector '{sector}'. "
                             f"Choose from: {list(SECTOR_CONFIG)}")
        self.sector = sector
        self.config = SECTOR_CONFIG[sector]
        self.tune_metric = tune_metric
        self.model = None
        self.scaler = StandardScaler()
        self.label_encoders: dict = {}
        self.feature_names: list[str] = []

    def _load_data(self) -> pd.DataFrame:
        path = self.config['data_path']
        if not Path(path).exists():
            raise FileNotFoundError(f"Data not found: {path}")
        return pd.read_csv(path)

    def _clean(self, df: pd.DataFrame) -> pd.DataFrame:
        drop = [c for c in self.config['drop_cols'] if c in df.columns]
        df = df.drop(columns=drop)
        if 'TotalCharges' in df.columns:
            df['TotalCharges'] = pd.to_numeric(
                df['TotalCharges'], errors='coerce').fillna(0)
        for col in df.select_dtypes(include='number').columns:
            df[col] = df[col].fillna(df[col].median())
        for col in df.select_dtypes(include=['object', 'string']).columns:
            mode = df[col].mode()
            df[col] = df[col].fillna(mode.iloc[0] if not mode.empty else '')
        return df

    def _encode(self, df: pd.DataFrame, fit: bool = True) -> pd.DataFrame:
        forced_label_cols = set(self.config.get('label_encode_cols', []))
        for col in df.select_dtypes(include=['object', 'string']).columns:
            if col in self.config.get('ohe_cols', []):
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
                            lambda x: x if x in known else le.classes_[0])
                        df[col] = le.transform(df[col])
                    else:
                        df[col] = 0
                continue
            mapped = df[col].map(self.config['binary_map'])
            if mapped.notna().all():
                df[col] = mapped
            elif col in self.config['ohe_cols']:
                pass
            else:
                if fit:
                    le = LabelEncoder()
                    df[col] = le.fit_transform(df[col].astype(str))
                    self.label_encoders[col] = le
                else:
                    if col in self.label_encoders:
                        le = self.label_encoders[col]
                        known = set(le.classes_)
                        df[col] = df[col].astype(str).apply(
                            lambda x: x if x in known else le.classes_[0])
                        df[col] = le.transform(df[col])
                    else:
                        df[col] = 0
        if self.config['ohe_cols']:
            ohe_present = [c for c in self.config['ohe_cols'] if c in df.columns]
            if ohe_present:
                df = pd.get_dummies(df, columns=ohe_present, drop_first=True)
        return df

    def _encode_target(self, series: pd.Series) -> pd.Series:
        if pd.api.types.is_numeric_dtype(series):
            return series.astype(int)
        series = series.astype(str).str.strip().map(
            {'Yes': 1, 'No': 0, 'yes': 1, 'no': 0, 'YES': 1, 'NO': 0})
        if series.isna().any():
            raise ValueError(
                f"_encode_target: {series.isna().sum()} target value(s) "
                "could not be mapped to 0/1.")
        return series.astype(int)

    def fit(self) -> 'SectorPipeline':
        print(f"\n{'='*50}\n  Training pipeline — {self.sector.upper()}\n{'='*50}")
        df = self._load_data()
        df = self._clean(df)
        target_col = self.config['target_col']
        y = self._encode_target(df[target_col])
        print("\nTarget classes:")
        print(pd.Series(y).value_counts())
        df.drop(columns=[target_col], inplace=True)
        df = self._encode(df, fit=True)
        scale_cols = [c for c in self.config['scale_cols'] if c in df.columns]
        df[scale_cols] = self.scaler.fit_transform(df[scale_cols])
        self.feature_names = df.columns.tolist()
        df = df.replace([np.inf, -np.inf], np.nan)
        if df.isna().sum().sum() > 0:
            df = df.fillna(0)
        X = df.values
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y)
        smote = SMOTE(random_state=42)
        X_train_sm, y_train_sm = smote.fit_resample(X_train, y_train)
        if self.tune_metric:
            param_grid = {'n_estimators': [100, 200, 300],
                          'max_depth': [3, 4, 6],
                          'learning_rate': [0.05, 0.1, 0.2]}
            base = XGBClassifier(random_state=42, use_label_encoder=False,
                                 eval_metric='logloss', verbosity=0)
            search = GridSearchCV(base, param_grid, scoring=self.tune_metric,
                                  cv=3, n_jobs=-1, verbose=0)
            search.fit(X_train_sm, y_train_sm)
            self.model = search.best_estimator_
        else:
            self.model = XGBClassifier(
                n_estimators=200, learning_rate=0.1, max_depth=4,
                random_state=42, use_label_encoder=False,
                eval_metric='logloss', verbosity=0)
            self.model.fit(X_train_sm, y_train_sm)
        y_pred = self.model.predict(X_test)
        y_proba = self.model.predict_proba(X_test)[:, 1]
        print(f"  Accuracy  : {accuracy_score(y_test, y_pred):.4f}")
        print(f"  ROC-AUC   : {roc_auc_score(y_test, y_proba):.4f}")
        model_path = Path(self.config['model_path'])
        scaler_path = Path(self.config['scaler_path'])
        feature_path = Path(self.config['features_path'])
        for p in (model_path, scaler_path, feature_path):
            p.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, model_path)
        joblib.dump(self.scaler, scaler_path)
        joblib.dump(self.label_encoders,
                    str(feature_path).replace('.csv', '_le.pkl'))
        pd.Series(self.feature_names).to_csv(feature_path, index=False)
        print(f"  Model saved  : {model_path}")
        return self

    def load(self) -> 'SectorPipeline':
        self.model = joblib.load(self.config['model_path'])
        self.scaler = joblib.load(self.config['scaler_path'])
        feat_path = self.config['features_path']
        le_path = feat_path.replace('.csv', '_le.pkl')
        self.feature_names = pd.read_csv(feat_path).iloc[:, 0].tolist()
        if Path(le_path).exists():
            self.label_encoders = joblib.load(le_path)
        return self

    def predict(self, input_csv: str, explain: bool = False,
                explain_output: str | None = None,
                _prediction_mode: str = 'Sector') -> pd.DataFrame:
        df_raw = pd.read_csv(input_csv)
        df_raw = sanitize_numerical_columns(df_raw)
        df_raw = derive_temporal_features(df_raw)
        coverage = compute_coverage_score(df_raw, self.sector, mode='sector')
        if coverage['prediction_mode'] == 'Refused':
            raise ValueError(
                f"Prediction refused for sector '{self.sector}': "
                f"weighted coverage {coverage['coverage_score']*100:.1f}% < 60%.")
        if coverage['prediction_mode'] == 'Fallback':
            recovered_df = attempt_feature_recovery(df_raw, self.sector)
            if recovered_df is not None:
                recovery_coverage = compute_coverage_score(
                    recovered_df, self.sector, mode='sector', _suppress_print=True)
                if recovery_coverage['prediction_mode'] == 'Full':
                    df_raw = recovered_df
                    coverage = recovery_coverage
        if coverage['prediction_mode'] == 'Fallback':
            from .universal_pipeline import predict_universal
            results = predict_universal(
                input_path=input_csv, force_sector=self.sector,
                _precomputed_coverage=coverage, _prediction_mode='Fallback')
            results.attrs['coverage'] = coverage
            results.attrs['explain_summary'] = None
            return results
        df_lower = df_raw.copy()
        df_lower.columns = (df_lower.columns.str.lower()
                            .str.replace(' ', '', regex=False)
                            .str.replace('_', '', regex=False))
        normalized_global_map = {
            k.replace('_', '').replace(' ', ''): v
            for k, v in GLOBAL_CONCEPT_MAP.items()
        }
        df_lower.rename(columns=normalized_global_map, inplace=True)
        target_cols_pool = (
            self.feature_names + self.config.get('scale_cols', [])
            + [self.config['target_col']] + self.config['drop_cols']
            + self.config.get('ohe_cols', [])
            + self.config.get('label_encode_cols', []))
        target_lower_map = {
            t.lower().replace('_', '').replace(' ', ''): t
            for t in target_cols_pool
        }
        rename_to_target = {}
        for col_idx, col_name in enumerate(df_raw.columns):
            translated_lower = df_lower.columns[col_idx]
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
        id_cols = ['customerID', 'CustomerID', 'Customer ID', 'CustomerId',
                   'RowNumber', 'PatientID', 'patientid']
        id_series = next((df_raw[c].copy() for c in df_raw.columns if c in id_cols), None)
        df = self._clean(df_mapped)
        df = self._encode(df, fit=False)
        for col in self.feature_names:
            if col not in df.columns:
                if hasattr(self.scaler, 'mean_') and col in self.config.get('scale_cols', []):
                    idx = list(self.config['scale_cols']).index(col)
                    df[col] = self.scaler.mean_[idx]
                else:
                    df[col] = 0
        df = df[self.feature_names]
        if hasattr(self.scaler, 'feature_names_in_'):
            scale_cols = [c for c in self.scaler.feature_names_in_ if c in df.columns]
        else:
            scale_cols = [c for c in self.config['scale_cols'] if c in df.columns]
        if scale_cols:
            df[scale_cols] = self.scaler.transform(df[scale_cols])
        X = df.values
        preds = self.model.predict(X)
        probas = self.model.predict_proba(X)[:, 1]
        verify_prediction_variance(probas)
        results = pd.DataFrame()
        results['CustomerID'] = (id_series.values if id_series is not None
                                 else [f"UNK_{i}" for i in range(len(df))])
        results['Predicted_Churn'] = pd.Series(preds).map({0: 'No', 1: 'Yes'})
        results['Churn_Probability'] = probas.round(4)
        results['Risk_Level'] = np.select(
            [probas >= 0.70, probas >= 0.40], ['High', 'Medium'], default='Low')
        results['Prediction_Model'] = 'Sector XGBoost'
        results['Prediction_Mode'] = _prediction_mode
        results['Coverage_Score'] = f"{coverage['coverage_score']*100:.1f}%"
        results['Coverage_Status'] = coverage['status']
        results = attach_common_metadata(results, coverage, 'Sector XGBoost')
        explain_summary = None
        if explain:
            id_col = results['CustomerID'].values
            log_path = explain_output or f"outputs/shap_logs/{self.sector}_shap_log.csv"
            write_shap_log(self.model, df, self.feature_names, id_col, log_path)
            explain_summary = summarize_shap_directions(self.model, df, self.feature_names)
        results.attrs['explain_summary'] = explain_summary
        results.attrs['coverage'] = coverage
        return results