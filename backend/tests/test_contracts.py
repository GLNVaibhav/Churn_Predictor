"""
Tests for backend.contracts — construction, serialization, and
round-trip (to_dict -> from_dict) for each section dataclass.
"""
from __future__ import annotations

from backend.contracts import (
    ExecutionInfo, DatasetInfo, PipelineStageInfo, PipelineSummary,
    FrameworkMetadata, ReportReference,
)
from backend.contracts.analysis_response import (
    UniversalAnalysisResponse, CoverageSummary, ConceptConfidenceSummary,
    QualitySummary, RoutingSummary, PredictionSummary, PredictionExplanationSummary,
    DecisionSummary, ReportReference,
)


# ── ExecutionInfo ────────────────────────────────────────────────

def test_execution_info_start_sets_running_status():
    info = ExecutionInfo.start(framework_version="1.0.0")
    assert info.status == "RUNNING"
    assert info.execution_id.startswith("exec_")
    assert info.started_at
    assert info.completed_at is None


def test_execution_info_mark_succeeded():
    info = ExecutionInfo.start()
    done = info.mark_succeeded(execution_time_ms=123.4)
    assert done.status == "SUCCEEDED"
    assert done.completed_at is not None
    assert done.execution_time_ms == 123.4
    # original execution id preserved
    assert done.execution_id == info.execution_id


def test_execution_info_round_trip():
    info = ExecutionInfo.start(framework_version="1.0.0").mark_succeeded(50.0)
    rebuilt = ExecutionInfo.from_dict(info.to_dict())
    assert rebuilt == info


# ── DatasetInfo ──────────────────────────────────────────────────

def test_dataset_info_round_trip():
    ds = DatasetInfo(filename="telecom.csv", sector="telecom",
                     prediction_mode="auto", rows=100, columns=20,
                     schema_version="6.chunk1")
    rebuilt = DatasetInfo.from_dict(ds.to_dict())
    assert rebuilt == ds


def test_dataset_info_defaults_are_none():
    ds = DatasetInfo()
    d = ds.to_dict()
    assert d["filename"] is None
    assert d["rows"] is None


# ── PipelineSummary ──────────────────────────────────────────────

def test_pipeline_summary_from_stages_aggregates_correctly():
    stages = [
        PipelineStageInfo(name="schema_resolution", status="OK"),
        PipelineStageInfo(name="coverage", status="WARNING", description="Yellow band"),
        PipelineStageInfo(name="prediction", status="FAILED", description="model missing"),
    ]
    summary = PipelineSummary.from_stages(stages)
    assert summary.total_stages == 3
    assert summary.failed == 1
    assert summary.warnings == 1
    assert summary.overall_status == "FAILED"


def test_pipeline_summary_all_ok_is_ok_overall():
    stages = [PipelineStageInfo(name="a", status="OK"), PipelineStageInfo(name="b", status="OK")]
    summary = PipelineSummary.from_stages(stages)
    assert summary.overall_status == "OK"
    assert summary.failed == 0
    assert summary.warnings == 0


def test_pipeline_summary_round_trip():
    stages = [PipelineStageInfo(name="a", status="OK", execution_time=12.5)]
    summary = PipelineSummary.from_stages(stages)
    rebuilt = PipelineSummary.from_dict(summary.to_dict())
    assert rebuilt.total_stages == summary.total_stages
    assert rebuilt.stages[0].name == "a"
    assert rebuilt.stages[0].execution_time == 12.5


# ── FrameworkMetadata ────────────────────────────────────────────

def test_framework_metadata_round_trip():
    meta = FrameworkMetadata(
        framework_version="1.0.0", knowledge_base_version="1.0.0",
        coverage_version="1.0.0", prediction_intelligence_version="8.2.1",
    )
    rebuilt = FrameworkMetadata.from_dict(meta.to_dict())
    assert rebuilt == meta


# ── section dataclasses ─────────────────────────────────────────

