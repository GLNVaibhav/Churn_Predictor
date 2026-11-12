"""
universal_churn/universal_pipeline.py
Phase B: Universal cross-sector model training and prediction.

Routing note
------------
predict_universal() can be reached two ways:
  1. Directly, as the --mode universal CLI entry point — in this case
     it computes coverage + quality itself and calls routing.route()
     so the quality gate (leakage check) still applies even when the
     user explicitly bypasses sector routing.
  2. As a fallback target from SectorPipeline.predict() (auto/sector
     modes routed to UNIVERSAL_MODEL) — in this case the caller has
     ALREADY called routing.route() and passes the precomputed
     coverage via _precomputed_coverage; this function does not call
     route() a second time in that case, to avoid a duplicate/
     conflicting routing decision for the same input.

train_universal_model() is unchanged — training has no routing
decisions to make.
"""
from __future__ import annotations
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from .config import (
    SECTOR_CONFIG, SECTOR_NORM_COLUMNS,
    UNIVERSAL_MODEL_PATH, UNIVERSAL_SCALER_PATH,
    GLOBAL_CONCEPT_MAP,
)
from .feature_engineering import (
    extract_universal_features, transform_features_by_sector, compute_norm_stats,
)
from .udif import active_run
from .preprocessing import (
    sanitize_numerical_columns, derive_temporal_features, detect_sector,
    normalize_target, validate_target_types,
)
from .reporting import attach_common_metadata
from .utils import positive_class_probabilities, verify_prediction_variance
from .quality_gate import run_quality_gate
from .coverage import CoverageResult
from .routing import RoutingDecision
from .intelligence_pipeline import IntelligenceResult, infer_intelligence
from .explainability import write_shap_log, summarize_shap_directions
from .leakage_safe_training import (
    classification_metrics, dataframe_fingerprint, fit_candidate, holdout_split,
    write_candidate_artifacts,
)


