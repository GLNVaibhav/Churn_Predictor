"""
Tests for backend.mappers.FrameworkMapper — verifies that framework
output shapes (dicts and typed-like objects) are faithfully reshaped
into backend.contracts sections, with no computation happening along
the way (every asserted value already existed in the fixture).
"""
from __future__ import annotations

import pytest

from backend.contracts import ExecutionInfo
from backend.exceptions import UnsupportedFrameworkOutputError
from backend.mappers import FrameworkMapper
from backend.models.execution_result import ExecutionResult
from backend.presentation import build_prediction_summary


@pytest.fixture
def mapper() -> FrameworkMapper:
    return FrameworkMapper()


# ── coverage ─────────────────────────────────────────────────────

def test_map_coverage_reads_fields_verbatim(mapper, fake_coverage_dict):
    summary = mapper.map_coverage(fake_coverage_dict)
    assert summary.coverage_score == fake_coverage_dict["coverage_score"]
    assert summary.status == "Green"
    assert summary.missing_high_impact == ["OnlineSecurity"]
    assert summary.semantic_matches == ["MonthlyCharges"]


def test_map_coverage_none_is_none(mapper):
    assert mapper.map_coverage(None) is None


def test_map_coverage_rejects_wrong_type(mapper):
    with pytest.raises(UnsupportedFrameworkOutputError):
        mapper.map_coverage("not a dict")


# ── concept confidence (embedded in coverage dict) ──────────────

def test_map_concept_confidence_reads_embedded_dict(mapper, fake_coverage_dict):
    summary = mapper.map_concept_confidence(fake_coverage_dict)
    assert summary.sector == "telecom"
    assert summary.overall_confidence == 0.72
    assert summary.concepts_reconstructable is True
    assert "CUSTOMER_LOYALTY" in summary.per_concept


def test_map_concept_confidence_missing_key_is_none(mapper):
    assert mapper.map_concept_confidence({"coverage_score": 0.5}) is None


def test_map_concept_confidence_error_flag_is_none(mapper):
    coverage = {"concept_confidence": {"error": "boom"}}
    assert mapper.map_concept_confidence(coverage) is None


# ── quality ──────────────────────────────────────────────────────

def test_map_quality_pass(mapper, fake_quality_dict):
    summary = mapper.map_quality(fake_quality_dict)
    assert summary.overall_passed is True
    assert summary.leakage_detected is False
    assert summary.leakage_warned == ["SeniorCitizen"]


def test_map_quality_leaked(mapper, fake_quality_dict_leaked):
    summary = mapper.map_quality(fake_quality_dict_leaked)
    assert summary.leakage_detected is True
    assert summary.leakage_flagged == ["BMI"]
    assert summary.overall_passed is False


def test_map_quality_none_is_none(mapper):
    assert mapper.map_quality(None) is None


# ── routing ──────────────────────────────────────────────────────

def test_map_routing_reads_enum_like_values(mapper, fake_routing_decision):
    summary = mapper.map_routing(fake_routing_decision)
    assert summary.selected_model == "FULL_SECTOR_MODEL"
    assert summary.reliability == "Very High"
    assert summary.coverage_score == 0.91
    assert summary.model_artifact == "sector:telecom"


def test_map_routing_none_is_none(mapper):
    assert mapper.map_routing(None) is None


def test_map_routing_accepts_plain_dict(mapper):
    routing_dict = {
        "selected_model": "UNIVERSAL_MODEL",
        "selected_pipeline": "UniversalPipeline",
        "prediction_mode": "auto",
        "routing_reason": "fallback",
        "coverage_score": 0.65,
        "coverage_band": "Yellow",
        "quality_score": 1.0,
        "quality_status": "GOOD",
        "concept_confidence": 0.5,
        "reliability": "Moderate",
        "model_artifact": "universal",
        "warnings": ["Coverage is Yellow"],
    }
    summary = mapper.map_routing(routing_dict)
    assert summary.selected_model == "UNIVERSAL_MODEL"
    assert summary.warnings == ["Coverage is Yellow"]


# ── prediction ───────────────────────────────────────────────────

def test_map_prediction_aggregates_from_results_df(mapper, fake_results_df):
    summary = mapper.map_prediction(fake_results_df)
    assert summary.rows == 3
    assert summary.predicted_churners == 2
    assert summary.prediction_model == "Sector XGBoost"
    assert summary.risk_distribution.get("High") == 1


def test_map_prediction_none_is_none(mapper):
    assert mapper.map_prediction(None) is None


def test_map_prediction_empty_dataframe(mapper, fake_results_df):
    empty = fake_results_df.iloc[0:0]
    summary = mapper.map_prediction(empty)
    assert summary.rows == 0


# ── prediction explanation ──────────────────────────────────────