def test_coverage_summary_round_trip():
    cov = CoverageSummary(
        coverage_score=0.9, status="Green", coverage_band="Green",
        missing_critical=[], missing_high_impact=["OnlineSecurity"],
    )
    rebuilt = CoverageSummary.from_dict(cov.to_dict())
    assert rebuilt == cov


def test_concept_confidence_summary_round_trip():
    cc = ConceptConfidenceSummary(
        sector="telecom", overall_confidence=0.72, reconstructable_concepts=3,
        total_concepts=5, concepts_reconstructable=True,
        per_concept={"CUSTOMER_LOYALTY": {"confidence": 1.0}},
    )
    rebuilt = ConceptConfidenceSummary.from_dict(cc.to_dict())
    assert rebuilt == cc


def test_quality_summary_round_trip():
    q = QualitySummary(overall_passed=False, leakage_detected=True,
                       leakage_flagged=["BMI"])
    rebuilt = QualitySummary.from_dict(q.to_dict())
    assert rebuilt == q


def test_routing_summary_round_trip():
    r = RoutingSummary(selected_model="UNIVERSAL_MODEL", reliability="High",
                       concept_confidence=0.5, warnings=["Coverage is Yellow"])
    rebuilt = RoutingSummary.from_dict(r.to_dict())
    assert rebuilt == r


def test_prediction_summary_round_trip():
    p = PredictionSummary(rows=10, predicted_churners=4, average_probability=0.42,
                          risk_distribution={"High": 4, "Low": 6},
                          prediction_model="Sector XGBoost", prediction_mode="Auto")
    rebuilt = PredictionSummary.from_dict(p.to_dict())
    assert rebuilt == p


def test_prediction_explanation_summary_round_trip():
    e = PredictionExplanationSummary(
        headline="HIGH CHURN", reason_text="reason", recommendation_text="rec",
        overall_business_health="MEDIUM", overall_customer_risk="HIGH",
        dominant_findings=["Retention Risk"],
    )
    rebuilt = PredictionExplanationSummary.from_dict(e.to_dict())
    assert rebuilt == e


def test_decision_summary_round_trip():
    d = DecisionSummary(decision_readiness="READY", overall_confidence=0.78,
                        risk_level="HIGH", recommended_action="Proceed")
    rebuilt = DecisionSummary.from_dict(d.to_dict())
    assert rebuilt == d


def test_report_reference_round_trip():
    rr = ReportReference(
        id="rep_123",
        type="quality",
        title="Quality Report",
        created_at="2023-01-01T00:00:00Z",
        location="s3://bucket/reports/rep_123.txt",
    )
    rebuilt = ReportReference.from_dict(rr.to_dict())
    assert rebuilt == rr

def test_universal_analysis_response_full_round_trip():
    execution = ExecutionInfo.start(framework_version="1.0.0").mark_succeeded(42.0)
    response = UniversalAnalysisResponse(
        execution=execution,
        dataset=DatasetInfo(filename="t.csv", sector="telecom"),
        pipeline=PipelineSummary.from_stages([PipelineStageInfo(name="coverage", status="OK")]),
        coverage=CoverageSummary(coverage_score=0.9, status="Green", coverage_band="Green"),
        concept_confidence=ConceptConfidenceSummary(sector="telecom", overall_confidence=0.7),
        quality=QualitySummary(overall_passed=True),
        routing=RoutingSummary(selected_model="FULL_SECTOR_MODEL"),
        prediction=PredictionSummary(rows=5, predicted_churners=2),
        prediction_explanation=PredictionExplanationSummary(headline="HIGH CHURN"),
        decision=DecisionSummary(decision_readiness="READY"),
        reports=[
            ReportReference(
                id="rep_1",
                type="quality",
                title="Quality Report",
                created_at="2023-01-01T00:00:00Z",
                location="/tmp/quality.txt",
            ),
            ReportReference(
                id="rep_2",
                type="decision",
                title="Decision Report",
                created_at="2023-01-01T00:00:00Z",
                location="/tmp/decision.txt",
            ),
        ],
        warnings=["some warning"],
        metadata=FrameworkMetadata(framework_version="1.0.0"),
    )
    d = response.to_dict()
    rebuilt = UniversalAnalysisResponse.from_dict(d)
    assert rebuilt.execution.execution_id == execution.execution_id
    assert rebuilt.dataset.sector == "telecom"
    assert rebuilt.coverage.coverage_score == 0.9
    assert rebuilt.concept_confidence.overall_confidence == 0.7
    assert rebuilt.quality.overall_passed is True
    assert rebuilt.routing.selected_model == "FULL_SECTOR_MODEL"
    assert rebuilt.prediction.rows == 5
    assert rebuilt.prediction_explanation.headline == "HIGH CHURN"
    assert rebuilt.decision.decision_readiness == "READY"
    assert rebuilt.reports[0].id == "rep_1"
    assert rebuilt.reports[1].type == "decision"
    assert rebuilt.warnings == ["some warning"]
    assert rebuilt.metadata.framework_version == "1.0.0"


