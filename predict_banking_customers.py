from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.preprocessing import LabelEncoder

# --------------------------------------------------
# Paths
# --------------------------------------------------

INPUT_FILE = Path(
    "data/banking/banking_new_customers.csv"
)

OUTPUT_FILE = Path(
    "outputs/results/banking_predictions.csv"
)

# --------------------------------------------------
# Load Models
# --------------------------------------------------

print("Loading models...")

lr_model = joblib.load(
    "outputs/lr_model_banking.pkl"
)

rf_model = joblib.load(
    "outputs/rf_model_banking.pkl"
)

xgb_model = joblib.load(
    "outputs/xgb_model_banking.pkl"
)

scaler = joblib.load(
    "outputs/scaler_banking.pkl"
)

feature_names = pd.read_csv(
    "outputs/banking_feature_names.csv"
).iloc[:, 0].tolist()

print("Models loaded successfully.")

# --------------------------------------------------
# Load Data
# --------------------------------------------------

df = pd.read_csv(INPUT_FILE)

customer_ids = df["CustomerId"].copy()

# --------------------------------------------------
# Drop Identifier
# --------------------------------------------------

df.drop(
    columns=["CustomerId"],
    inplace=True
)

# --------------------------------------------------
# Encode Categoricals
# --------------------------------------------------

cat_cols = [
    "Geography",
    "Gender"
]

for col in cat_cols:

    le = LabelEncoder()

    df[col] = le.fit_transform(
        df[col].astype(str)
    )

# --------------------------------------------------
# Scale Numerical Features
# --------------------------------------------------

scale_cols = [
    "CreditScore",
    "Age",
    "Tenure",
    "Balance",
    "NumOfProducts",
    "EstimatedSalary"
]

df[scale_cols] = scaler.transform(
    df[scale_cols]
)

# --------------------------------------------------
# Match Training Features
# --------------------------------------------------

for col in feature_names:

    if col not in df.columns:
        df[col] = 0

df = df[feature_names]

# --------------------------------------------------
# Predictions
# --------------------------------------------------

results = pd.DataFrame()

results["CustomerId"] = customer_ids

# Logistic Regression

lr_pred = lr_model.predict(df)

lr_prob = lr_model.predict_proba(df)[:,1]

results["LR_Prediction"] = np.where(
    lr_pred == 1,
    "Exited",
    "Retained"
)

results["LR_Probability"] = lr_prob.round(3)

# Random Forest

rf_pred = rf_model.predict(df)

rf_prob = rf_model.predict_proba(df)[:,1]

results["RF_Prediction"] = np.where(
    rf_pred == 1,
    "Exited",
    "Retained"
)

results["RF_Probability"] = rf_prob.round(3)

# XGBoost

xgb_pred = xgb_model.predict(df)

xgb_prob = xgb_model.predict_proba(df)[:,1]

results["XGB_Prediction"] = np.where(
    xgb_pred == 1,
    "Exited",
    "Retained"
)

results["XGB_Probability"] = xgb_prob.round(3)

# --------------------------------------------------
# Majority Vote
# --------------------------------------------------

def majority_vote(row):

    votes = [
        row["LR_Prediction"],
        row["RF_Prediction"],
        row["XGB_Prediction"]
    ]

    exited_votes = votes.count("Exited")

    if exited_votes >= 2:
        return "Exited"

    return "Retained"

results["Majority_Vote"] = results.apply(
    majority_vote,
    axis=1
)

# --------------------------------------------------
# Risk Levels
# --------------------------------------------------

avg_prob = (
    results["LR_Probability"] +
    results["RF_Probability"] +
    results["XGB_Probability"]
) / 3

results["Average_Probability"] = avg_prob.round(3)

results["Risk"] = np.select(
    [
        avg_prob >= 0.70,
        avg_prob >= 0.40
    ],
    [
        "High",
        "Medium"
    ],
    default="Low"
)

# --------------------------------------------------
# Save
# --------------------------------------------------

OUTPUT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)

results.to_csv(
    OUTPUT_FILE,
    index=False
)

print("\nBanking Predictions")
print("=" * 120)

print(
    results.to_string(index=False)
)

print("=" * 120)

print(
    f"\nResults saved to: {OUTPUT_FILE}"
)