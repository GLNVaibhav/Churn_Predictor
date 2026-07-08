"""
Tests for golden contract generation and regression artifact integrity.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN_DIR = REPO_ROOT / "backend" / "tests" / "golden"
UNIVERSAL_MODEL = REPO_ROOT / "outputs" / "universal" / "universal_xgb_model.pkl"

requires_models = pytest.mark.skipif(
    not UNIVERSAL_MODEL.exists(),
    reason="universal model artifact not trained in this environment",
)


@requires_models
def test_generate_golden_contract_produces_both_artifacts(tmp_path):
    from scripts.generate_golden_contract import generate

    input_csv = REPO_ROOT / "tests" / "golden_telecom.csv"
    raw, normalized = generate(
        input_path=input_csv,
        mode="auto",
        output_dir=tmp_path,
    )

    framework_path = tmp_path / "golden_framework_output.json"
    execution_path = tmp_path / "golden_execution_result.json"
    assert framework_path.exists()
    assert execution_path.exists()

    if raw.get("coverage") and normalized.get("coverage"):
        assert raw["coverage"]["coverage_score"] == normalized["coverage"]["coverage_score"]

    assert raw["sector"] == normalized["metadata"]["sector"]
    assert raw["mode"] == normalized["metadata"]["mode"]


@requires_models
def test_golden_contract_regression_against_committed_artifacts():
    from scripts.generate_golden_contract import generate

    input_csv = REPO_ROOT / "tests" / "golden_telecom.csv"
    if not (GOLDEN_DIR / "golden_framework_output.json").exists():
        generate(input_path=input_csv, output_dir=GOLDEN_DIR)

    committed_framework = json.loads(
        (GOLDEN_DIR / "golden_framework_output.json").read_text(encoding="utf-8")
    )
    committed_execution = json.loads(
        (GOLDEN_DIR / "golden_execution_result.json").read_text(encoding="utf-8")
    )

    fresh_raw, fresh_normalized = generate(
        input_path=input_csv, output_dir=GOLDEN_DIR,
    )

    assert fresh_raw["sector"] == committed_framework["sector"]
    assert fresh_raw["mode"] == committed_framework["mode"]

    if committed_framework.get("coverage") and fresh_raw.get("coverage"):
        assert (
            fresh_raw["coverage"]["coverage_score"]
            == committed_framework["coverage"]["coverage_score"]
        )
        assert (
            fresh_normalized["coverage"]["coverage_score"]
            == committed_execution["coverage"]["coverage_score"]
        )
