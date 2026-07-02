"""
tests/test_prediction_explanation.py
Tests for the Prediction Explanation Layer (Version 7, Chunk 5).
"""
import pandas as pd
import pytest

from universal_churn.prediction_explanation import (
    PredictionExplanationBuilder, PredictionSummary, PredictionEvidence,
    PredictionEvidenceItem, PredictionRecommendation, PredictionReliability,
    PredictionNarrative, DatasetExplanation,
)
from universal_churn.prediction_explanation_report import (
    attach_explanation_columns, generate_prediction_explanation_text,
    build_and_attach_explanations,
)
from universal_churn.routing import route, ModelType, PredictionMode


def _fake_results(n=3, churners=1):
    return pd.DataFrame({
        'CustomerID': [f"C{i}" for i in range(n)],
        'Predicted_Churn': (['Yes'] * churners) + (['No'] * (n - churners)),
        'Churn_Probability': [0.8] * churners + [0.2] * (n - churners),
        'Risk_Level': ['High'] * churners + ['Low'] * (n - churners),
        'Prediction_Model': ['Sector XGBoost'] * n,
        'Prediction_Mode': ['Sector'] * n,
    })


def _fake_raw_df(sector='telecom', n=3):
    return pd.DataFrame({
        'tenure': [1, 40, 2],
        'MonthlyCharges': [90, 20, 95],
        'Contract': ['Month-to-month', 'Two year', 'Month-to-month'],
        'Churn': ['Yes', 'No', 'Yes'],
    }).head(n)


def _fake_coverage(status='Green', concept_confidence=0.8, reconstructable=True):
    return {
        'coverage_score': 0.9 if status == 'Green' else 0.4,
        'status': status,
        'missing_critical': [] if status == 'Green' else ['Contract', 'MonthlyCharges'],
        'missing_high_impact': [],
        'missing_all': [],
        'concept_confidence': {
            'overall_confidence': concept_confidence,
            'concepts_reconstructable': reconstructable,
            'per_concept': {},
            'reconstructable_concepts': 3, 'total_concepts': 5,
        },
    }


def _fake_quality():
    return {
        'leakage_detected': False, 'failed_columns': [], 'leakage_flagged': [],
        'leakage_warned': [], 'overall_passed': True,
    }


class TestDataclasses:
    def test_summary_to_dict(self):
        s = PredictionSummary(
            row_index=0, customer_id="C1", predicted_label="Yes", probability=0.8,
            risk_level="High", sector="telecom", prediction_model="Sector XGBoost",
            prediction_mode="Sector",
        )
        d = s.to_dict()
        assert d['predicted_label'] == "Yes"
        assert d['probability'] == 0.8

    def test_frozen_dataclasses_are_immutable(self):
        s = PredictionReliability(level="Low", reasons=("a",), missing_features=())
        with pytest.raises(Exception):
            s.level = "High"


class TestBuilder:
    def test_builds_report_with_correct_row_count(self):
        results = _fake_results(n=3, churners=1)
        raw = _fake_raw_df(n=3)
        coverage = _fake_coverage()
        quality = _fake_quality()
        decision = route(mode='sector', coverage=coverage, quality=quality, sector='telecom')

        report = PredictionExplanationBuilder().build(
            df_raw=raw, sector='telecom', results=results,
            coverage=coverage, quality=quality, routing_decision=decision,
        )
        assert len(report.row_explanations) == 3
        assert report.dataset_explanation.rows_analyzed == 3
        assert report.dataset_explanation.predicted_churners == 1
        assert 0.0 <= report.dataset_explanation.average_probability <= 1.0

    def test_row_explanation_reflects_row_prediction(self):
        results = _fake_results(n=2, churners=1)
        raw = _fake_raw_df(n=2)
        coverage = _fake_coverage()
        quality = _fake_quality()
        decision = route(mode='sector', coverage=coverage, quality=quality, sector='telecom')

        report = PredictionExplanationBuilder().build(
            df_raw=raw, sector='telecom', results=results,
            coverage=coverage, quality=quality, routing_decision=decision,
        )
        first = report.row_explanations[0]
        second = report.row_explanations[1]
        assert first.summary.predicted_label == "Yes"
        assert first.narrative.headline == "HIGH CHURN"
        assert second.summary.predicted_label == "No"
        assert second.narrative.headline == "LOW CHURN"

    def test_missing_features_included_when_coverage_low(self):
        results = _fake_results(n=1, churners=1)
        raw = _fake_raw_df(n=1)
        coverage = _fake_coverage(status='Yellow', concept_confidence=0.5)
        quality = _fake_quality()
        decision = route(mode='sector', coverage=coverage, quality=quality, sector='telecom')

        report = PredictionExplanationBuilder().build(
            df_raw=raw, sector='telecom', results=results,
            coverage=coverage, quality=quality, routing_decision=decision,
        )
        assert report.row_explanations[0].reliability.missing_features

    def test_handles_missing_quality_gracefully(self):
        results = _fake_results(n=1, churners=0)
        raw = _fake_raw_df(n=1)
        coverage = _fake_coverage()
        report = PredictionExplanationBuilder().build(
            df_raw=raw, sector='telecom', results=results,
            coverage=coverage, quality=None, routing_decision=None,
        )
        assert len(report.row_explanations) == 1
        assert report.row_explanations[0].reliability.level == "Unknown"

    def test_handles_none_routing_decision(self):
        results = _fake_results(n=1)
        raw = _fake_raw_df(n=1)
        report = PredictionExplanationBuilder().build(
            df_raw=raw, sector='telecom', results=results,
            coverage=None, quality=None, routing_decision=None,
        )
        assert report.dataset_explanation.rows_analyzed == 1


