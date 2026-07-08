"""
Tests for backend.models.ExecutionResult — normalization, immutability,
serialization round-trip, and golden contract integrity.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd
import pytest

from backend.models.execution_result import (
    ExecutionMetadata,
    ExecutionResult,
    PredictionsSection,
    extract_raw_framework_output,
)


@pytest.fixture
def sample_results_df() -> pd.DataFrame:
    return pd.DataFrame({
        "CustomerID": ["A1", "A2"],
        "Predicted_Churn": ["Yes", "No"],
        "Churn_Probability": [0.81, 0.12],
        "Risk_Level": ["High", "Low"],
        "Prediction_Model": ["Sector XGBoost", "Sector XGBoost"],
        "Prediction_Mode": ["Auto", "Auto"],
    })


@pytest.fixture
def sample_coverage() -> dict:
    return {
        "coverage_score": 0.91,
        "status": "Green",
        "coverage_band": "Green",
        "concept_confidence": {
            "sector": "telecom",
            "overall_confidence": 0.72,
            "reconstructable_concepts": 3,
            "total_concepts": 5,
            "concepts_reconstructable": True,
            "per_concept": {},
        },
    }


@pytest.fixture
def sample_quality() -> dict:
    return {
        "overall_passed": True,
        "leakage_detected": False,
        "leakage_flagged": [],
        "leakage_warned": [],
        "failed_columns": [],
    }


class _EnumLike:
    def __init__(self, value: str):
        self.value = value


@pytest.fixture
def sample_routing() -> SimpleNamespace:
    return SimpleNamespace(
        selected_model=_EnumLike("FULL_SECTOR_MODEL"),
        selected_pipeline="SectorPipeline:telecom",
        prediction_mode=_EnumLike("auto"),
        routing_reason="Coverage Green",
        coverage_score=0.91,
        coverage_band="Green",
        quality_score=1.0,
        quality_status="GOOD",
        concept_confidence=0.72,
        reliability=_EnumLike("Very High"),
        model_artifact="sector:telecom",
        warnings=[],
    )


def test_from_framework_output_preserves_values(
    sample_results_df, sample_coverage, sample_quality, sample_routing,
):
    explanation = SimpleNamespace(
        dataset_narrative=SimpleNamespace(headline="HIGH CHURN"),
        dataset_explanation=SimpleNamespace(
            overall_business_health="MEDIUM",
            overall_customer_risk="HIGH",
            dominant_findings=("Retention Risk",),
        ),
    )
    decision = SimpleNamespace(
        decision_readiness=_EnumLike("READY"),
        overall_confidence=0.78,
        business_confidence=0.74,
        technical_confidence=0.82,
        evidence_strength=0.80,
        risk_level=_EnumLike("HIGH"),
        recommended_action="Proceed",
        warnings=["warn1"],
    )

    result = ExecutionResult.from_framework_output(
        sector="telecom",
        mode="auto",
        input_path="tests/golden_telecom.csv",
        results=sample_results_df,
        coverage=sample_coverage,
        quality=sample_quality,
        routing_decision=sample_routing,
        explanation_report=explanation,
        decision_assessment=decision,
    )

    assert result.sector == "telecom"
    assert result.mode == "auto"
    assert result.refused is False
    assert result.coverage["coverage_score"] == 0.91
    assert result.quality["overall_passed"] is True
    assert result.results_df is not None
    assert len(result.results_df) == 2
    assert result.reasoning is explanation
    assert result.decision is decision


def test_from_framework_output_does_not_modify_coverage(sample_coverage):
    original_score = sample_coverage["coverage_score"]
    ExecutionResult.from_framework_output(
        sector="telecom", mode="auto", coverage=dict(sample_coverage),
    )
    assert sample_coverage["coverage_score"] == original_score


def test_refused_result_has_no_predictions():
    result = ExecutionResult.from_framework_output(
        sector="telecom",
        mode="auto",
        refused=True,
        refusal_reason="CRITICAL_UNRELIABLE",
        coverage={"coverage_score": 0.3, "status": "Red"},
    )
    assert result.refused is True
    assert result.refusal_reason == "CRITICAL_UNRELIABLE"
    assert result.results_df is None


def test_immutability():
    meta = ExecutionMetadata(sector="telecom", mode="auto")
    with pytest.raises(Exception):
        meta.sector = "banking"  # frozen dataclass


def test_with_reports_returns_new_instance(sample_coverage):
    base = ExecutionResult.from_framework_output(
        sector="telecom", mode="auto", coverage=sample_coverage,
    )
    updated = base.with_reports({"quality_report_text": "ok"})
    assert base.reports is None
    assert updated.reports == {"quality_report_text": "ok"}
    assert updated.coverage == base.coverage


def test_to_dict_from_dict_round_trip(
    sample_results_df, sample_coverage, sample_quality, sample_routing,
):
    original = ExecutionResult.from_framework_output(
        sector="telecom",
        mode="auto",
        input_path="tests/golden_telecom.csv",
        results=sample_results_df,
        coverage=sample_coverage,
        quality=sample_quality,
        routing_decision=sample_routing,
    )
    serialized = original.to_dict()
    json.dumps(serialized)  # must be JSON-safe

    restored = ExecutionResult.from_dict(serialized)
    assert restored.sector == original.sector
    assert restored.mode == original.mode
    assert restored.coverage["coverage_score"] == original.coverage["coverage_score"]
    assert len(restored.results_df) == len(original.results_df)


def test_extract_raw_framework_output_structure(
    sample_results_df, sample_coverage, sample_quality, sample_routing,
):
    result = ExecutionResult.from_framework_output(
        sector="telecom",
        mode="auto",
        results=sample_results_df,
        coverage=sample_coverage,
        quality=sample_quality,
        routing_decision=sample_routing,
    )
    raw = extract_raw_framework_output(result)
    assert raw["sector"] == "telecom"
    assert raw["coverage"]["coverage_score"] == 0.91
    assert raw["results"]["columns"] == list(sample_results_df.columns)
    assert len(raw["results"]["records"]) == 2


def test_coverage_score_unchanged_after_normalization(sample_coverage):
    """Golden contract invariant: normalization must not alter framework values."""
    before = sample_coverage["coverage_score"]
    result = ExecutionResult.from_framework_output(
        sector="telecom", mode="auto", coverage=sample_coverage,
    )
    after = result.to_dict()["coverage"]["coverage_score"]
    assert before == after
