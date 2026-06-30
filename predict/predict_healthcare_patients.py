import pandas as pd
import numpy as np
import joblib

# --------------------------------------------------
# Load Models & Artifacts
# --------------------------------------------------

lr_model = joblib.load(
    'outputs/lr_model_healthcare.pkl'
)

rf_model = joblib.load(
    'outputs/rf_model_healthcare.pkl'
)

xgb_model = joblib.load(
    'outputs/xgb_model_healthcare.pkl'
)

scaler = joblib.load(
    'outputs/scaler_healthcare.pkl'
)

encoders = joblib.load(
    'outputs/healthcare_encoders.pkl'
)

feature_names = pd.read_csv(
    'outputs/healthcare_feature_names.csv'
).iloc[:,0].tolist()

# --------------------------------------------------
# Load New Patients
# --------------------------------------------------

df = pd.read_csv(
    'data/healthcare/healthcare_new_patients.csv'
)

customer_ids = df['PatientID'].copy()

# --------------------------------------------------
# Remove Non-Feature Columns
# --------------------------------------------------
    
drop_cols = [
    'PatientID',
    'Last_Interaction_Date'
]

for col in drop_cols:
    if col in df.columns:
        df.drop(columns=[col], inplace=True)

# --------------------------------------------------
# Encode Categoricals
# --------------------------------------------------

cat_cols = [
    'Gender',
    'State',
    'Specialty',
    'Insurance_Type'
]

def safe_label_transform(series, encoder, col_name):

    label_map = {
        label: idx
        for idx, label in enumerate(encoder.classes_)
    }

    values = series.astype(str)
    unknown_values = sorted(
        set(values) - set(label_map)
    )

    if unknown_values:
        print(
            f"Warning: Unseen labels in {col_name}: {unknown_values}. "
            "Encoding as -1."
        )

    return values.map(label_map).fillna(-1).astype(int)

for col in cat_cols:

    le = encoders[col]

    df[col] = safe_label_transform(
        df[col],
        le,
        col
    )

# --------------------------------------------------
# Scale Numerical Features
# --------------------------------------------------

scale_cols = [
    'Age',
    'Tenure_Months',
    'Visits_Last_Year',
    'Missed_Appointments',
    'Days_Since_Last_Visit',
    'Overall_Satisfaction',
    'Wait_Time_Satisfaction',
    'Staff_Satisfaction',
    'Provider_Rating',
    'Avg_Out_Of_Pocket_Cost',
    'Billing_Issues',
    'Portal_Usage',
    'Referrals_Made',
    'Distance_To_Facility_Miles'
]

df[scale_cols] = scaler.transform(
    df[scale_cols]
)

# --------------------------------------------------
# Match Training Feature Order
# --------------------------------------------------

for col in feature_names:

    if col not in df.columns:
        df[col] = 0

df = df[feature_names]

# --------------------------------------------------
# Predictions
# --------------------------------------------------

results = pd.DataFrame()

results['PatientID'] = customer_ids

# LR

lr_pred = lr_model.predict(df)
lr_prob = lr_model.predict_proba(df)[:,1]

results['LR_Prediction'] = np.where(
    lr_pred == 1,
    'Churn',
    'No Churn'
)

results['LR_Probability'] = lr_prob.round(3)

# RF

rf_pred = rf_model.predict(df)
rf_prob = rf_model.predict_proba(df)[:,1]

results['RF_Prediction'] = np.where(
    rf_pred == 1,
    'Churn',
    'No Churn'
)

results['RF_Probability'] = rf_prob.round(3)

# XGB

xgb_pred = xgb_model.predict(df)
xgb_prob = xgb_model.predict_proba(df)[:,1]

results['XGB_Prediction'] = np.where(
    xgb_pred == 1,
    'Churn',
    'No Churn'
)

results['XGB_Probability'] = xgb_prob.round(3)

# --------------------------------------------------
# Majority Vote
# --------------------------------------------------

def majority_vote(row):

    votes = [
        row['LR_Prediction'],
        row['RF_Prediction'],
        row['XGB_Prediction']
    ]

    churn_votes = votes.count('Churn')

    if churn_votes >= 2:
        return 'Churn'

    return 'No Churn'

results['Majority_Vote'] = results.apply(
    majority_vote,
    axis=1
)

# --------------------------------------------------
# Save Results
# --------------------------------------------------

results.to_csv(
    'outputs/results/healthcare_predictions.csv',
    index=False
)

print("\nHealthcare Predictions")
print("="*100)

print(
    results.to_string(index=False)
)

print("="*100)

print(
    "\nResults saved to:"
)

print(
    "outputs/results/healthcare_predictions.csv"
)
