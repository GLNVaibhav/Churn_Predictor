import os
import pytest
import pandas as pd
import numpy as np
from pathlib import Path

# Import pipeline functions from your file
from universal_churn_predictor import predict_universal, SECTOR_CONFIG

def test_single_row_input(tmp_path):
    df = pd.DataFrame({
        "customerID": ["T1"],
        "tenure": [12],
        "InternetService": ["Fiber optic"],
        "Contract": ["Month-to-month"],
        "MonthlyCharges": [85.5],
        "TotalCharges": [1026.0]
    })
    path = tmp_path / "single_row.csv"
    df.to_csv(path, index=False)

    results = predict_universal(str(path), force_sector="telecom")
    assert not results.empty
    assert len(results) == 1

def test_mixed_valid_and_invalid_rows(tmp_path):
    df = pd.DataFrame({
        "customerID": ["T1", "T2", "T3"],
        "tenure": [12, "bad", 70],
        "InternetService": ["Fiber optic", "No", "DSL"],
        "Contract": ["Month-to-month", "Two year", "One year"],
        "MonthlyCharges": [85.5, 20.0, None],
        "TotalCharges": [1026.0, 1400.0, 500.0]
    })
    path = tmp_path / "mixed_rows.csv"
    df.to_csv(path, index=False)

    results = predict_universal(str(path), force_sector="telecom")
    assert not results.empty

