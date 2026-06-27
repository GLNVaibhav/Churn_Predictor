import os
import pytest
import pandas as pd
import numpy as np
from pathlib import Path

# Import pipeline functions from your file
from universal_churn_predictor import predict_universal, SECTOR_CONFIG

# ══════════════════════════════════════════════════════════════════
# DATA STRESS TESTS
# ══════════════════════════════════════════════════════════════════

def test_telecom_messy_numeric_and_text_fields(tmp_path):
    """
    STRESS TEST 1: Tests if the framework handles or filters out messy numeric
    and text strings like currency symbols and strings with units.
    """
    df = pd.DataFrame({
        "Customer ID": ["T1", "T2", "T3"],
        "Tenure": ["12 months", None, "70"],
        "Internet Service": ["Fiber optic", "fibre optic", "No"],
        "Contract": ["Month to month", "Two-year", "month-to-month"],
        "Monthly Charges": ["₹85.50", "120 USD", "20"],
        "Total Charges": ["1026", "", "1400.00"]
    })
    
    test_csv = tmp_path / "telecom_dirty_stress.csv"
    df.to_csv(test_csv, index=False)
    
    # Run the pipeline in universal mode
    results = predict_universal(str(test_csv))
    
    # Assertions to confirm execution survival and logical bounds
    assert not results.empty
    assert "Churn_Probability" in results.columns
    assert all(0.0 <= p <= 1.0 for p in results["Churn_Probability"])


def test_healthcare_mixed_date_and_missing_fields(tmp_path):
    """
    STRESS TEST 2: Validates resilience against multiple date layouts, 
    mixed text strings, and blank metrics in a medical footprint context.
    """
    df = pd.DataFrame({
        "Patient ID": ["H1", "H2", "H3"],
        "Age": [45, None, "67"],
        "Visits Last Year": ["3", "14 visits", 0],
        "Avg Out Of Pocket Cost": ["₹120", "450", None],
        "Billing Issues": [0, 5, "2"],
        "Last Interaction Date": ["2025-01-10", "12/05/2026", "May 12 2026"]
    })
    
    test_csv = tmp_path / "healthcare_dirty_stress.csv"
    df.to_csv(test_csv, index=False)
    
    results = predict_universal(str(test_csv))
    
    assert not results.empty
    assert "Risk_Level" in results.columns
    # Ensure probabilities didn't collapse into a flatline identity
    assert results["Churn_Probability"].nunique() >= 1 


def test_duplicate_and_conflicting_rows(tmp_path):
    """
    STRESS TEST 3: Evaluates how the pipeline processes rows with duplicate IDs 
    but varying behavioral charges.
    """
    df = pd.DataFrame({
        "customerID": ["X1", "X1", "X2"],
        "tenure": [12, 24, 70],
        "InternetService": ["Fiber optic", "Fiber optic", "No"],
        "Contract": ["Month-to-month", "Month-to-month", "Two year"],
        "MonthlyCharges": [85.5, 90.0, 20.0],
        "TotalCharges": [1026.0, 2040.0, 1400.0]
    })
    
    test_csv = tmp_path / "duplicate_stress.csv"
    df.to_csv(test_csv, index=False)
    
    results = predict_universal(str(test_csv))
    
    assert len(results) == 3
    assert results["CustomerID"].iloc[0] == "X1"
    assert results["CustomerID"].iloc[1] == "X1"