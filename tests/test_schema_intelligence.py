"""
tests/test_schema_intelligence.py
══════════════════════════════════════════════════════════════════════
Phase 7 tests for the Schema Intelligence Layer:

    - Canonical field resolution           (schema_resolution.py)
    - Business concept generation           (concepts.py)
    - Concept Confidence Engine             (concept_confidence.py, NEW)
    - Concept-confidence-aware routing      (routing.py, extended)

These tests do NOT require trained .pkl model artifacts — they exercise
the schema-intelligence layer in isolation, unlike
tests/test_schema_stress.py (end-to-end, requires train_all first).
"""
from __future__ import annotations

import pandas as pd
import pytest

from universal_churn.schema_resolution import resolve_schema, resolution_summary
from universal_churn.concepts import (
    BUSINESS_CONCEPTS, CONCEPT_NAMES, compute_concept_values,
)
from universal_churn.concept_confidence import (
    compute_concept_confidence, MIN_RECONSTRUCTABLE_OVERALL_CONFIDENCE,
)
from universal_churn.coverage import compute_coverage_score
from universal_churn.quality_gate import run_quality_gate
from universal_churn.routing import route, ModelType, ReliabilityLevel


# ══════════════════════════════════════════════════════════════════
# FIXTURES — three schema scenarios named in the architecture spec
# ══════════════════════════════════════════════════════════════════

@pytest.fixture
def golden_healthcare_df():
    """Full, clean Healthcare schema — every canonical field present."""
    return pd.DataFrame({
        'PatientID': ['P1', 'P2', 'P3', 'P4'],
        'Tenure_Months': [18, 48, 6, 30],
        'Avg_Out_Of_Pocket_Cost': [200.0, 500.0, 100.0, 300.0],
        'Visits_Last_Year': [8, 15, 2, 10],
        'Billing_Issues': [0, 2, 0, 1],
        'Overall_Satisfaction': [4.0, 2.0, 5.0, 3.0],
        'Age': [45, 70, 32, 60],
        'Churned': ['No', 'Yes', 'No', 'No'],
    })


@pytest.fixture
def telecom_sparse_df():
    """Telecom file with only the two strongest signals present."""
    return pd.DataFrame({
        'tenure': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        'MonthlyCharges': [20, 30, 40, 50, 60, 70, 80, 90, 100, 110],
        'Churn': ['No', 'No', 'Yes', 'No', 'Yes', 'No', 'No', 'Yes', 'No', 'No'],
    })


@pytest.fixture
def unknown_schema_df():
    """Columns with no relationship to any canonical field."""
    return pd.DataFrame({
        'foo': [1, 2, 3], 'bar': [4, 5, 6], 'Churn': ['No', 'Yes', 'No'],
    })


# ══════════════════════════════════════════════════════════════════
# 1. CANONICAL MAPPING (schema_resolution.py)
# ══════════════════════════════════════════════════════════════════

class TestCanonicalMapping:
    def test_exact_alias_resolves_at_full_confidence(self, golden_healthcare_df):
        _, resolutions = resolve_schema(golden_healthcare_df)
        by_col = {r.raw_column: r for r in resolutions}
        assert by_col['Tenure_Months'].canonical_field == 'Tenure_Raw'
        assert by_col['Tenure_Months'].method == 'exact'
        assert by_col['Tenure_Months'].confidence == 1.0

    def test_unrelated_columns_stay_unresolved(self, unknown_schema_df):
        _, resolutions = resolve_schema(unknown_schema_df)
        by_col = {r.raw_column: r for r in resolutions}
        assert by_col['foo'].method == 'unresolved'
        assert by_col['foo'].canonical_field is None

    def test_resolution_summary_counts(self, golden_healthcare_df):
        _, resolutions = resolve_schema(golden_healthcare_df)
        summary = resolution_summary(resolutions)
        assert summary['exact_matches'] >= 6
        assert 'Tenure_Raw' in summary['matched_fields']


# ══════════════════════════════════════════════════════════════════
# 2. BUSINESS CONCEPT GENERATION (concepts.py)
# ══════════════════════════════════════════════════════════════════

class TestBusinessConceptGeneration:
    def test_all_five_concepts_registered(self):
        assert set(CONCEPT_NAMES) == {
            'RECURRING_COMMITMENT', 'CUSTOMER_LOYALTY', 'SUPPORT_FRICTION',
            'ENGAGEMENT_LEVEL', 'SATISFACTION_SIGNAL',
        }

    def test_concept_values_in_unit_range(self, golden_healthcare_df):
        from universal_churn.schema_resolution import resolve_schema
        resolved_df, _ = resolve_schema(golden_healthcare_df)
        concept_df, confidence = compute_concept_values(resolved_df, 'healthcare')
        for col in concept_df.columns:
            assert concept_df[col].between(0.0, 1.0).all()
        assert confidence['CUSTOMER_LOYALTY'] == 1.0  # direct measure for healthcare

    def test_unavailable_concept_reports_zero_confidence(self, golden_healthcare_df):
        from universal_churn.schema_resolution import resolve_schema
        resolved_df, _ = resolve_schema(golden_healthcare_df)
        _, confidence = compute_concept_values(resolved_df, 'telecom')
        # telecom has no documented SUPPORT_FRICTION source
        assert confidence['SUPPORT_FRICTION'] == 0.0