def train_universal_model(tune_metric: str | None = None) -> None:
    """Train a non-promoted universal candidate with per-sector raw holdouts.

    Each source dataset is split before normalization statistics or engineered
    features are learned. The final pooled holdout is never used for model
    selection, preprocessing, or resampling.
    """
    print("\n" + "=" * 55)
    print("  PHASE B — Training Universal Cross-Sector Model")
    print("=" * 55)
    development_parts: list[pd.DataFrame] = []
    holdout_parts: list[pd.DataFrame] = []
    group_parts: list[pd.Series] = []
    fingerprints: dict[str, str] = {}
    norm_stats: dict = {}
    for sector, config in SECTOR_CONFIG.items():
        path = config['data_path']
        if not Path(path).exists():
            print(f"  Skipping {sector} — data not found at {path}")
            continue
        print(f"  Loading {sector}...")
        df = pd.read_csv(path)
        target_col = config['target_col']
        if target_col not in df:
            raise ValueError(f"{sector} dataset lacks target {target_col!r}.")
        y = pd.Series(normalize_target(df[target_col]), index=df.index)
        excluded = {target_col, *config.get('drop_cols', [])}
        raw_predictors = df.drop(columns=[c for c in excluded if c in df])
        entity_col = next((
            c for c in config.get('drop_cols', [])
            if c in df and 'id' in c.lower()
        ), None)
        split = holdout_split(
            raw_predictors, y,
            groups=df[entity_col] if entity_col else None,
            group_column=entity_col,
            random_state=42,
        )
        train_raw = df.iloc[split.train_indices].copy()
        holdout_raw = df.iloc[split.holdout_indices].copy()
        # Normalization maxima are learned only from this sector's development rows.
        sector_stats = compute_norm_stats(
            train_raw, sector, SECTOR_NORM_COLUMNS.get(sector, []))
        norm_stats.update(sector_stats)
        train_features = extract_universal_features(
            train_raw, sector, target_col, norm_stats=sector_stats)
        holdout_features = extract_universal_features(
            holdout_raw, sector, target_col, norm_stats=sector_stats)
        dev_ids = train_raw[entity_col].astype(str) if entity_col else pd.Series(train_raw.index.astype(str), index=train_raw.index)
        group_parts.append(pd.Series([f"{sector}:{value}" for value in dev_ids], index=train_features.index))
        development_parts.append(train_features)
        holdout_parts.append(holdout_features)
        fingerprints[sector] = dataframe_fingerprint(df)
        print(f"  {sector}: {len(train_features)} development / {len(holdout_features)} untouched holdout rows; split={split.strategy}")
    if not development_parts:
        raise RuntimeError("No sector data found. Check data paths.")
    development = pd.concat(development_parts, ignore_index=True)
    untouched = pd.concat(holdout_parts, ignore_index=True)
    development['Churn'] = normalize_target(development['Churn'])
    untouched['Churn'] = normalize_target(untouched['Churn'])
    X_train = development.drop(columns=['Churn'])
    y_train = development['Churn'].astype(int)
    X_holdout = untouched.drop(columns=['Churn'])
    y_holdout = untouched['Churn'].astype(int)
    groups = pd.concat(group_parts, ignore_index=True)
    validate_target_types(y_train.to_numpy(), context="train_universal_model")
    base = XGBClassifier(
        n_estimators=300, learning_rate=0.05, max_depth=5,
        subsample=0.8, colsample_bytree=0.8, random_state=42,
        eval_metric='logloss', verbosity=0,
    )
    if tune_metric:
        param_grid = {
            'model__n_estimators': [200, 300], 'model__max_depth': [4, 5],
            'model__learning_rate': [0.03, 0.05],
        }
    else:
        param_grid = None
    groups.index = X_train.index
    result = fit_candidate(
        X_train, y_train, base, groups=groups, group_column='sector-prefixed-entity',
        parameter_grid=param_grid, selection_metric=tune_metric or 'roc_auc',
        final_holdout=(X_holdout, y_holdout),
        split_description='Per-sector stratified raw holdout before feature normalization; pooled final holdout',
    )
    sector_holdout_metrics = {}
    for sector_frame in holdout_parts:
        sector_name = str(sector_frame['Sector'].iloc[0])
        sector_target = normalize_target(sector_frame['Churn'])
        sector_features = sector_frame.drop(columns=['Churn'])
        positive_index = list(result['model'].classes_).index(1)
        sector_probabilities = result['model'].predict_proba(sector_features)[:, positive_index]
        sector_holdout_metrics[sector_name] = {
            "rows": len(sector_frame),
            "metrics": classification_metrics(sector_target, sector_probabilities),
        }
    report = {
        "candidate_only": True, "model": "Universal XGBClassifier",
        "dataset_fingerprints": fingerprints,
        "targets": {sector: SECTOR_CONFIG[sector]['target_col'] for sector in fingerprints},
        "random_state": 42, "sector_specific_normalization": norm_stats,
        "preprocessing": "per-sector raw development-only normalization; fold-local imputation/encoding/scaling",
        "imbalance": "fold-local RandomOverSampler after encoding; no pre-split duplication",
        "cross_domain_claim": "Not established; this is a pooled random holdout, not leave-one-sector-out validation.",
        "per_sector_holdout_metrics": sector_holdout_metrics,
    }
    out = Path('outputs/evaluation/candidates/universal-per-sector')
    model_path, report_path = write_candidate_artifacts(
        result, output_directory=out, model_name='universal_xgb', metadata=report)
    print(f"\n  Universal candidate holdout metrics: {result['holdout_metrics']}")
    print(f"  Candidate only (not promoted): {model_path}; report: {report_path}")


