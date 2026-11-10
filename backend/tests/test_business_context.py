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
    document = {**SAMPLE, "events": [SAMPLE["events"][0]]}
    result = evaluate_business_context(document, sector="telecom", execution_id="run-123")

    assert result["status"] == "AVAILABLE"
    assert result["signal_count"] == 1
    assert result["sector"] == "telecom"
    assert result["signals"][0]["evidence_id"] == "ABIL-run-123-1"
    assert result["signals"][0]["affected_segments"] == ["High Data Users"]
    assert result["signals"][0]["confidence"] == 0.82
    assert not {"predictions", "churn_probability", "probabilities"}.intersection(result)
