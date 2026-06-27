import os
import pytest
import pandas as pd
import numpy as np
from pathlib import Path

# Import pipeline functions from your file
from universal_churn_predictor import predict_universal, SECTOR_CONFIG

def test_column_order_and_extra_columns(tmp_path):
    df = pd.DataFrame({
        "Extra_Notes": ["x", "y"],
        "TotalCharges": [1026.0, 1400.0],
        "MonthlyCharges": [85.5, 20.0],
        "Contract": ["Month-to-month", "Two year"],
        "InternetService": ["Fiber optic", "No"],
        "tenure": [12, 70],
        "customerID": ["T1", "T2"]
    })
    path = tmp_path / "telecom_reordered.csv"
    df.to_csv(path, index=False)

    results = predict_universal(str(path), force_sector="telecom")
    assert not results.empty
    assert results["Churn_Probability"].between(0, 1).all()

def test_unknown_and_null_markers(tmp_path):
    df = pd.DataFrame({
        "customerID": ["T1", "T2", "T3"],
        "tenure": [12, "NA", None],
        "InternetService": ["unknown", "Fiber optic", ""],
        "Contract": ["Month-to-month", None, "Two year"],
        "MonthlyCharges": [85.5, "?", 20.0],
        "TotalCharges": [1026.0, 1400.0, "null"]
    })
    path = tmp_path / "unknowns.csv"
    df.to_csv(path, index=False)

    results = predict_universal(str(path))
    assert not results.empty
    assert results["Churn_Probability"].between(0, 1).all()

def test_healthcare_conflicting_duplicate_patient_ids(tmp_path):
    df = pd.DataFrame({
        "PatientID": ["P1", "P1", "P2"],
        "Age": [45, 46, 67],
        "Visits_Last_Year": [3, 14, 2],
        "Avg_Out_Of_Pocket_Cost": [120.0, 450.0, 80.0],
        "Billing_Issues": [0, 5, 1],
        "Last_Interaction_Date": ["2025-01-10", "2026-05-12", "2026-01-01"]
    })
    path = tmp_path / "patient_conflicts.csv"
    df.to_csv(path, index=False)

    results = predict_universal(str(path), force_sector="healthcare")
    assert not results.empty
    assert results["Churn_Probability"].between(0, 1).all()

    