"""
Integration tests for backend.services (AnalysisService, PipelineService,
ReportService). Like test_framework_adapter.py, these exercise the real
universal_churn pipeline against golden datasets and skip when the
required trained artifacts aren't present in this environment.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.contracts import UniversalAnalysisResponse
from backend.exceptions import ServiceInitializationError
from backend.services import AnalysisService, PipelineService, ReportService

UNIVERSAL_MODEL_PATH = Path("outputs/universal/universal_xgb_model.pkl")
requires_models = pytest.mark.skipif(
    not UNIVERSAL_MODEL_PATH.exists(),
    reason="universal model artifact not trained in this environment",
)

GOLDEN_TELECOM = "tests/golden_telecom.csv"


# ── AnalysisService ──────────────────────────────────────────────

def test_analysis_service_requires_initialize():
    service = AnalysisService()
    with pytest.raises(ServiceInitializationError):
        service.execute(input_path=GOLDEN_TELECOM, mode="auto")


@requires_models
def test_analysis_service_execute_returns_valid_response():
    service = AnalysisService().initialize()
    bundle = service.execute(input_path=GOLDEN_TELECOM, mode="auto")
    response = bundle.response
    assert response.execution.status == "SUCCEEDED"
    assert response.dataset.sector is not None
    assert response.coverage is not None
    assert response.routing is not None
    assert bundle.execution_result.sector is not None
    service.shutdown()


@requires_models
def test_analysis_service_execute_with_reports():
    service = AnalysisService().initialize()
    bundle = service.execute(input_path=GOLDEN_TELECOM, mode="auto", include_reports=True)
    response = bundle.response
    if response.routing and response.routing.selected_model != "CRITICAL_UNRELIABLE":
        assert response.reports is not None or bundle.execution_result.reports


@requires_models
def test_analysis_service_response_is_json_serializable():
    import json
    service = AnalysisService().initialize()
    bundle = service.execute(input_path=GOLDEN_TELECOM, mode="auto")
    payload = json.dumps(bundle.response.to_dict())
    assert bundle.response.execution.execution_id in payload


def test_analysis_service_wraps_framework_errors():
    from backend.exceptions import FrameworkExecutionError
    service = AnalysisService().initialize()
    with pytest.raises(FrameworkExecutionError):
        service.execute(input_path="does_not_exist.csv", mode="auto")


# ── PipelineService ──────────────────────────────────────────────

def test_pipeline_service_requires_initialize():
    service = PipelineService()
    with pytest.raises(ServiceInitializationError):
        service.list_models()


def test_pipeline_service_lists_known_models():
    service = PipelineService().initialize()
    models = service.list_models()
    names = {m.model_name for m in models}
    assert "universal_cross_sector_model" in names
    assert any(name.endswith("_sector_model") for name in names)


def test_pipeline_service_summary_counts_match_registry():
    service = PipelineService().initialize()
    models = service.list_models()
    summary = service.summary()
    assert summary.total_stages == len(models)


# ── ReportService ────────────────────────────────────────────────

def test_report_service_degrades_gracefully_on_missing_inputs():
    from backend.models.execution_result import ExecutionResult
    service = ReportService()
    fake_result = ExecutionResult.from_framework_output(
        sector="telecom", mode="auto",
    )
    texts = service.generate_reports(fake_result)
    assert texts == {}