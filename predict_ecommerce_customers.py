"""
predict_ecommerce_customers.py
-------------------------------
Run all 3 trained models on new E-commerce customer data.

Usage:
    python predict_ecommerce_customers.py
    python predict_ecommerce_customers.py --input data/ecommerce/ecommerce_new_customers.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

try:
    from xgboost import XGBClassifier
except ImportError as exc:
    raise ImportError("xgboost is required.") from exc


# ── Default paths ────────────────────────────────────────────────
DEFAULT_INPUT    = Path("data/ecommerce/ecommerce_new_customers.csv")
DEFAULT_OUTPUT   = Path("outputs/results/ecommerce_new_predictions.csv")
DEFAULT_SCALER   = Path("outputs/scaler_ecommerce.pkl")
DEFAULT_FEATURES = Path("outputs/ecommerce_feature_names.csv")
DEFAULT_LR       = Path("outputs/lr_model_ecommerce.pkl")
DEFAULT_RF       = Path("outputs/rf_model_ecommerce.pkl")
DEFAULT_XGB      = Path("outputs/xgb_model_ecommerce.pkl")
DEFAULT_X_TRAIN  = Path("outputs/X_train_ecommerce.npy")
DEFAULT_Y_TRAIN  = Path("outputs/y_train_ecommerce.npy")
DEFAULT_ENCODERS = Path(
    "outputs/ecommerce_encoders.pkl"
)

# ── Categorical columns that need encoding ───────────────────────
CATEGORICAL_COLS = [
    'PreferredLoginDevice',
    'PreferredPaymentMode',
    'Gender',
    'PreferedOrderCat',
    'MaritalStatus',
]

# ── Numerical columns to scale ───────────────────────────────────
NUMERIC_COLS = [
    'Tenure', 'CityTier', 'WarehouseToHome',
    'HourSpendOnApp', 'NumberOfDeviceRegistered',
    'SatisfactionScore', 'NumberOfAddress',
    'Complain', 'OrderAmountHikeFromlastYear',
    'CouponUsed', 'OrderCount',
    'DaySinceLastOrder', 'CashbackAmount',
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Predict churn for new E-commerce customers."
    )
    parser.add_argument("--input",    type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output",   type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--scaler",   type=Path, default=DEFAULT_SCALER)
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--lr-model", type=Path, default=DEFAULT_LR)
    parser.add_argument("--rf-model", type=Path, default=DEFAULT_RF)
    parser.add_argument("--xgb-model",type=Path, default=DEFAULT_XGB)
    parser.add_argument("--x-train",  type=Path, default=DEFAULT_X_TRAIN)
    parser.add_argument("--y-train",  type=Path, default=DEFAULT_Y_TRAIN)
    parser.add_argument(
    "--encoders",
    type=Path,
    default=DEFAULT_ENCODERS
    )
    return parser.parse_args()


def load_feature_names(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Feature list not found: {path}")
    return pd.read_csv(path).iloc[:, 0].astype(str).tolist()


def load_or_train_lr(model_path, x_train_path, y_train_path):
    if model_path.exists():
        return joblib.load(model_path)
    X = np.load(x_train_path)
    y = np.load(y_train_path)
    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(X, y)
    joblib.dump(model, model_path)
    return model


def load_or_train_rf(model_path, x_train_path, y_train_path):
    if model_path.exists():
        return joblib.load(model_path)
    X = np.load(x_train_path)
    y = np.load(y_train_path)
    model = RandomForestClassifier(
        n_estimators=100, random_state=42, n_jobs=-1
    )
    model.fit(X, y)
    joblib.dump(model, model_path)
    return model


def load_or_train_xgb(model_path, x_train_path, y_train_path):
    if model_path.exists():
        return joblib.load(model_path)
    X = np.load(x_train_path)
    y = np.load(y_train_path)
    model = XGBClassifier(
        n_estimators=200, learning_rate=0.1, max_depth=4,
        random_state=42, use_label_encoder=False,
        eval_metric='logloss', verbosity=0
    )
    model.fit(X, y)
    joblib.dump(model, model_path)
    return model


def preprocess(
    input_path: Path,
    feature_names: list[str],
    scaler,encoders

) -> tuple[pd.DataFrame, pd.Series]:

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = pd.read_csv(input_path)

    # Extract and remove CustomerID
    if 'CustomerID' not in df.columns:
        raise ValueError("Input CSV must have a CustomerID column.")
    customer_ids = df['CustomerID'].copy()
    df.drop(columns=['CustomerID'], inplace=True)

    # Drop Expected_Churn if present (test label — not a feature)
    if 'Expected_Churn' in df.columns:
        df.drop(columns=['Expected_Churn'], inplace=True)

    # Fill numeric nulls
    for col in df.select_dtypes(include='number').columns:
        df[col] = df[col].fillna(df[col].median())

    # Fill categorical nulls
    for col in df.select_dtypes(include=['object', 'string']).columns:
        df[col] = df[col].fillna(df[col].mode()[0])

    # Encode categorical columns
    for col in CATEGORICAL_COLS:

        if col not in df.columns:
            continue

        if col not in encoders:
            continue

        le = encoders[col]

        known_values = set(le.classes_)

        df[col] = df[col].astype(str)

        df.loc[
            ~df[col].isin(known_values),
            col
        ] = le.classes_[0]

        df[col] = le.transform(
            df[col]
        )

    # Add any missing feature columns as 0
    for col in feature_names:
        if col not in df.columns:
            df[col] = 0

    # Reorder to match training feature order
    # Add missing features
    for col in feature_names:
        if col not in df.columns:
            df[col] = 0

    # Remove extras and reorder
    df = df.reindex(
        columns=feature_names,
        fill_value=0
    )

    # Scale exactly the columns used during training

    scale_cols = list(scaler.feature_names_in_)

    for col in scale_cols:
        if col not in df.columns:
            df[col] = 0

    df[scale_cols] = scaler.transform(
        df[scale_cols]
    )

    # Final null check
    if df.isnull().any().any():
        raise ValueError("Preprocessed data still has nulls.")

    return df, customer_ids


def add_results(
    results: pd.DataFrame,
    prefix: str,
    preds: np.ndarray,
    probs: np.ndarray,
) -> None:
    results[f"{prefix}_Prediction"]   = pd.Series(preds).map({0:'No Churn', 1:'Churn'})
    results[f"{prefix}_Probability"]  = probs.round(3)
    results[f"{prefix}_Risk"]         = np.select(
        [probs >= 0.70, probs >= 0.40],
        ['High', 'Medium'],
        default='Low'
    )


def main() -> None:
    args = parse_args()

    print("Loading models and scaler...")
    feature_names = load_feature_names(args.features)

    encoders = joblib.load(
        args.encoders
    )

    scaler = joblib.load(
        args.scaler
    )
    lr_model  = load_or_train_lr( args.lr_model,  args.x_train, args.y_train)
    rf_model  = load_or_train_rf( args.rf_model,  args.x_train, args.y_train)
    xgb_model = load_or_train_xgb(args.xgb_model, args.x_train, args.y_train)
    print("All models ready.")

    print(f"\nPreprocessing input: {args.input}")
    df_processed, customer_ids = preprocess(
        args.input,
        feature_names,
        scaler,
        encoders
    )
    X = df_processed.to_numpy()

    results = pd.DataFrame({'CustomerID': customer_ids})

    add_results(results, 'LR',  lr_model.predict(X),  lr_model.predict_proba(X)[:,1])
    add_results(results, 'RF',  rf_model.predict(X),  rf_model.predict_proba(X)[:,1])
    add_results(results, 'XGB', xgb_model.predict(X), xgb_model.predict_proba(X)[:,1])

    # Majority vote across 3 models
    results['Majority_Vote'] = results[[
        'LR_Prediction','RF_Prediction','XGB_Prediction'
    ]].apply(
        lambda row: 'Churn' if list(row).count('Churn') >= 2 else 'No Churn',
        axis=1
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.output, index=False)

    print(f"\nResults saved to: {args.output}")
    print(f"Customers scored: {len(results)}")
    print("\n" + "="*90)
    print(results.to_string(index=False))
    print("="*90)

    # Summary
    print("\nSummary:")
    for col in ['LR_Prediction','RF_Prediction','XGB_Prediction','Majority_Vote']:
        churn_count = (results[col] == 'Churn').sum()
        print(f"  {col:<25}: {churn_count} churners out of {len(results)}")


if __name__ == "__main__":
    main()
