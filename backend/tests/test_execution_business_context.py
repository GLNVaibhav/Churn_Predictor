import asyncio
from types import SimpleNamespace

from backend.runtime import executor


def test_analysis_execution_persists_and_exposes_adaptive_business_context(monkeypatch):
    service = SimpleNamespace(
        initialize=lambda: None,
        execute=lambda **kwargs: SimpleNamespace(response=object(), execution_result=object()),
        shutdown=lambda: None,
    )
    monkeypatch.setattr(executor, "AnalysisService", lambda: service)
    monkeypatch.setattr(
        executor,
        "enrich_platform_payload",
        lambda *args, **kwargs: {
            "execution": {"status": "SUCCEEDED"},
            "dataset": {"filename": "telecom.csv", "sector": "telecom"},
            "decision": {"recommended_action": "Review high-risk customers."},
            "report_texts": {"decision_report_text": "Decision report."},
            "execution_result": {"prediction_count": 1},
        },
    )
    context = {
        "sector": "telecom",
        "events": [
            {"category": "Network Outage", "description": "Regional interruption", "severity": "HIGH", "confidence": 0.91, "affected_segments": ["North"]},
            {"category": "Competitor Promotion", "description": "Local competitor discount", "severity": "MEDIUM", "confidence": 0.82},
        ],
    }

    result = asyncio.run(executor.run_analysis_task(
        execution_id="execution-1", cancel_event=asyncio.Event(), input_path="telecom.csv",
        sector="telecom", upload_id="upload-1", business_context=context,
    ))

    assert result["context"]["business_context"] == context
    assert result["adaptive_business"]["signal_count"] == 2
    recommendations = result["decision"]["context_recommendations"]
    assert len(recommendations) == 2
    assert recommendations[0]["evidence_id"].startswith("ABIL-execution-1-")
    assert "ADAPTIVE BUSINESS CONTEXT" in result["report_texts"]["decision_report_text"]
    assert result["execution_result"] == {"prediction_count": 1}
