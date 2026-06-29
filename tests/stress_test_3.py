import os
import pytest
import pandas as pd
import numpy as np
from pathlib import Path

# Import pipeline functions from your file
from universal_churn_predictor import predict_universal, SECTOR_CONFIG

def test_telecom_boundary_values(tmp_path):
    df = pd.DataFrame({
        "customerID": ["T1", "T2", "T3"],
        "tenure": [0, -1, 9999],
        "InternetService": ["Fiber optic", "No", "DSL"],
        "Contract": ["Month-to-month", "Two year", "One year"],
        "MonthlyCharges": [0, 99999, 85.5],
        "TotalCharges": [0, 10, 1026]
    })
    path = tmp_path / "telecom_boundary.csv"
    df.to_csv(path, index=False)

    results = predict_universal(str(path), force_sector="telecom")
    assert not results.empty
    assert results["Churn_Probability"].between(0, 1).all()

def test_healthcare_invalid_and_extreme_values(tmp_path):
    df = pd.DataFrame({
        "PatientID": ["H1", "H2", "H3"],
        "Age": [0, -5, 150],
        "Visits_Last_Year": [0, 500, "14 visits"],
        "Avg_Out_Of_Pocket_Cost": [0, 999999, "₹450"],
        "Billing_Issues": [0, 99, 5],
        "Last_Interaction_Date": ["2025-01-10", "invalid", "2026-05-12"]
    })
    path = tmp_path / "healthcare_boundary.csv"
    df.to_csv(path, index=False)

    results = predict_universal(str(path), force_sector="healthcare")
    assert not results.empty
    assert results["Churn_Probability"].between(0, 1).all()