def predict_universal(
    input_path: str,
    force_sector: str | None = None,
    explain: bool = False,
    explain_output: str | None = None,
    _prediction_mode: str = 'Universal',
    _intelligence: IntelligenceResult | None = None,
) -> pd.DataFrame:
    """
    Predict churn using the universal cross-sector model.

    Routing: if _precomputed_coverage is None (this function is the
    entry point, e.g. --mode universal), coverage + quality are
    computed here and routing.route() is called once so the quality
    gate (leakage detection) still applies. If _precomputed_coverage
    is provided (this function was reached as a fallback FROM
    SectorPipeline.predict(), which already called route()), routing
    is not re-run — the caller's RoutingDecision already determined
    that the universal model should be used for this input.
    """
    df_raw = pd.read_csv(input_path)
    df_raw = sanitize_numerical_columns(df_raw)
    df_raw = derive_temporal_features(df_raw)
    sector = force_sector or detect_sector(df_raw)

    intelligence = _intelligence or infer_intelligence(df_raw)
    diagnostic_run = active_run()
    if diagnostic_run is not None:
        diagnostic_run.capture_intelligence(df_raw, sector, intelligence)
    _coverage: CoverageResult = intelligence.coverage
    routing_decision: RoutingDecision = intelligence.routing.decision
    _quality = run_quality_gate(df_raw, target_col=SECTOR_CONFIG[sector]['target_col'])

    df_lower = df_raw.copy()
    df_lower.columns = (df_lower.columns.str.lower()
                        .str.replace(' ', '', regex=False)
                        .str.replace('_', '', regex=False))
    normalized_global_map = {
        k.replace('_', '').replace(' ', ''): v
        for k, v in GLOBAL_CONCEPT_MAP.items()
    }
    df_lower.rename(columns=normalized_global_map, inplace=True)
    config = SECTOR_CONFIG[sector]
    target_cols_pool = (config['scale_cols'] + [config['target_col']]
                        + config['drop_cols'] + config.get('ohe_cols', []))
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
    X_processed = transform_features_by_sector(
        df_mapped, sector,
        canonical_mapping_result=intelligence.canonical_mapping,
        coverage_summary=intelligence.coverage.summary,
    )
    # Shadow semantic resolver report.  Universal preparation already uses
    # canonical fields; this report makes the intelligence-to-feature bridge
    # explicit and comparable with the sector-model migration path.
    from .semantic_feature_resolver import FeatureResolverPipeline
    semantic_bindings = FeatureResolverPipeline().run(
        df_raw, intelligence, list(X_processed.columns),
    )
    if diagnostic_run is not None:
        diagnostic_run.capture_feature_preparation(
            X_processed.attrs.get('feature_engineering_manifest', {})
        )
    scaler = joblib.load(str(UNIVERSAL_SCALER_PATH))
    model = joblib.load(str(UNIVERSAL_MODEL_PATH))
    if hasattr(scaler, 'feature_names_in_'):
        expected_features = scaler.feature_names_in_
        for col in expected_features:
            if col not in X_processed.columns:
                X_processed[col] = 0
        X_processed = X_processed[list(expected_features)]
        X_scaled = scaler.transform(X_processed)
    else:
        X_scaled = scaler.transform(X_processed.values)
    if diagnostic_run is not None:
        diagnostic_run.capture_model_input(X_scaled, list(X_processed.columns))
    probas = positive_class_probabilities(model, X_scaled)
    if diagnostic_run is not None:
        diagnostic_run.capture_predictions(probas)
    preds = model.predict(X_scaled)
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
    id_cols = ['customerID', 'CustomerID', 'Customer ID',
               'CustomerId', 'PatientID', 'patientid']
    id_series = None
    for col in df_raw.columns:
        if col in id_cols:
            id_series = df_raw[col]
            break
    results['CustomerID'] = (id_series.values if id_series is not None
                             else [f"UNK_{i}" for i in range(len(df_raw))])
    results['Predicted_Churn'] = pd.Series(preds).map({0: 'No', 1: 'Yes'})
    results['Churn_Probability'] = probas.round(4)
    results['Risk_Level'] = np.select(
        [probas >= 0.70, probas >= 0.40], ['High', 'Medium'], default='Low')
    results['Sector'] = sector.capitalize()
    results['Prediction_Model'] = 'Universal XGBoost'
    results['Prediction_Mode'] = _prediction_mode
    results['Coverage_Score'] = f"{_coverage.summary.overall_coverage*100:.1f}%"
    results['Coverage_Status'] = _coverage.summary.readiness
    results = attach_common_metadata(results, _coverage, 'Universal XGBoost')

    results['Routing_Pipeline'] = routing_decision.selected_pipeline
    results['Routing_Confidence'] = routing_decision.confidence
    results['Routing_Reason'] = routing_decision.reasoning

    explain_summary = None
    if explain:
        id_col = results['CustomerID'].values
        log_path = explain_output or "outputs/shap_logs/universal_shap_log.csv"
        write_shap_log(model, X_processed, list(X_processed.columns), id_col, log_path)
        explain_summary = summarize_shap_directions(
            model, X_processed, list(X_processed.columns))
    results.attrs['explain_summary'] = explain_summary
    results.attrs['intelligence'] = intelligence
    results.attrs['coverage'] = _coverage
    results.attrs['quality'] = _quality
    results.attrs['routing_decision'] = routing_decision
    results.attrs['semantic_feature_bindings'] = semantic_bindings
    results.attrs['semantic_feature_provenance'] = semantic_bindings.to_dict()
    return results
