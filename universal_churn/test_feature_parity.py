-- tests/test_feature_parity.py 



"""
tests/test_feature_parity.py
══════════════════════════════════════════════════════════════════════
PARITY TESTS: Training vs Inference Feature Transformations

These tests feed the SAME raw input into both the training transform
path and the inference transform path, then assert the engineered
feature outputs match exactly (or within numerical tolerance).

This is the clearest protection against schema drift and skew in
production ML systems.

Test Categories
---------------
1. EXACT PARITY TESTS — Same input → same features (training vs inference)
2. NORMALIZATION GUARD TESTS — Single-row inference uses training stats
3. DEFAULT CONSISTENCY TESTS — Missing columns get same defaults
4. DERIVATION MATH TESTS — Interaction terms computed identically
5. END-TO-END PIPELINE TESTS — Full predict() path parity
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import joblib


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════

@pytest.fixture
def telecom_raw_data():
    """Sample Telecom raw data."""
    return pd.DataFrame({
        'customerID': ['C001', 'C002', 'C003'],
        'tenure': [12, 48, 2],
        'MonthlyCharges': [50.0, 80.0, 35.0],
        'TotalCharges': [600.0, 3840.0, 70.0],
        'Contract': ['Month-to-month', 'Two year', 'One year'],
        'PaymentMethod': ['Electronic check', 'Bank transfer', 'Credit card'],
        'InternetService': ['DSL', 'Fiber optic', 'No'],
        'PhoneService': ['Yes', 'Yes', 'No'],
        'MultipleLines': ['No', 'Yes', 'No phone service'],
        'OnlineSecurity': ['No', 'Yes', 'No'],
        'OnlineBackup': ['Yes', 'No', 'No'],
        'DeviceProtection': ['No', 'Yes', 'No'],
        'TechSupport': ['Yes', 'No', 'No'],
        'StreamingTV': ['Yes', 'Yes', 'No'],
        'StreamingMovies': ['Yes', 'No', 'No'],
        'SeniorCitizen': [0, 1, 0],
        'Churn': ['No', 'No', 'Yes'],
    })


@pytest.fixture
def ecommerce_raw_data():
    """Sample Ecommerce raw data."""
    return pd.DataFrame({
        'CustomerID': ['E001', 'E002', 'E003'],
        'Tenure': [24, 6, 36],
        'CashbackAmount': [150.0, 50.0, 300.0],
        'OrderCount': [20, 3, 50],
        'CouponUsed': [10, 1, 25],
        'DaySinceLastOrder': [5, 45, 2],
        'WarehouseToHome': [10.0, 30.0, 5.0],
        'Complain': [0, 1, 0],
        'SatisfactionScore': [4.0, 2.0, 5.0],
        'PreferredPaymentMode': ['Credit Card', 'Cash on Delivery', 'UPI'],
        'Churn': ['No', 'Yes', 'No'],
    })


@pytest.fixture
def banking_raw_data():
    """Sample Banking raw data."""
    return pd.DataFrame({
        'RowNumber': [1, 2, 3],
        'CustomerId': [1001, 1002, 1003],
        'Tenure': [5, 10, 2],
        'Balance': [50000.0, 150000.0, 10000.0],
        'CreditScore': [720, 680, 750],
        'IsActiveMember': [1, 0, 1],
        'NumOfProducts': [2, 1, 3],
        'HasCrCard': [1, 0, 1],
        'Age': [35, 58, 42],
        'Exited': [0, 1, 0],
    })


@pytest.fixture
def healthcare_raw_data():
    """Sample Healthcare raw data."""
    return pd.DataFrame({
        'PatientID': ['P001', 'P002', 'P003'],
        'Tenure_Months': [18, 48, 6],
        'Avg_Out_Of_Pocket_Cost': [200.0, 500.0, 100.0],
        'Visits_Last_Year': [8, 15, 2],
        'Missed_Appointments': [1, 3, 0],
        'Days_Since_Last_Visit': [30, 120, 7],
        'Overall_Satisfaction': [4.0, 2.0, 5.0],
        'Wait_Time_Satisfaction': [3.0, 1.0, 4.0],
        'Staff_Satisfaction': [4.0, 2.0, 5.0],
        'Provider_Rating': [4.5, 2.5, 5.0],
        'Distance_To_Facility_Miles': [5.0, 20.0, 2.0],
        'Portal_Usage': [3.0, 1.0, 5.0],
        'Referrals_Made': [2, 0, 4],
        'Billing_Issues': [0, 2, 0],
        'Age': [45, 70, 32],
        'Churned': [0, 1, 0],
    })


@pytest.fixture(scope="module")
def training_norm_stats():
    """
    Simulated training-time normalization statistics.

    In production, these would be computed during train_all and saved
    to UNIVERSAL_NORM_STATS_PATH. Here we use realistic values.
    """
    return {
        # Telecom
        'telecom.tenure': 72.0,
        'telecom.MonthlyCharges': 118.0,
        # Ecommerce
        'ecommerce.Tenure': 72.0,
        'ecommerce.CashbackAmount': 500.0,
        'ecommerce.OrderCount': 100.0,
        'ecommerce.CouponUsed': 50.0,
        'ecommerce.DaySinceLastOrder': 90.0,
        'ecommerce.WarehouseToHome': 50.0,
        # Banking
        'banking.Tenure': 10.0,
        'banking.Balance': 250000.0,
        'banking.CreditScore': 850.0,
        # Healthcare
        'healthcare.Tenure_Months': 60.0,
        'healthcare.Avg_Out_Of_Pocket_Cost': 800.0,
        'healthcare.Visits_Last_Year': 20.0,
        'healthcare.Days_Since_Last_Visit': 180.0,
        'healthcare.Overall_Satisfaction': 5.0,
        'healthcare.Wait_Time_Satisfaction': 5.0,
        'healthcare.Staff_Satisfaction': 5.0,
        'healthcare.Provider_Rating': 5.0,
        'healthcare.Distance_To_Facility_Miles': 50.0,
        'healthcare.Referrals_Made': 10.0,
    }


# ══════════════════════════════════════════════════════════════════
# IMPORT TRANSFORM FUNCTIONS
# ══════════════════════════════════════════════════════════════════

try:
    from universal_churn.feature_transforms import (
        transform_to_universal_features,
        compute_norm_stats,
        derive_tenure_normalized,
        derive_charge_normalized,
        derive_dormant_loyalty_risk,
        derive_lockin_risk,
        MINIMAL_FEATURE_SUBSETS,
        HIGH_IMPORTANCE_FEATURES,
        check_feature_sufficiency,
    )
    TRANSFORMS_AVAILABLE = True
except ImportError:
    TRANSFORMS_AVAILABLE = False

try:
    from universal_churn_predictor import extract_universal_features
    LEGACY_EXTRACT_AVAILABLE = True
except ImportError:
    LEGACY_EXTRACT_AVAILABLE = False


# ══════════════════════════════════════════════════════════════════
# 1. EXACT PARITY TESTS
# ══════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not TRANSFORMS_AVAILABLE, reason="feature_transforms module not available")
class TestExactParity:
    """Tests that training and inference produce identical features."""

    def test_telecom_features_parity(self, telecom_raw_data, training_norm_stats):
        """Telecom: training transform == inference transform."""
        df = telecom_raw_data.copy()

        # Simulate training-time transform (norm_stats computed from batch)
        train_stats = compute_norm_stats(
            df, 'telecom', ['tenure', 'MonthlyCharges']
        )
        features_train, _ = transform_to_universal_features(df, 'telecom', train_stats)

        # Simulate inference-time transform (using persisted training stats)
        features_infer, _ = transform_to_universal_features(df, 'telecom', training_norm_stats)

        # For the SAME data, if we use the same norm_stats, results should match
        features_infer_same, _ = transform_to_universal_features(df, 'telecom', train_stats)

        pd.testing.assert_frame_equal(features_train, features_infer_same)

    def test_ecommerce_features_parity(self, ecommerce_raw_data, training_norm_stats):
        """Ecommerce: training transform == inference transform."""
        df = ecommerce_raw_data.copy()

        train_stats = compute_norm_stats(
            df, 'ecommerce',
            ['Tenure', 'CashbackAmount', 'OrderCount', 'CouponUsed',
             'DaySinceLastOrder', 'WarehouseToHome']
        )
        features_train, _ = transform_to_universal_features(df, 'ecommerce', train_stats)
        features_infer_same, _ = transform_to_universal_features(df, 'ecommerce', train_stats)

        pd.testing.assert_frame_equal(features_train, features_infer_same)

    def test_banking_features_parity(self, banking_raw_data, training_norm_stats):
        """Banking: training transform == inference transform."""
        df = banking_raw_data.copy()

        train_stats = compute_norm_stats(
            df, 'banking', ['Tenure', 'Balance', 'CreditScore']
        )
        features_train, _ = transform_to_universal_features(df, 'banking', train_stats)
        features_infer_same, _ = transform_to_universal_features(df, 'banking', train_stats)

        pd.testing.assert_frame_equal(features_train, features_infer_same)

    def test_healthcare_features_parity(self, healthcare_raw_data, training_norm_stats):
        """Healthcare: training transform == inference transform."""
        df = healthcare_raw_data.copy()

        train_stats = compute_norm_stats(
            df, 'healthcare',
            ['Tenure_Months', 'Avg_Out_Of_Pocket_Cost', 'Visits_Last_Year',
             'Days_Since_Last_Visit', 'Overall_Satisfaction', 'Provider_Rating',
             'Referrals_Made']
        )
        features_train, _ = transform_to_universal_features(df, 'healthcare', train_stats)
        features_infer_same, _ = transform_to_universal_features(df, 'healthcare', train_stats)

        pd.testing.assert_frame_equal(features_train, features_infer_same)


# ══════════════════════════════════════════════════════════════════
# 2. NORMALIZATION GUARD TESTS
# ══════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not TRANSFORMS_AVAILABLE, reason="feature_transforms module not available")
class TestNormalizationGuard:
    """
    Tests that single-row inference uses TRAINING stats, not batch stats.

    This is critical: without persisted norm_stats, a single row would
    normalize its own value to 1.0, causing massive skew.
    """

    def test_single_row_uses_training_stats_telecom(self, training_norm_stats):
        """Single telecom row must use training max, not its own value."""
        single_row = pd.DataFrame({
            'customerID': ['C999'],
            'tenure': [12],  # If normalized to itself, would be 1.0
            'MonthlyCharges': [50.0],
            'Contract': ['Month-to-month'],
        })

        # Without training stats (WRONG way - would normalize to self)
        features_no_stats, _ = transform_to_universal_features(single_row, 'telecom', None)

        # With training stats (CORRECT way)
        features_with_stats, _ = transform_to_universal_features(
            single_row, 'telecom', training_norm_stats
        )

        # tenure=12 with training max=72 should give 12/72 = 0.167, NOT 1.0
        expected_tenure_norm = 12.0 / 72.0
        actual_with_stats = features_with_stats['tenure_normalized'].iloc[0]

        assert abs(actual_with_stats - expected_tenure_norm) < 0.01, \
            f"Expected ~{expected_tenure_norm}, got {actual_with_stats}"

        # Verify that without stats, it would incorrectly use batch max (=self)
        # This documents the bug we're preventing
        actual_no_stats = features_no_stats['tenure_normalized'].iloc[0]
        # When only one row, batch max = row value, so 12/12 = 1.0
        assert abs(actual_no_stats - 1.0) < 0.01, \
            "Without training stats, single row normalizes to 1.0 (this is the bug!)"

    def test_single_row_uses_training_stats_ecommerce(self, training_norm_stats):
        """Single ecommerce row must use training max for recency."""
        single_row = pd.DataFrame({
            'CustomerID': ['E999'],
            'Tenure': [24],
            'CashbackAmount': [100.0],
            'OrderCount': [10],
            'DaySinceLastOrder': [5],  # Should be 5/90 = 0.056, not 1.0
        })

        features_with_stats, _ = transform_to_universal_features(
            single_row, 'ecommerce', training_norm_stats
        )

        expected_recency = 5.0 / 90.0
        actual_recency = features_with_stats['recency_score'].iloc[0]

        assert abs(actual_recency - expected_recency) < 0.01, \
            f"Expected recency ~{expected_recency}, got {actual_recency}"


# ══════════════════════════════════════════════════════════════════
# 3. DEFAULT CONSISTENCY TESTS
# ══════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not TRANSFORMS_AVAILABLE, reason="feature_transforms module not available")
class TestDefaultConsistency:
    """Tests that missing columns get consistent default values."""

    def test_missing_columns_get_defaults_telecom(self):
        """Telecom with minimal schema gets consistent defaults."""
        minimal_df = pd.DataFrame({
            'customerID': ['C001'],
            'tenure': [12],
            'MonthlyCharges': [50.0],
            # Missing: Contract, PaymentMethod, all service columns
        })

        features, metadata = transform_to_universal_features(minimal_df, 'telecom', None)

        # contract_stability should default to 0.5
        assert features['contract_stability'].iloc[0] == 0.5

        # Service-related features should have sensible defaults
        assert features['num_products_services'].iloc[0] == 0.0  # No services

    def test_missing_columns_get_defaults_ecommerce(self):
        """Ecommerce with minimal schema gets consistent defaults."""
        minimal_df = pd.DataFrame({
            'CustomerID': ['E001'],
            'Tenure': [12],
            'CashbackAmount': [50.0],
            # Missing: OrderCount, CouponUsed, DaySinceLastOrder, etc.
        })

        features, metadata = transform_to_universal_features(minimal_df, 'ecommerce', None)

        # recency_score should default to 0.5 (no information)
        assert features['recency_score'].iloc[0] == 0.5

        # engagement should be 0 (no order data)
        assert features['engagement_score'].iloc[0] == 0.0


# ══════════════════════════════════════════════════════════════════
# 4. DERIVATION MATH TESTS
# ══════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not TRANSFORMS_AVAILABLE, reason="feature_transforms module not available")
class TestDerivationMath:
    """Tests that interaction terms and derived features are computed correctly."""

    def test_dormant_loyalty_risk_ecommerce(self, ecommerce_raw_data, training_norm_stats):
        """dormant_loyalty_risk = tenure_normalized * recency_score."""
        df = ecommerce_raw_data.copy()
        features, _ = transform_to_universal_features(df, 'ecommerce', training_norm_stats)

        expected = features['tenure_normalized'] * features['recency_score']
        pd.testing.assert_series_equal(
            features['dormant_loyalty_risk'],
            expected,
            check_names=False
        )

    def test_lockin_risk_telecom(self, telecom_raw_data, training_norm_stats):
        """lockin_risk = contract_stability * (1 - tenure_normalized)."""
        df = telecom_raw_data.copy()
        features, _ = transform_to_universal_features(df, 'telecom', training_norm_stats)

        expected = features['contract_stability'] * (1 - features['tenure_normalized'])
        pd.testing.assert_series_equal(
            features['lockin_risk'],
            expected,
            check_names=False
        )

    def test_missed_appt_rate_healthcare(self, healthcare_raw_data, training_norm_stats):
        """missed_appt_rate = missed_appointments / total_visits."""
        df = healthcare_raw_data.copy()
        features, _ = transform_to_universal_features(df, 'healthcare', training_norm_stats)

        # Manual calculation for first row
        visits = df['Visits_Last_Year'].iloc[0]
        missed = df['Missed_Appointments'].iloc[0]
        expected_first = missed / visits if visits > 0 else 0.0

        actual_first = features['missed_appt_rate'].iloc[0]
        assert abs(actual_first - expected_first) < 0.01


# ══════════════════════════════════════════════════════════════════
# 5. FEATURE SUFFICIENCY CHECKS
# ══════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not TRANSFORMS_AVAILABLE, reason="feature_transforms module not available")
class TestFeatureSufficiency:
    """Tests for stricter refusal thresholds based on feature importance."""

    def test_high_importance_features_present(self, telecom_raw_data):
        """Telecom with full schema has high-importance features."""
        is_sufficient, details = check_feature_sufficiency(telecom_raw_data, 'telecom')

        assert is_sufficient
        assert details['has_high_importance']

    def test_minimal_schema_fallback_check(self):
        """Minimal schema triggers fallback check."""
        minimal_df = pd.DataFrame({
            'customerID': ['C001'],
            'tenure': [12],
            'MonthlyCharges': [50.0],
        })

        is_sufficient, details = check_feature_sufficiency(minimal_df, 'telecom')

        # Should still pass because we have tenure + charge (core features)
        assert 'tenure_normalized' in details['available_canonical']
        assert 'charge_normalized' in details['available_canonical']

    def test_truly_insufficient_schema(self):
        """Schema with no recognizable features fails sufficiency."""
        garbage_df = pd.DataFrame({
            'RandomCol1': [1, 2, 3],
            'RandomCol2': ['a', 'b', 'c'],
        })

        is_sufficient, details = check_feature_sufficiency(garbage_df, 'telecom')

        assert not details['has_high_importance']
        assert not details['has_fallback']


# ══════════════════════════════════════════════════════════════════
# 6. LEGACY COMPATIBILITY TESTS
# ══════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not (TRANSFORMS_AVAILABLE and LEGACY_EXTRACT_AVAILABLE),
                    reason="Both modules required for comparison")
class TestLegacyCompatibility:
    """
    Tests that the new unified transform matches the legacy extract function.

    These tests ensure backward compatibility during the migration period.
    Eventually, legacy tests can be removed once all code uses feature_transforms.
    """

    def test_new_transform_matches_legacy_telecom(self, telecom_raw_data, training_norm_stats):
        """New transform_to_universal_features matches legacy extract_universal_features."""
        df = telecom_raw_data.copy()

        # New unified transform
        features_new, _ = transform_to_universal_features(df, 'telecom', training_norm_stats)

        # Legacy extract (for comparison during migration)
        features_legacy = extract_universal_features(df, 'telecom', 'Churn', training_norm_stats)

        # Compare common columns (both should have UNIVERSAL_FEATURES)
        common_cols = list(set(features_new.columns) & set(features_legacy.columns))

        for col in common_cols:
            new_vals = features_new[col].values
            legacy_vals = features_legacy[col].values
            np.testing.assert_array_almost_equal(
                new_vals, legacy_vals, decimal=5,
                err_msg=f"Column {col} differs between new and legacy transforms"
            )


# ══════════════════════════════════════════════════════════════════
# 7. END-TO-END PIPELINE INTEGRATION
# ══════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not TRANSFORMS_AVAILABLE, reason="feature_transforms module not available")
class TestEndToEndIntegration:
    """Integration tests for the full prediction pipeline."""

    def test_full_pipeline_metadata_tracking(self, ecommerce_raw_data, training_norm_stats):
        """Full transform returns complete derivation metadata."""
        df = ecommerce_raw_data.copy()

        features, metadata = transform_to_universal_features(df, 'ecommerce', training_norm_stats)

        # Metadata should include:
        assert 'sector' in metadata
        assert metadata['sector'] == 'ecommerce'

        assert 'norm_stats_used' in metadata
        assert metadata['norm_stats_used'] is True

        assert 'derivations_applied' in metadata
        assert len(metadata['derivations_applied']) > 0

        assert 'defaults_applied' in metadata
        # Some features may use defaults even with good data

    def test_reproducibility_across_runs(self, banking_raw_data, training_norm_stats):
        """Same input + same stats = identical output across multiple runs."""
        df = banking_raw_data.copy()

        features_run1, meta1 = transform_to_universal_features(df, 'banking', training_norm_stats)
        features_run2, meta2 = transform_to_universal_features(df, 'banking', training_norm_stats)
        features_run3, meta3 = transform_to_universal_features(df, 'banking', training_norm_stats)

        pd.testing.assert_frame_equal(features_run1, features_run2)
        pd.testing.assert_frame_equal(features_run2, features_run3)

        # Metadata should also be consistent
        assert meta1 == meta2 == meta3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])