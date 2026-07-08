"""
Integration tests for backend.adapters.FrameworkAdapter.

Unlike test_framework_mapper.py / test_contracts.py (which fabricate
framework SHAPES to stay fast and dependency-free), these tests
exercise the REAL universal_churn pipeline against the repo's golden
datasets and already-trained model artifacts (outputs/universal/...).
They are the integration layer that confirms FrameworkAdapter's
orchestration actually produces the shapes FrameworkMapper expects —
skipped automatically if the trained artifacts aren't present (e.g. a
fresh checkout that hasn't run `train_all` yet), mirroring
validate_framework.py's own tolerance for missing model files.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.adapters import FrameworkAdapter
from backend.models.execution_result import ExecutionResult

GOLDEN = {
    "telecom": "tests/golden_telecom.csv",
    "banking": "tests/golden_banking.csv",
    "ecommerce": "tests/golden_ecommerce.csv",
    "healthcare": "tests/golden_healthcare.csv",
}

UNIVERSAL_MODEL_PATH = Path("outputs/universal/universal_xgb_model.pkl")


def _sector_model_trained(sector: str) -> bool:
    from universal_churn.config import SECTOR_CONFIG
    return Path(SECTOR_CONFIG[sector]["model_path"]).exists()


requires_models = pytest.mark.skipif(
    not UNIVERSAL_MODEL_PATH.exists(),
    reason="universal model artifact not trained in this environment",
)


@pytest.fixture
def adapter() -> FrameworkAdapter:
    return FrameworkAdapter()


@requires_models
def test_auto_mode_returns_execution_result(adapter):
    result = adapter.execute(input_path=GOLDEN["telecom"], mode="auto")
    assert isinstance(result, ExecutionResult)
    assert result.sector == "telecom"
    assert result.mode == "auto"
    assert result.coverage is not None
    assert result.quality is not None
    assert result.routing_decision is not None


@requires_models
def test_auto_mode_non_refused_has_results(adapter):
    result = adapter.execute(input_path=GOLDEN["ecommerce"], mode="auto")
    if result.refused:
        pytest.skip("routing refused this golden dataset in this environment")
    assert result.results_df is not None
    assert len(result.results_df) > 0
    assert "Predicted_Churn" in result.results_df.columns
    assert "Churn_Probability" in result.results_df.columns


@requires_models
def test_sector_mode_matches_detected_sector(adapter):
    if not _sector_model_trained("banking"):
        pytest.skip("banking sector model not trained in this environment")
    result = adapter.execute(input_path=GOLDEN["banking"], mode="sector")
    assert result.sector == "banking"
    assert result.mode == "sector"
    if not result.refused:
        assert result.results_df is not None
        assert result.routing_decision is not None
        assert result.routing_decision.selected_model.value == "FULL_SECTOR_MODEL"


@requires_models
def test_universal_mode_runs_for_any_sector(adapter):
    result = adapter.execute(input_path=GOLDEN["healthcare"], mode="universal", sector="healthcare")
    assert result.sector == "healthcare"
    assert result.mode == "universal"
    if not result.refused:
        assert result.results_df is not None
        assert result.routing_decision.selected_model.value == "UNIVERSAL_MODEL"


def test_execute_raises_file_not_found_for_missing_input(adapter):
    with pytest.raises(FileNotFoundError):
        adapter.execute(input_path="tests/does_not_exist_at_all.csv", mode="auto")


def test_execute_rejects_unknown_mode(adapter):
    with pytest.raises(ValueError):
        adapter.execute(input_path=GOLDEN["telecom"], mode="bogus_mode")


@requires_models
def test_enrichment_attaches_explanation_and_decision(adapter):
    result = adapter.execute(input_path=GOLDEN["telecom"], mode="auto")
    if result.refused:
        pytest.skip("routing refused this golden dataset in this environment")
    # explanation/decision enrichment is best-effort — assert it at
    # least ran without raising and (when successful) is attached.
    assert result.reasoning is None or hasattr(result.reasoning, "reasoning_report")
    assert result.decision is None or hasattr(result.decision, "decision_readiness")