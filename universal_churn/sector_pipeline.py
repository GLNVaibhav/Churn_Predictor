"""
universal_churn/sector_pipeline.py
SectorPipeline: per-sector XGBoost model (Phase A).

Routing note
------------
This module no longer decides which model to use. predict() computes
CoverageResult and QualityResult inputs, calls routing.route() exactly
once, and then executes whatever RoutingDecision says. Feature recovery
(attempt_feature_recovery) still happens here — it is a preprocessing/
feature-engineering concern, not a routing decision, and the router
only ever sees the FINAL, post-recovery coverage result.
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
from .coverage import CoverageResult
from .quality_gate import run_quality_gate
from .routing import RoutingDecision
from .intelligence_pipeline import infer_intelligence
from .explainability import write_shap_log, summarize_shap_directions
from .preprocessing import (
    sanitize_numerical_columns, derive_temporal_features,
    normalize_target, validate_target_types,
)
from .reporting import attach_common_metadata
from .utils import verify_prediction_variance
from .udif import active_run


def _print_telecom_pre_prediction_diagnostics(
    frame: pd.DataFrame,
    *,
    default_features: list[str],
    raw_feature_sources: dict[str, list[str]],
    canonical_by_raw_column: dict[str, str],
) -> None:
    """Emit observational TelecomPipeline diagnostics immediately before scoring.

    This function intentionally receives the already prepared model frame and
    never returns a value.  It is diagnostic-only: it cannot alter feature
    ordering, values, defaults, scaling, or the prediction path.
    """
    numeric = frame.select_dtypes(include=[np.number])
    variance = numeric.var(ddof=0).replace([np.inf, -np.inf], np.nan)
    constants = [str(column) for column in frame.columns if frame[column].nunique(dropna=False) <= 1]
    near_constants = [
        str(column) for column, value in variance.items()
        if column not in constants and pd.notna(value) and float(value) < 1e-8
    ]
    missing_values = int(frame.isna().sum().sum())
    provenance_rows = []
    canonical_features = []
    for feature in frame.columns:
        sources = raw_feature_sources.get(str(feature), [])
        concepts = [canonical_by_raw_column[source] for source in sources if source in canonical_by_raw_column]
        status = "default" if feature in default_features else "source"
        if concepts:
            canonical_features.append(str(feature))
        provenance_rows.append({
            "feature": str(feature),
            "status": status,
            "source_columns": ", ".join(sources) or "—",
            "canonical_concepts": ", ".join(dict.fromkeys(concepts)) or "—",
        })

    print("\n[TelecomPipeline pre-prediction diagnostics]")
    print(f"Final dataframe shape: {frame.shape}")
    print("Final feature names: " + ", ".join(map(str, frame.columns)))
    print(f"Constant feature count: {len(constants)}")
    print(f"Near-constant feature count: {len(near_constants)}")
    print(f"Missing value count: {missing_values}")
    print(f"Missing required feature count before defaults: {len(default_features)}")
    print("Features filled by defaults: " + (", ".join(default_features) or "None"))
    # The sector model's established preparation path is source-header based;
    # canonical concepts are not consumed to populate this dataframe.  Keep
    # that distinction explicit so diagnostics do not imply a behavior change.
    print("Features resolved from canonical concepts: 0 (not used by SectorPipeline preparation)")
    print(f"Features with semantic canonical provenance (observational): {len(canonical_features)}")
    print("Semantic-canonical provenance features: " + (", ".join(canonical_features) or "None"))
    print("Feature variance table:")
    print(pd.DataFrame({"feature": variance.index.astype(str), "variance": variance.values}).to_string(index=False))
    print("Feature provenance:")
    print(pd.DataFrame(provenance_rows).to_string(index=False))


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

    # fix: _encode_target() was a second, independent implementation of
    # label normalization living alongside preprocessing.normalize_target()
    # — and a stricter/buggier one at that (no support for True/False or
    # "0"/"1" string labels that normalize_target() already handles).
    # Removed in favor of the single shared implementation so every
    # training path (SectorPipeline, train_universal_model, and
    # extract_universal_features) applies identical label rules.

    # ── Training (unchanged — no routing decisions made during fit) ──

    def fit(self) -> 'SectorPipeline':
        print(f"\n{'='*50}\n  Training pipeline — {self.sector.upper()}\n{'='*50}")
        df = self._load_data()
        df = self._clean(df)
        target_col = self.config['target_col']
        y = normalize_target(df[target_col])
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
        y = y.values
        # fix: pre-flight check immediately before stratify=y, per the
        # shared validation contract (same check train_universal_model
        # now runs) — catches a mixed/non-binary target here with an
        # actionable message instead of a cryptic NumPy error.
        validate_target_types(y, context=f"SectorPipeline.fit[{self.sector}]")
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

    # ── Internal: the actual sector-model inference, unchanged math ──
    # Split out from predict() so predict() can call this ONLY after
    # routing.route() has selected FULL_SECTOR_MODEL — this method
    # itself makes no routing decisions.

    def _run_sector_model(
        self,
        df_raw: pd.DataFrame,
        coverage_dict: CoverageResult,
        quality_dict: dict,
        routing_decision,
        explain: bool,
        explain_output: str | None,
        _prediction_mode: str,
        _canonical_by_raw_column: dict[str, str] | None = None,
        _intelligence=None,
    ) -> pd.DataFrame:
        diagnostic_run = active_run()
        # Phase 1 of the semantic prediction migration: produce the complete
        # semantic binding report beside the legacy ABI vector.  This is
        # intentionally shadow-only until benchmark parity is demonstrated.
        # The resolver never performs header-to-header matching.
        semantic_bindings = None
        if _intelligence is not None:
            from .semantic_feature_resolver import FeatureResolverPipeline
            semantic_bindings = FeatureResolverPipeline().run(
                df_raw, _intelligence, self.feature_names,
            )
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
        default_features: list[str] = []
        for col in self.feature_names:
            if col not in df.columns:
                default_features.append(col)
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
        # The standard UDIF model-input capture supplies the final shape,
        # feature names, missing values, constant/near-constant counts, and
        # numeric spread when diagnostics are enabled.  The Telecom report
        # below adds default and source/canonical provenance from this path.
        if diagnostic_run is not None:
            diagnostic_run.capture_model_input(X, list(df.columns))
        preds = self.model.predict(X)
        if self.sector == 'telecom':
            raw_feature_sources: dict[str, list[str]] = {}
            for raw_column, target_column in rename_to_target.items():
                if target_column in self.feature_names:
                    raw_feature_sources.setdefault(target_column, []).append(raw_column)
                # One-hot fields originate from the configured categorical
                # source, even though their final feature name is expanded.
                for feature in self.feature_names:
                    if feature.startswith(f"{target_column}_"):
                        raw_feature_sources.setdefault(feature, []).append(raw_column)
            _print_telecom_pre_prediction_diagnostics(
                df,
                default_features=default_features,
                raw_feature_sources=raw_feature_sources,
                canonical_by_raw_column=_canonical_by_raw_column or {},
            )
        probas = self.model.predict_proba(X)[:, 1]
        if diagnostic_run is not None:
            diagnostic_run.capture_predictions(probas)
        try:
            verify_prediction_variance(probas)
        except Exception as exc:
            if diagnostic_run is not None:
                try:
                    from .udif_rendering import render, render_execution_terminated
                    render(diagnostic_run)
                    render_execution_terminated("verify_prediction_variance", exc)
                except Exception:
                    # Observability must never replace the prediction guard's error.
                    pass
            raise

        results = pd.DataFrame()
        results['CustomerID'] = (id_series.values if id_series is not None
                                 else [f"UNK_{i}" for i in range(len(df))])
        results['Predicted_Churn'] = pd.Series(preds).map({0: 'No', 1: 'Yes'})
        results['Churn_Probability'] = probas.round(4)
        results['Risk_Level'] = np.select(
            [probas >= 0.70, probas >= 0.40], ['High', 'Medium'], default='Low')
        results['Prediction_Model'] = 'Sector XGBoost'
        results['Prediction_Mode'] = _prediction_mode
        results['Coverage_Score'] = f"{coverage_dict.summary.overall_coverage*100:.1f}%"
        results['Coverage_Status'] = coverage_dict.summary.readiness
        results = attach_common_metadata(results, coverage_dict, 'Sector XGBoost')

        results['Routing_Pipeline'] = routing_decision.selected_pipeline
        results['Routing_Confidence'] = routing_decision.confidence
        results['Routing_Reason'] = routing_decision.reasoning

        explain_summary = None
        if explain:
            id_col = results['CustomerID'].values
            log_path = explain_output or f"outputs/shap_logs/{self.sector}_shap_log.csv"
            write_shap_log(self.model, df, self.feature_names, id_col, log_path)
            explain_summary = summarize_shap_directions(self.model, df, self.feature_names)
        results.attrs['explain_summary'] = explain_summary
        results.attrs['coverage'] = coverage_dict
        results.attrs['quality'] = quality_dict
        results.attrs['routing_decision'] = routing_decision
        if semantic_bindings is not None:
            results.attrs['semantic_feature_bindings'] = semantic_bindings
            results.attrs['semantic_feature_provenance'] = semantic_bindings.to_dict()
        return results

    # ── Public prediction entry point ────────────────────────────

    def predict(self, input_csv: str, explain: bool = False,
                explain_output: str | None = None,
                _prediction_mode: str = 'Sector') -> pd.DataFrame:
        """
        Predict churn for this sector. ALL routing decisions are made by
        routing.route() — this method only:
          1. Prepares the input (sanitize, derive temporal features)
          2. Computes coverage + quality
          3. Attempts feature recovery if coverage is Yellow (a feature-
             engineering step, not a routing decision) and re-scores
             coverage on the recovered frame
          4. Calls routing.route() exactly once with the FINAL coverage
          5. Executes whatever RoutingDecision.selected_model specifies
        """
        df_raw = pd.read_csv(input_csv)
        df_raw = sanitize_numerical_columns(df_raw)
        df_raw = derive_temporal_features(df_raw)

        intelligence = infer_intelligence(df_raw)
        diagnostic_run = active_run()
        if diagnostic_run is not None:
            diagnostic_run.capture_intelligence(df_raw, self.sector, intelligence)
        coverage = intelligence.coverage
        quality = run_quality_gate(df_raw, target_col=self.config['target_col'])
        decision = intelligence.routing.decision

        if decision.selected_pipeline != f"{self.sector.capitalize()}Pipeline":
            from .universal_pipeline import predict_universal
            results = predict_universal(
                input_path=input_csv, force_sector=self.sector,
                _intelligence=intelligence, _prediction_mode=_prediction_mode)
            results.attrs['coverage'] = coverage
            results.attrs['quality'] = quality
            results.attrs['routing_decision'] = decision
            results.attrs.setdefault('explain_summary', None)
            return results

        return self._run_sector_model(
            df_raw, coverage, quality, decision,
            explain, explain_output, _prediction_mode,
            {str(column): mapping.chosen_concept.name for column, mapping in zip(
                df_raw.columns, intelligence.canonical_mapping.mappings
            )}, intelligence,
        )
