from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier

try:
    from xgboost import XGBClassifier
except ImportError as exc:
    raise ImportError("xgboost is required to score the XGBoost model.") from exc


DEFAULT_INPUT = Path("new_telecom_customers.csv")
DEFAULT_OUTPUT = Path("outputs/results/new_customer_predictions.csv")
DEFAULT_SCALER = Path("outputs/scaler_telecom.pkl")
DEFAULT_FEATURES = Path("outputs/telecom_feature_names.csv")
DEFAULT_MODEL = Path("outputs/lr_model_telecom.pkl")
DEFAULT_RF_MODEL = Path("outputs/rf_model_telecom.pkl")
DEFAULT_XGB_MODEL = Path("outputs/xgb_model_telecom.pkl")
DEFAULT_X_TRAIN = Path("outputs/X_train_telecom.npy")
DEFAULT_Y_TRAIN = Path("outputs/y_train_telecom.npy")

NUMERIC_SCALE_COLS = ["tenure", "MonthlyCharges", "TotalCharges"]
BINARY_COLS = [
    "Partner",
    "Dependents",
    "PhoneService",
    "PaperlessBilling",
    "MultipleLines",
    "OnlineSecurity",
    "OnlineBackup",
    "DeviceProtection",
    "TechSupport",
    "StreamingTV",
    "StreamingMovies",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Predict churn for new telecom customers."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--scaler", type=Path, default=DEFAULT_SCALER)
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--rf-model", type=Path, default=DEFAULT_RF_MODEL)
    parser.add_argument("--xgb-model", type=Path, default=DEFAULT_XGB_MODEL)
    parser.add_argument("--x-train", type=Path, default=DEFAULT_X_TRAIN)
    parser.add_argument("--y-train", type=Path, default=DEFAULT_Y_TRAIN)
    return parser.parse_args()


def load_feature_names(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Feature list not found: {path}")
    feature_df = pd.read_csv(path)
    if feature_df.shape[1] != 1:
        raise ValueError(f"Expected one feature column in {path}, found {feature_df.shape[1]}")
    return feature_df.iloc[:, 0].astype(str).tolist()


def load_or_train_lr(model_path: Path, x_train_path: Path, y_train_path: Path) -> LogisticRegression:
    if model_path.exists():
        return joblib.load(model_path)

    if not x_train_path.exists():
        raise FileNotFoundError(f"Training features not found: {x_train_path}")
    if not y_train_path.exists():
        raise FileNotFoundError(f"Training target not found: {y_train_path}")

    X_train = np.load(x_train_path)
    y_train = np.load(y_train_path)
    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(X_train, y_train)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    return model


def load_or_train_rf(model_path: Path, x_train_path: Path, y_train_path: Path) -> RandomForestClassifier:
    if model_path.exists():
        return joblib.load(model_path)

    if not x_train_path.exists():
        raise FileNotFoundError(f"Training features not found: {x_train_path}")
    if not y_train_path.exists():
        raise FileNotFoundError(f"Training target not found: {y_train_path}")

    X_train = np.load(x_train_path)
    y_train = np.load(y_train_path)
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=None,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    return model


def load_or_train_xgb(model_path: Path, x_train_path: Path, y_train_path: Path) -> XGBClassifier:
    if model_path.exists():
        return joblib.load(model_path)

    if not x_train_path.exists():
        raise FileNotFoundError(f"Training features not found: {x_train_path}")
    if not y_train_path.exists():
        raise FileNotFoundError(f"Training target not found: {y_train_path}")

    X_train = np.load(x_train_path)
    y_train = np.load(y_train_path)
    model = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric="logloss",
        tree_method="hist",
    )
    model.fit(X_train, y_train)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    return model


def preprocess_new_customers(input_path: Path, feature_names: list[str], scaler) -> tuple[pd.DataFrame, pd.Series]:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    new_df = pd.read_csv(input_path)
    if "customerID" not in new_df.columns:
        raise ValueError("Input file must include a customerID column.")

    customer_ids = new_df["customerID"].copy()
    new_df.drop(columns=["customerID"], inplace=True)

    if "TotalCharges" not in new_df.columns:
        raise ValueError("Input file must include a TotalCharges column.")
    new_df["TotalCharges"] = pd.to_numeric(new_df["TotalCharges"], errors="coerce")
    new_df["TotalCharges"] = new_df["TotalCharges"].fillna(0)

    for col in BINARY_COLS:
        if col not in new_df.columns:
            raise ValueError(f"Missing required binary column: {col}")
        new_df[col] = new_df[col].map(
            {
                "Yes": 1,
                "No": 0,
                "No phone service": 0,
                "No internet service": 0,
            }
        )

    if "gender" not in new_df.columns:
        raise ValueError("Missing required binary column: gender")
    new_df["gender"] = new_df["gender"].map({"Male": 1, "Female": 0})

    encoded_nulls = [col for col in BINARY_COLS + ["gender"] if new_df[col].isna().any()]
    if encoded_nulls:
        raise ValueError(
            "Unexpected values found while encoding: " + ", ".join(encoded_nulls)
        )

    for col in ["Contract", "InternetService", "PaymentMethod"]:
        if col not in new_df.columns:
            raise ValueError(f"Missing required categorical column: {col}")

    new_df = pd.get_dummies(
        new_df,
        columns=["Contract", "InternetService", "PaymentMethod"],
        drop_first=True,
    )

    for col in feature_names:
        if col not in new_df.columns:
            new_df[col] = 0

    new_df = new_df[feature_names]
    new_df[NUMERIC_SCALE_COLS] = scaler.transform(new_df[NUMERIC_SCALE_COLS])

    if new_df.isna().any().any():
        raise ValueError("Preprocessed data still contains missing values.")

    return new_df, customer_ids


def add_model_results(
    results: pd.DataFrame,
    prefix: str,
    predictions: np.ndarray,
    probabilities: np.ndarray,
) -> None:
    results[f"{prefix}_Predicted_Churn"] = pd.Series(predictions).map({0: "No", 1: "Yes"})
    results[f"{prefix}_Churn_Probability"] = probabilities.round(3)
    results[f"{prefix}_Risk_Level"] = np.select(
        [
            results[f"{prefix}_Churn_Probability"] >= 0.70,
            results[f"{prefix}_Churn_Probability"] >= 0.40,
        ],
        ["High", "Medium"],
        default="Low",
    )


def main() -> None:
    args = parse_args()

    feature_names = load_feature_names(args.features)
    scaler = joblib.load(args.scaler)
    lr_model = load_or_train_lr(args.model, args.x_train, args.y_train)
    rf_model = load_or_train_rf(args.rf_model, args.x_train, args.y_train)
    xgb_model = load_or_train_xgb(args.xgb_model, args.x_train, args.y_train)

    new_df, customer_ids = preprocess_new_customers(args.input, feature_names, scaler)
    model_input = new_df.to_numpy()
    results = pd.DataFrame({"CustomerID": customer_ids})
    add_model_results(results, "LR", lr_model.predict(model_input), lr_model.predict_proba(model_input)[:, 1])
    add_model_results(results, "RF", rf_model.predict(model_input), rf_model.predict_proba(model_input)[:, 1])
    add_model_results(results, "XGB", xgb_model.predict(model_input), xgb_model.predict_proba(model_input)[:, 1])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.output, index=False)

    print(f"Rows scored: {len(results)}")
    print(f"Report saved: {args.output}")
    print(results)


if __name__ == "__main__":
    main()