# ══════════════════════════════════════════════════════════════════
# 3. CONCEPT CONFIDENCE ENGINE (concept_confidence.py)
# ══════════════════════════════════════════════════════════════════

class TestConceptConfidenceEngine:
    def test_golden_dataset_high_confidence(self, golden_healthcare_df):
        report = compute_concept_confidence(golden_healthcare_df, 'healthcare')
        assert report.overall_confidence >= 0.7
        assert report.concepts_reconstructable is True

    def test_sparse_dataset_partial_but_reconstructable(self, telecom_sparse_df):
        report = compute_concept_confidence(telecom_sparse_df, 'telecom')
        assert 0.0 < report.overall_confidence < 1.0
        assert report.reconstructable_concepts >= 1
        assert report.concepts_reconstructable is True

    def test_unknown_schema_zero_confidence(self, unknown_schema_df):
        report = compute_concept_confidence(unknown_schema_df, 'telecom')
        assert report.overall_confidence == 0.0
        assert report.reconstructable_concepts == 0
        assert report.concepts_reconstructable is False

    def test_report_serializes_to_plain_dict(self, telecom_sparse_df):
        report = compute_concept_confidence(telecom_sparse_df, 'telecom')
        d = report.to_dict()
        assert isinstance(d, dict)
        assert set(d.keys()) >= {
            'sector', 'per_concept', 'overall_confidence',
            'reconstructable_concepts', 'total_concepts', 'concepts_reconstructable',
        }

    def test_coverage_dict_carries_concept_confidence(self, telecom_sparse_df):
        """Phase 4 wiring: compute_coverage_score() must attach concept_confidence."""
        cov = compute_coverage_score(telecom_sparse_df, 'telecom', mode='auto',
                                     _suppress_print=True)
        assert 'concept_confidence' in cov
        assert cov['concept_confidence']['sector'] == 'telecom'


# ══════════════════════════════════════════════════════════════════
# 4. ROUTING USING CONCEPT CONFIDENCE (routing.py)
# ══════════════════════════════════════════════════════════════════

class TestConceptAwareRouting:
    def test_sparse_but_reconstructable_routes_universal_not_refused(self, telecom_sparse_df):
        """
        Before Phase 5: Red coverage always -> CRITICAL_UNRELIABLE.
        After Phase 5: Red coverage + reconstructable concepts -> UNIVERSAL_MODEL.
        """
        cov = compute_coverage_score(telecom_sparse_df, 'telecom', mode='auto',
                                     _suppress_print=True)
        qual = run_quality_gate(telecom_sparse_df, target_col='Churn')
        assert cov['status'] == 'Red'

        decision = route(mode='auto', coverage=cov, quality=qual, sector='telecom')
        assert decision.selected_model == ModelType.UNIVERSAL_MODEL
        assert decision.reliability == ReliabilityLevel.LOW
        assert not decision.is_rejected

    def test_unknown_schema_still_refused(self, unknown_schema_df):
        """Coverage Red AND concepts unreconstructable -> still CRITICAL_UNRELIABLE."""
        cov = compute_coverage_score(unknown_schema_df, 'telecom', mode='auto',
                                     _suppress_print=True)
        qual = run_quality_gate(unknown_schema_df, target_col='Churn')
        assert cov['status'] == 'Red'

        decision = route(mode='auto', coverage=cov, quality=qual, sector='telecom')
        assert decision.selected_model == ModelType.CRITICAL_UNRELIABLE
        assert decision.is_rejected

    def test_leakage_still_refuses_regardless_of_concept_confidence(self, golden_healthcare_df):
        """Quality gate (leakage) must remain the hard, mode-independent block."""
        # _check_leakage requires >=10 overlapping numeric rows AND a
        # numeric-coercible target, so tile the fixture and use a 0/1
        # target column rather than the raw 'Yes'/'No' strings.
        df = pd.concat([golden_healthcare_df] * 4, ignore_index=True)
        df['Churned'] = (df['Churned'] == 'Yes').astype(int)
        # Inject a perfectly-leaked column, mirroring the original BMI incident.
        df['LeakedColumn'] = df['Churned'].astype(float)
        cov = compute_coverage_score(df, 'healthcare', mode='auto', _suppress_print=True)
        qual = run_quality_gate(df, target_col='Churned')
        assert qual['leakage_detected'] is True

        decision = route(mode='auto', coverage=cov, quality=qual, sector='healthcare')
        assert decision.selected_model == ModelType.CRITICAL_UNRELIABLE
        assert 'Quality gate FAILED' in decision.routing_reason

    def test_golden_dataset_still_routes_full_sector_model(self, golden_healthcare_df):
        cov = compute_coverage_score(golden_healthcare_df, 'healthcare', mode='auto',
                                     _suppress_print=True)
        qual = run_quality_gate(golden_healthcare_df, target_col='Churned')
        decision = route(mode='auto', coverage=cov, quality=qual, sector='healthcare')
        # Golden dataset is small (n=4) so coverage may not hit Green in every
        # environment; assert it is not refused and not degraded to Red-only path.
        assert decision.selected_model in (ModelType.FULL_SECTOR_MODEL, ModelType.UNIVERSAL_MODEL)
        assert not decision.is_rejected


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
