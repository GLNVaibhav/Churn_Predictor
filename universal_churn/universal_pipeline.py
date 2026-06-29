"""
universal_churn/universal_pipeline.py
Phase B: Universal cross-sector model training and prediction.
"""
from __future__ import annotations
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, classification_report,
    f1_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import LabelEncoder, StandardScaler
from imblearn.over_sampling import SMOTE
from xgboost import XGBClassifier
from .config import (
    SECTOR_CONFIG, SECTOR_NORM_COLUMNS,
    UNIVERSAL_MODEL_PATH, UNIVERSAL_SCALER_PATH,
    UNIVERSAL_FEATURES_PATH, UNIVERSAL_NORM_STATS_PATH,
    GLOBAL_CONCEPT_MAP,
)
from .feature_engineering import (
    extract_universal_features, transform_features_by_sector, compute_norm_stats,
)
from .preprocessing import (
    sanitize_numerical_columns, derive_temporal_features, detect_sector,
)
from .reporting import attach_common_metadata
from .utils import verify_prediction_variance
from .coverage import compute_coverage_score
from .explainability import write_shap_log, summarize_shap_directions


def train_universal_model(tune_metric: str | None = None) -> None:
    """Phase B: Merge all 4 sectors into universal feature space."""
    print("\n" + "=" * 55)
    print("  PHASE B — Training Universal Cross-Sector Model")
    print("=" * 55)
    all_data = []
    norm_stats: dict = {}
    for sector, config in SECTOR_CONFIG.items():
        path = config['data_path']
        if not Path(path).exists():
            print(f"  Skipping {sector} — data not found at {path}")
            continue
        print(f"  Loading {sector}...")
        df = pd.read_csv(path)
        if 'TotalCharges' in df.columns:
            df['TotalCharges'] = pd.to_numeric(
                df['TotalCharges'], errors='coerce').fillna(0)
        for col in df.select_dtypes(include='number').columns:
            df[col] = df[col].fillna(df[col].median())
        for col in df.select_dtypes(include=['object', 'string']).columns:
            df[col] = df[col].fillna(df[col].mode()[0])
        norm_stats.update(
            compute_norm_stats(df, sector, SECTOR_NORM_COLUMNS.get(sector, [])))
        feat_df = extract_universal_features(
            df, sector, config['target_col'], norm_stats=norm_stats)
        all_data.append(feat_df)
        print(f"  {sector}: {len(feat_df)} rows extracted")
    if not all_data:
        raise RuntimeError("No sector data found. Check data paths.")
    combined = pd.concat(all_data, ignore_index=True)
    print(f"\n  Combined dataset: {combined.shape[0]} rows")
    balanced_parts = []
    for _, group in combined.groupby('Sector'):
        counts = group['Churn'].value_counts()
        if len(counts) < 2:
            balanced_parts.append(group)
            continue
        majority_n = counts.max()
        minority_class = counts.idxmin()
        minority = group[group['Churn'] == minority_class]
        majority = group[group['Churn'] != minority_class]
        balanced_parts.append(pd.concat([
            majority, minority.sample(n=majority_n, replace=True, random_state=42)]))
    combined = pd.concat(balanced_parts, ignore_index=True)
    le_sector = LabelEncoder()
    combined['Sector_Encoded'] = le_sector.fit_transform(combined['Sector'])
    combined.drop(columns=['Sector'], inplace=True)
    combined = combined.replace([np.inf, -np.inf], np.nan).fillna(0)
    X = combined.drop(columns=['Churn'])
    y = combined['Churn'].values
    feature_names = X.columns.tolist()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y)
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)
    smote = SMOTE(random_state=42)
    X_train_sm, y_train_sm = smote.fit_resample(X_train, y_train)
    if tune_metric:
        param_grid = {
            'n_estimators': [200, 300, 400], 'max_depth': [4, 5, 6],
            'learning_rate': [0.03, 0.05, 0.1],
            'subsample': [0.8, 1.0], 'colsample_bytree': [0.8, 1.0],
        }
        base = XGBClassifier(random_state=42, use_label_encoder=False,
                             eval_metric='logloss', verbosity=0)
        search = GridSearchCV(base, param_grid, scoring=tune_metric,
                              cv=3, n_jobs=-1, verbose=0)
        search.fit(X_train_sm, y_train_sm)
        model = search.best_estimator_
    else:
        model = XGBClassifier(
            n_estimators=300, learning_rate=0.05, max_depth=5,
            subsample=0.8, colsample_bytree=0.8, random_state=42,
            use_label_encoder=False, eval_metric='logloss', verbosity=0)
        model.fit(X_train_sm, y_train_sm)
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    print(f"\n  Universal Model — Test Set Results:")
    print(f"  Accuracy  : {accuracy_score(y_test, y_pred):.4f}")
    print(f"  ROC-AUC   : {roc_auc_score(y_test, y_proba):.4f}")
    UNIVERSAL_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, UNIVERSAL_MODEL_PATH)
    joblib.dump(scaler, UNIVERSAL_SCALER_PATH)
    joblib.dump(le_sector, str(UNIVERSAL_MODEL_PATH).replace('.pkl', '_le_sector.pkl'))
    joblib.dump(norm_stats, UNIVERSAL_NORM_STATS_PATH)
    pd.Series(feature_names).to_csv(UNIVERSAL_FEATURES_PATH, index=False)
    print(f"  Universal model saved : {UNIVERSAL_MODEL_PATH}")


def predict_universal(
    input_path: str,
    force_sector: str | None = None,
    explain: bool = False,
    explain_output: str | None = None,
    _prediction_mode: str = 'Universal',
    _precomputed_coverage: dict | None = None,
) -> pd.DataFrame:
    """Predict churn using the universal cross-sector model."""
    df_raw = pd.read_csv(input_path)
    df_raw = sanitize_numerical_columns(df_raw)
    df_raw = derive_temporal_features(df_raw)
    sector_for_coverage = force_sector if force_sector else detect_sector(df_raw)
    if _precomputed_coverage is not None:
        _coverage = _precomputed_coverage
    else:
        _coverage = compute_coverage_score(
            df_input=df_raw, sector=sector_for_coverage, mode='universal')
    sector = force_sector or detect_sector(df_raw)
    print(f"  Auto-detected sector: {sector}")
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
    X_processed = transform_features_by_sector(df_mapped, sector)
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
    probas = model.predict_proba(X_scaled)[:, 1]
    preds = model.predict(X_scaled)
    verify_prediction_variance(probas)
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
    results['Coverage_Score'] = f"{_coverage['coverage_score']*100:.1f}%"
    results['Coverage_Status'] = _coverage['status']
    results = attach_common_metadata(results, _coverage, 'Universal XGBoost')
    explain_summary = None
    if explain:
        id_col = results['CustomerID'].values
        log_path = explain_output or "outputs/shap_logs/universal_shap_log.csv"
        write_shap_log(model, X_processed, list(X_processed.columns), id_col, log_path)
        explain_summary = summarize_shap_directions(
            model, X_processed, list(X_processed.columns))
    results.attrs['explain_summary'] = explain_summary
    results.attrs['coverage'] = _coverage
    return results