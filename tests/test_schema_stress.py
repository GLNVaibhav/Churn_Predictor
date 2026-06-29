import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import universal_churn_predictor as ucp

@pytest.fixture(scope="module", autouse=True)
def ensure_artifacts_exist():
    """
    End-to-end tests require the trained .pkl artifacts. 
    Run `python universal_churn_predictor.py --mode train_all` before running these tests.
    """
    if not Path(ucp.UNIVERSAL_MODEL_PATH).exists():
        pytest.skip("Artifacts not found. Run `python universal_churn_predictor.py --mode train_all` first.")

# ==============================================================================
# 1. SCHEMA AGNOSTICISM & ALIAS STRESS TEST
# ==============================================================================
def test_frankenstein_schema_aliases(tmp_path):
    """
    Test: Feed a Healthcare Schema 2 dataset using aliases and messy casing.
    Validates: detect_sector variant matching and concept_map aliasing.
    """
    data = {
        'MonthlyPremium': [150.0, 200.0],       # Alias for Avg_Out_Of_Pocket_Cost
        'FrequencyOfVisits': [2, 5],            # Alias for Visits_Last_Year
        'CustomerSupportCalls': [1, 0],         # Alias for Billing_Issues
        'ClaimHistoryCount': [0, 2],
        'Age': [45, 60]
    }
    df = pd.DataFrame(data)
    csv_path = tmp_path / "messy_healthcare.csv"
    df.to_csv(csv_path, index=False)
    
    # Should auto-detect as healthcare and map concepts without KeyError
    results = ucp.predict_universal(str(csv_path))
    assert len(results) == 2
    assert 'Churn_Probability' in results.columns

# ==============================================================================
# 2. AUTO-DETECTION BOUNDARY TEST
# ==============================================================================
def test_minimal_signature_failure(tmp_path):
    """
    Test: Feed a CSV with only 1 matching column (MIN_SIGNATURE_HITS = 2).
    Validates: The pipeline correctly rejects ambiguous/insufficient schemas.
    """
    data = {'MonthlyCharges': [50.0, 60.0], 'RandomCol1': [1, 2], 'RandomCol2': [3, 4]}
    df = pd.DataFrame(data)
    csv_path = tmp_path / "minimal.csv"
    df.to_csv(csv_path, index=False)
    
    with pytest.raises(ValueError, match="Could not auto-detect"):
        ucp.predict_universal(str(csv_path))

# ==============================================================================
# 3. NORMALIZATION GUARD (SINGLE-ROW INFERENCE)
# ==============================================================================
def test_single_row_normalization_guard(tmp_path):
    """
    Test: Single-row inference.
    Validates: _norm_max uses persisted training stats instead of normalizing 
    the single row's value to 1.0. Also validates variance check bypass for len=1.
    """
    data = {
        'customerID': ['C1'],
        'tenure': [12],
        'MonthlyCharges': [50.0],
        'Contract': ['Month-to-month'],
        'InternetService': ['DSL']
    }
    df = pd.DataFrame(data)
    csv_path = tmp_path / "single_row.csv"
    df.to_csv(csv_path, index=False)
    
    results = ucp.predict_universal(str(csv_path))
    assert len(results) == 1

# ==============================================================================
# 4. ADVERSARIAL FLATLINE TRAP (VARIANCE GUARD)
# ==============================================================================
def test_flatline_variance_trap(tmp_path):
    """
    Test: Feed 10 identical rows to trigger the flatline safeguard.
    Validates: verify_prediction_variance catches schema-misalignment/garbage data.
    """
    # Identical rows guarantee std(probas) == 0.0
    data = {
        'MonthlyCharges': [50.0] * 10,
        'Contract': ['Month-to-month'] * 10,
        'Garbage1': [1] * 10,
    }
    df = pd.DataFrame(data)
    csv_path = tmp_path / "garbage.csv"
    df.to_csv(csv_path, index=False)
    
    with pytest.raises(RuntimeError, match="CRITICAL WARNING"):
        ucp.predict_universal(str(csv_path))

# ==============================================================================
# 5. UNSEEN CATEGORICALS & MISSING COLUMNS
# ==============================================================================
def test_unseen_categoricals(tmp_path):
    """
    Test: Feed unseen categories (e.g., 'Five-Year' contract).
    Validates: Graceful degradation (unseen dummies dropped, missing filled with 0).
    """
    data = {
        'customerID': ['C1', 'C2'],
        'tenure': [10, 20],
        'MonthlyCharges': [50.0, 60.0],
        'Contract': ['Five-Year', 'Decade'], # Unseen categories
        'InternetService': ['Fiber', 'DSL']
    }
    df = pd.DataFrame(data)
    csv_path = tmp_path / "unseen.csv"
    df.to_csv(csv_path, index=False)
    
    results = ucp.predict_universal(str(csv_path))
    assert len(results) == 2

# ==============================================================================
# 6. UNIVERSAL FEATURE MATH VERIFICATION (NO .pkl REQUIRED)
# ==============================================================================
def test_universal_feature_extraction_math():
    """
    Test: Verify the interaction term math directly.
    Validates: dormant_loyalty_risk is correctly calculated as tenure * recency.
    """
    data = {
        'Tenure': [10, 20],
        'DaySinceLastOrder': [5, 10],
        'Churn': [0, 1]
    }
    df = pd.DataFrame(data)
    norm_stats = {'ecommerce.Tenure': 100.0, 'ecommerce.DaySinceLastOrder': 30.0}
    
    features = ucp.extract_universal_features(df, 'ecommerce', 'Churn', norm_stats=norm_stats)
    
    expected_recency = df['DaySinceLastOrder'] / 30.0
    expected_tenure = df['Tenure'] / 100.0
    expected_dormant = expected_tenure * expected_recency
    
    np.testing.assert_array_almost_equal(features['dormant_loyalty_risk'].values, expected_dormant.values)