def test_map_prediction_explanation(mapper, fake_explanation_report):
    summary = mapper.map_prediction_explanation(fake_explanation_report)
    assert summary.headline == "HIGH CHURN"
    assert summary.overall_customer_risk == "HIGH"
    assert summary.dominant_findings == ["Retention Risk"]


def test_map_prediction_explanation_none_is_none(mapper):
    assert mapper.map_prediction_explanation(None) is None


# ── decision ─────────────────────────────────────────────────────

def test_map_decision(mapper, fake_decision_assessment):
    summary = mapper.map_decision(fake_decision_assessment)
    assert summary.decision_readiness == "READY"
    assert summary.risk_level == "HIGH"
    assert summary.overall_confidence == 0.78
    assert len(summary.warnings) == 1


def test_map_decision_none_is_none(mapper):
    assert mapper.map_decision(None) is None


# ── reports ──────────────────────────────────────────────────────

def test_map_reports(mapper):
    execution = ExecutionInfo.start()
    reports = mapper.map_reports({"quality_report_text": "all good"}, execution.execution_id)
    assert isinstance(reports, list)
    assert reports[0].type == "quality"
    assert reports[0].title == "Quality"


def test_map_reports_empty_is_none(mapper):
    execution = ExecutionInfo.start()
    assert mapper.map_reports(None, execution.execution_id) is None
    assert mapper.map_reports({}, execution.execution_id) is None


# ── warnings roll-up ─────────────────────────────────────────────

def test_collect_warnings_deduplicates(mapper):
    from backend.contracts.analysis_response import RoutingSummary, QualitySummary, DecisionSummary
    routing = RoutingSummary(warnings=["dup", "routing only"])
    quality = QualitySummary(leakage_warned=["ColX"])
    decision = DecisionSummary(warnings=["dup"])
    warnings = mapper.collect_warnings(
        routing_summary=routing, quality_summary=quality,
        decision_summary=decision, extra=["dup"],
    )
    assert warnings.count("dup") == 1
    assert "routing only" in warnings
    assert "Elevated correlation with target (ColX)" in warnings


# ── full assembly ────────────────────────────────────────────────

def test_build_response_full_pipeline(
    mapper, fake_coverage_dict, fake_quality_dict, fake_routing_decision,
    fake_results_df, fake_explanation_report, fake_decision_assessment,
):
    execution = ExecutionInfo.start(framework_version="1.0.0")
    execution_result = ExecutionResult.from_framework_output(
        sector="telecom", mode="auto",
        results=fake_results_df,
        coverage=fake_coverage_dict,
        quality=fake_quality_dict,
        routing_decision=fake_routing_decision,
        explanation_report=fake_explanation_report,
        decision_assessment=fake_decision_assessment,
    ).with_reports({"quality_report_text": "ok"})
    response = mapper.build_response(
        execution=execution,
        execution_result=execution_result,
        prediction_summary=build_prediction_summary(fake_results_df),
    )

    assert response.execution is execution
    assert response.coverage.status == "Green"
    assert response.concept_confidence.overall_confidence == 0.72
    assert response.quality.overall_passed is True
    # Verify reports list and first report reference
    assert isinstance(response.reports, list)
    assert response.reports[0].type == "quality"
    # The report ID includes execution id prefix; ensure it matches pattern
    assert response.reports[0].id.startswith(execution.execution_id + "_quality")
    # The title should be capitalized form of type
    assert response.reports[0].title == "Quality"


def test_build_response_refused_prediction_has_no_prediction_sections(
    mapper, fake_coverage_dict, fake_quality_dict_leaked,
):
    """A quality-gate FAIL means no prediction was ever made — the
    response must still be well-formed with those sections as None."""
    execution = ExecutionInfo.start()
    execution_result = ExecutionResult.from_framework_output(
        sector="telecom", mode="auto",
        refused=True, refusal_reason="CRITICAL_UNRELIABLE",
        coverage=fake_coverage_dict,
        quality=fake_quality_dict_leaked,
    )
    response = mapper.build_response(
        execution=execution,
        execution_result=execution_result,
        prediction_summary=None,
    )
    assert response.quality.leakage_detected is True
    assert response.routing is None
    assert response.prediction is None
    assert response.prediction_explanation is None
    assert response.decision is None


def test_build_response_is_fully_serializable(
    mapper, fake_coverage_dict, fake_quality_dict, fake_routing_decision,
    fake_results_df,
):
    import json
    execution = ExecutionInfo.start().mark_succeeded(10.0)
    execution_result = ExecutionResult.from_framework_output(
        sector="telecom", mode="auto",
        results=fake_results_df,
        coverage=fake_coverage_dict,
        quality=fake_quality_dict,
        routing_decision=fake_routing_decision,
    )
    response = mapper.build_response(
        execution=execution,
        execution_result=execution_result,
        prediction_summary=build_prediction_summary(fake_results_df),
    )
    payload = json.dumps(response.to_dict())
    assert "FULL_SECTOR_MODEL" in payload