class TestCsvEnrichment:
    def test_attach_columns_preserves_existing_columns(self):
        results = _fake_results(n=2, churners=1)
        original_columns = set(results.columns)
        raw = _fake_raw_df(n=2)
        coverage = _fake_coverage()
        quality = _fake_quality()
        decision = route(mode='sector', coverage=coverage, quality=quality, sector='telecom')
        report = PredictionExplanationBuilder().build(
            df_raw=raw, sector='telecom', results=results,
            coverage=coverage, quality=quality, routing_decision=decision,
        )
        enriched = attach_explanation_columns(results, report)

        # every original column present and untouched
        assert original_columns.issubset(set(enriched.columns))
        pd.testing.assert_series_equal(
            results['Predicted_Churn'], enriched['Predicted_Churn'],
        )
        pd.testing.assert_series_equal(
            results['Churn_Probability'], enriched['Churn_Probability'],
        )

    def test_attach_columns_adds_expected_new_columns(self):
        results = _fake_results(n=1)
        raw = _fake_raw_df(n=1)
        coverage = _fake_coverage()
        quality = _fake_quality()
        decision = route(mode='sector', coverage=coverage, quality=quality, sector='telecom')
        report = PredictionExplanationBuilder().build(
            df_raw=raw, sector='telecom', results=results,
            coverage=coverage, quality=quality, routing_decision=decision,
        )
        enriched = attach_explanation_columns(results, report)
        expected_new = {
            'Explanation_Prediction', 'Explanation_Probability',
            'Explanation_Triggered_Findings', 'Explanation_Dominant_Concepts',
            'Explanation_Business_Reason', 'Explanation_Recommendation',
            'Explanation_Reliability', 'Explanation_Reliability_Reasons',
            'Explanation_Missing_Features',
        }
        assert expected_new.issubset(set(enriched.columns))

    def test_attach_columns_raises_on_row_mismatch(self):
        results = _fake_results(n=2)
        raw = _fake_raw_df(n=2)
        coverage = _fake_coverage()
        quality = _fake_quality()
        decision = route(mode='sector', coverage=coverage, quality=quality, sector='telecom')
        report = PredictionExplanationBuilder().build(
            df_raw=raw, sector='telecom', results=results,
            coverage=coverage, quality=quality, routing_decision=decision,
        )
        mismatched = _fake_results(n=5)
        with pytest.raises(ValueError):
            attach_explanation_columns(mismatched, report)

    def test_no_column_never_overwrites_existing_prediction_reliability(self):
        # Simulate the real pipeline attaching routing report_fields(),
        # which already includes a 'Prediction_Reliability' column.
        results = _fake_results(n=1)
        results['Prediction_Reliability'] = 'High'
        raw = _fake_raw_df(n=1)
        coverage = _fake_coverage()
        quality = _fake_quality()
        decision = route(mode='sector', coverage=coverage, quality=quality, sector='telecom')
        report = PredictionExplanationBuilder().build(
            df_raw=raw, sector='telecom', results=results,
            coverage=coverage, quality=quality, routing_decision=decision,
        )
        enriched = attach_explanation_columns(results, report)
        assert enriched['Prediction_Reliability'].iloc[0] == 'High'  # untouched
        assert 'Explanation_Reliability' in enriched.columns          # new, separate


class TestReportText:
    def test_generate_text_contains_required_sections(self):
        results = _fake_results(n=2, churners=1)
        raw = _fake_raw_df(n=2)
        coverage = _fake_coverage()
        quality = _fake_quality()
        decision = route(mode='sector', coverage=coverage, quality=quality, sector='telecom')
        report = PredictionExplanationBuilder().build(
            df_raw=raw, sector='telecom', results=results,
            coverage=coverage, quality=quality, routing_decision=decision,
        )
        text = generate_prediction_explanation_text(report)
        assert "PREDICTION EXPLANATION" in text
        assert "Prediction accepted because" in text
        assert "Dataset Summary" in text


class TestBuildAndAttachHelper:
    def test_never_raises_and_returns_dataframe(self):
        results = _fake_results(n=1)
        coverage = _fake_coverage()
        quality = _fake_quality()
        decision = route(mode='sector', coverage=coverage, quality=quality, sector='telecom')
        results.attrs['coverage'] = coverage
        results.attrs['quality'] = quality
        results.attrs['routing_decision'] = decision
        raw = _fake_raw_df(n=1)

        enriched = build_and_attach_explanations(results, raw, 'telecom')
        assert isinstance(enriched, pd.DataFrame)
        assert len(enriched) == 1
        assert 'Explanation_Prediction' in enriched.columns

    def test_degrades_gracefully_on_bad_input(self):
        results = _fake_results(n=1)
        # No attrs set at all — simulates a malformed/foreign results df.
        bad_raw = None  # will cause run_business_reasoning to raise
        enriched = build_and_attach_explanations(results, bad_raw, 'telecom')
        # Must return SOMETHING usable, never raise.
        assert isinstance(enriched, pd.DataFrame)
        assert len(enriched) == len(results)