# ── UniversalAnalysisResponse ────────────────────────────────────

def test_universal_analysis_response_minimal_construction():
    execution = ExecutionInfo.start()
    response = UniversalAnalysisResponse(execution=execution)
    assert response.dataset is None
    assert response.coverage is None
    assert response.warnings == []


def test_universal_analysis_response_full_round_trip():
    execution = ExecutionInfo.start(framework_version="1.0.0").mark_succeeded(42.0)
    response = UniversalAnalysisResponse(
        execution=execution,
        dataset=DatasetInfo(filename="t.csv", sector="telecom"),
        pipeline=PipelineSummary.from_stages([PipelineStageInfo(name="coverage", status="OK")]),
        coverage=CoverageSummary(coverage_score=0.9, status="Green", coverage_band="Green"),
        concept_confidence=ConceptConfidenceSummary(sector="telecom", overall_confidence=0.7),
        quality=QualitySummary(overall_passed=True),
        routing=RoutingSummary(selected_model="FULL_SECTOR_MODEL"),
        prediction=PredictionSummary(rows=5, predicted_churners=2),
        prediction_explanation=PredictionExplanationSummary(headline="HIGH CHURN"),
        decision=DecisionSummary(decision_readiness="READY"),
        reports=[
            ReportReference(
                id="rep_1",
                type="quality",
                title="Quality",
                created_at="2023-01-01T00:00:00Z",
                location="/tmp/quality.txt",
            ),
        ],
        warnings=["some warning"],
        metadata=FrameworkMetadata(framework_version="1.0.0"),
    )
    d = response.to_dict()
    rebuilt = UniversalAnalysisResponse.from_dict(d)

    assert rebuilt.execution.execution_id == execution.execution_id
    assert rebuilt.dataset.sector == "telecom"
    assert rebuilt.coverage.coverage_score == 0.9
    assert rebuilt.concept_confidence.overall_confidence == 0.7
    assert rebuilt.quality.overall_passed is True
    assert rebuilt.routing.selected_model == "FULL_SECTOR_MODEL"
    assert rebuilt.prediction.rows == 5
    assert rebuilt.prediction_explanation.headline == "HIGH CHURN"
    assert rebuilt.decision.decision_readiness == "READY"
    assert rebuilt.reports.quality_report_text == "ok"
    assert rebuilt.warnings == ["some warning"]
    assert rebuilt.metadata.framework_version == "1.0.0"


def test_universal_analysis_response_from_dict_requires_execution():
    import pytest
    with pytest.raises(ValueError):
        UniversalAnalysisResponse.from_dict({})


def test_universal_analysis_response_is_json_serializable():
    import json
    execution = ExecutionInfo.start()
    response = UniversalAnalysisResponse(
        execution=execution,
        coverage=CoverageSummary(coverage_score=0.5, status="Yellow", coverage_band="Yellow"),
    )
    # Should not raise
    payload = json.dumps(response.to_dict())
    assert "coverage_score" in payload
