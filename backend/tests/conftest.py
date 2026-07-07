"""
Shared fixtures for backend tests.

These fixtures fabricate the SHAPES that ``universal_churn``'s real
modules produce (coverage dicts, quality dicts, RoutingDecision-like
objects, a results DataFrame, PredictionExplanationReport-like
objects, DecisionAssessment-like objects) WITHOUT importing the real
framework modules. That keeps these tests fast and independent of
model artifacts / trained pickles / knowledge-base YAML files, while
still exercising the exact field names ``FrameworkMapper`` reads.

Where the real framework uses an Enum (e.g. ``routing.ModelType``,
``routing.ReliabilityLevel``), the fakes below use a tiny stand-in
with a ``.value`` attribute, since that's the only thing
``FrameworkMapper`` reads off them.
"""
from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest


class _EnumLike:
    """Minimal stand-in for a str Enum member — exposes only `.value`."""
    def __init__(self, value: str):
        self.value = value


@pytest.fixture
def fake_coverage_dict() -> dict:
    return {
        "coverage_score": 0.91,
        "status": "Green",
        "coverage_band": "Green",
        "prediction_mode": "Full",
        "missing_critical": [],
        "missing_high_impact": ["OnlineSecurity"],
        "missing_all": ["OnlineSecurity"],
        "recovered_features": [],
        "semantic_matches": ["MonthlyCharges"],
        "detail": [{"feature": "tenure", "weight": 5, "quality": 1, "reason": "OK"}],
        "concept_confidence": {
            "sector": "telecom",
            "overall_confidence": 0.72,
            "reconstructable_concepts": 3,
            "total_concepts": 5,
            "concepts_reconstructable": True,
            "per_concept": {
                "CUSTOMER_LOYALTY": {
                    "confidence": 1.0, "reconstructable": True,
                    "reason": "Reconstructed from resolved canonical field.",
                    "canonical_field": "Tenure_Raw",
                    "source_confidence": 1.0, "resolution_confidence": 1.0,
                },
            },
        },
    }


@pytest.fixture
def fake_quality_dict() -> dict:
    return {
        "column_results": [],
        "failed_columns": ["gender"],
        "leakage_flagged": [],
        "leakage_warned": ["SeniorCitizen"],
        "leakage_detected": False,
        "overall_passed": True,
    }


@pytest.fixture
def fake_quality_dict_leaked() -> dict:
    return {
        "column_results": [],
        "failed_columns": ["BMI"],
        "leakage_flagged": ["BMI"],
        "leakage_warned": [],
        "leakage_detected": True,
        "overall_passed": False,
    }


@pytest.fixture
def fake_routing_decision() -> SimpleNamespace:
    return SimpleNamespace(
        selected_model=_EnumLike("FULL_SECTOR_MODEL"),
        selected_pipeline="SectorPipeline:telecom",
        prediction_mode=_EnumLike("auto"),
        routing_reason="Auto mode — coverage Green (91.0% >= 85%). Sector model selected.",
        coverage_score=0.91,
        coverage_band="Green",
        quality_score=1.0,
        quality_status="GOOD",
        concept_confidence=0.72,
        reliability=_EnumLike("Very High"),
        model_artifact="sector:telecom",
        warnings=[],
    )


@pytest.fixture
def fake_results_df() -> pd.DataFrame:
    return pd.DataFrame({
        "CustomerID": ["A1", "A2", "A3"],
        "Predicted_Churn": ["Yes", "No", "Yes"],
        "Churn_Probability": [0.81, 0.12, 0.66],
        "Risk_Level": ["High", "Low", "Medium"],
        "Sector": ["Telecom", "Telecom", "Telecom"],
        "Prediction_Model": ["Sector XGBoost"] * 3,
        "Prediction_Mode": ["Auto"] * 3,
    })


@pytest.fixture
def fake_explanation_report() -> SimpleNamespace:
    narrative = SimpleNamespace(
        headline="HIGH CHURN",
        reason_text="Retention Risk fired — recurring commitment weak.",
        recommendation_text="Launch a targeted retention campaign.",
    )
    dataset_explanation = SimpleNamespace(
        overall_business_health="MEDIUM",
        overall_customer_risk="HIGH",
        dominant_findings=("Retention Risk",),
    )
    return SimpleNamespace(
        dataset_narrative=narrative,
        dataset_explanation=dataset_explanation,
    )


@pytest.fixture
def fake_decision_assessment() -> SimpleNamespace:
    return SimpleNamespace(
        decision_readiness=_EnumLike("READY"),
        overall_confidence=0.78,
        business_confidence=0.74,
        technical_confidence=0.82,
        evidence_strength=0.80,
        risk_level=_EnumLike("HIGH"),
        recommended_action="Proceed with retention campaign for this customer segment.",
        warnings=["Concept confidence is 72.0%, below the 40% automation threshold."],
    )
