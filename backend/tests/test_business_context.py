from __future__ import annotations

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.api.routers.analysis import AnalyzeRequest
from backend.services.business_context_service import evaluate_business_context
from universal_churn.adaptive_business import validate_business_context


SAMPLE = {
    "events": [
        {
            "category": "Competitor Promotion",
            "description": "Local unlimited-data promotion.",
            "severity": "HIGH",
            "affected_segments": ["High Data Users"],
            "confidence": 0.82,
        },
        {
            "category": "Network Outage",
            "description": "Regional service disruption.",
            "severity": "MEDIUM",
            "confidence": 0.91,
        },
    ]
}


def test_abil_context_fixture_shape_is_accepted_and_normalized():
    assert len(validate_business_context(SAMPLE)) == 2


@pytest.mark.parametrize(
    "document",
    [
        {},
        {"events": []},
        {"events": [{"category": "x", "description": "y", "severity": "HIGH"}]},
        {"events": [{**SAMPLE["events"][0], "confidence": 1.1}]},
    ],
)
def test_invalid_or_empty_abil_documents_are_rejected(document):
    with pytest.raises((ValidationError, ValueError)):
        AnalyzeRequest(upload_id="upload-1", business_context=document)


def test_context_sector_mismatch_is_rejected():
    context = {"sector": "banking", **SAMPLE}
    with pytest.raises(ValidationError, match="sector must match"):
        AnalyzeRequest(upload_id="upload-1", sector="telecom", business_context=context)


def test_api_validation_errors_are_422_json_and_do_not_echo_request_data():
    client = TestClient(app)
    response = client.post(
        "/api/v1/analyze",
        json={
            "upload_id": "upload-1",
            "sector": "telecom",
            "business_context": {"sector": "banking", **SAMPLE},
        },
    )
    assert response.status_code == 422
    assert "sector must match" in response.json()["detail"][0]["msg"]
    assert "input" not in response.text
    assert "Competitor Promotion" not in response.text


def test_contextless_analysis_remains_backward_compatible():
    assert AnalyzeRequest(upload_id="upload-1", sector="telecom").business_context is None


def test_abil_generates_execution_scoped_signals_without_prediction_fields():
    source_event = {
        **SAMPLE["events"][0],
        "category": "Network Outage",
        "department": "Network Operations",
        "priority": 1,
        "recommended_action": "Run the source-provided action.",
    }
    document = {**SAMPLE, "events": [source_event]}
    result = evaluate_business_context(document, sector="telecom", execution_id="run-123")

    assert result["status"] == "AVAILABLE"
    assert result["signal_count"] == 1
    assert result["sector"] == "telecom"
    assert result["signals"][0]["evidence_id"] == "ABIL-run-123-1"
    assert result["signals"][0]["affected_segments"] == ["High Data Users"]
    assert result["signals"][0]["confidence"] == 0.82
    assert result["signals"][0]["department"] == "Network Operations"
    assert result["signals"][0]["priority"] == 1
    assert result["signals"][0]["source_recommendation"] == "Run the source-provided action."
    assert result["signals"][0]["action"] != "Run the source-provided action."
    assert "network" in result["signals"][0]["action"].lower()
    assert "does not establish" in result["signals"][0]["rationale"]
    assert result["assessment"]["recommended_action"] == result["signals"][0]["action"]
    assert not {"predictions", "churn_probability", "probabilities"}.intersection(result)


def test_comparative_abil_report_uses_existing_multi_event_assessment():
    result = evaluate_business_context(SAMPLE, sector="telecom", execution_id="run-compare")

    report = result["comparative_report"]
    assert report["status"] == "COMPARISON_AVAILABLE"
    assert report["context_count"] == 2
    assert [item["business_driver"] for item in report["individual_assessments"]] == [
        "Competitor Promotion", "Network Outage",
    ]
    assert report["dominant_business_driver"] == result["assessment"]["dominant_driver"]
    assert report["dominant_business_driver"] == "Competitor Promotion"
    assert "severity first, then supplied confidence" in report["decision_justification"]
    assert "Highest reported impact is HIGH" in report["comparative_findings"][0]
    assert report["individual_assessments"][0]["reported_confidence"] == 0.82
    assert any("not calibrated churn probabilities" in item for item in report["limitations"])


def test_comparative_abil_report_handles_single_and_missing_contexts():
    single = evaluate_business_context(
        {"events": [SAMPLE["events"][0]]}, sector="telecom", execution_id="run-single",
    )["comparative_report"]
    empty = evaluate_business_context(
        {"events": []}, sector="telecom", execution_id="run-empty",
    )["comparative_report"]

    assert single["status"] == "SINGLE_CONTEXT"
    assert single["context_count"] == 1
    assert single["comparative_findings"] == ["One supplied context was assessed; there are no peer contexts to compare."]
    assert empty["status"] == "NO_CONTEXT"
    assert empty["context_count"] == 0
    assert empty["individual_assessments"] == []
    assert empty["dominant_business_driver"] is None


@pytest.mark.parametrize(
    ("sector", "category", "expected"),
    [
        ("telecom", "Network Quality", "network or service-reliability"),
        ("banking", "Cybersecurity", "authorized case review"),
        ("ecommerce", "Logistics", "fulfillment, return, or inventory"),
        ("healthcare", "Patient Safety", "clinical or safety signal"),
    ],
)
def test_abil_follow_up_is_sector_specific_and_evidence_bounded(sector, category, expected):
    result = evaluate_business_context(
        {"events": [{
            "category": category,
            "description": "A supplied operational event description.",
            "severity": "HIGH",
            "confidence": 0.83,
            "department": "Strategy",
            "priority": 1,
        }]},
        sector=sector,
        execution_id="run-sector",
    )

    signal = result["signals"][0]
    assert expected in signal["action"]
    assert signal["priority"] == 1
    assert signal["department"] == "Strategy"
    assert signal["evidence_id"] == "ABIL-run-sector-1"
    assert "does not establish" in signal["rationale"]
