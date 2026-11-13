"""Run a read-only, real-model UCIF workflow on one external pair per sector.

The CSVs and ABIL documents are evaluation inputs only. This runner does not
train, tune, persist predictions, or modify source data or model artifacts.

Run from the repository root, supplying the external input directories:
    python scripts/verify_ucif_local_framework.py --data-root <csv-root> --contexts-root <abil-root>

The paths can instead be provided through UCIF_EXTERNAL_EVAL_ROOT and
UCIF_EXTERNAL_ABIL_ROOT. They are never embedded in this repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import asyncio
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

from backend.runtime.executor import run_analysis_task
from backend.services.analysis_service import AnalysisService
from universal_churn.config import SECTOR_CONFIG
from universal_churn.explainability import SHAP_AVAILABLE


DATA_ROOT: Path | None = None
CONTEXT_ROOT: Path | None = None
ARTIFACT_MANIFEST = REPO_ROOT / "outputs/evaluation/old_vs_new/model_artifact_manifest.json"

CASES = (
    ("Telecom", "Airtel_Telecom_400.csv", "Airtel_Context.json"),
    ("Banking", "Axis_Banking_450.csv", "Axis_Context.json"),
    ("Ecommerce", "Amazon_Ecommerce_700.csv", "Amazon_Context.json"),
    ("Healthcare", "Apollo_Healthcare_500.csv", "Apollo_Context.json"),
)
SECTOR_ACTIONS = {
    "Telecom": ("Network Quality", "network or service-reliability"),
    "Banking": ("Credit Risk", "authorized case review"),
    "Ecommerce": ("Logistics", "fulfillment, return, or inventory"),
    "Healthcare": ("Clinical Quality", "clinical or safety signal"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def current_artifact_hashes() -> dict[str, str]:
    manifest = json.loads(ARTIFACT_MANIFEST.read_text(encoding="utf-8"))
    expected = manifest["hashes"]["current_dev_HEAD"]
    actual: dict[str, str] = {}
    for relative_path in expected:
        path = REPO_ROOT / relative_path
        if not path.is_file():
            raise AssertionError(f"Active model artifact is missing: {relative_path}")
        actual[relative_path] = sha256(path)
    if len(actual) != 34 or actual != expected:
        raise AssertionError(
            f"Active model artifact integrity mismatch ({len(actual)} checked; expected 34)."
        )
    return actual


def get_selected_model(routing: Any) -> str:
    selected = getattr(routing, "selected_model", None)
    return str(getattr(selected, "value", selected) or "UNKNOWN")


def run_case(sector_label: str, csv_name: str, context_name: str) -> dict[str, Any]:
    if DATA_ROOT is None or CONTEXT_ROOT is None:
        raise RuntimeError("Evaluation roots must be configured before running cases.")
    sector_dir = {"Ecommerce": "Ecommerce"}.get(sector_label, sector_label)
    dataset = DATA_ROOT / sector_dir / csv_name
    context_path = CONTEXT_ROOT / sector_dir / context_name
    if not dataset.is_file() or not context_path.is_file():
        raise FileNotFoundError(f"Required evaluation pair is missing for {sector_label}.")

    input_hash_before = sha256(dataset)
    context_hash_before = sha256(context_path)
    raw = pd.read_csv(dataset)
    context = json.loads(context_path.read_text(encoding="utf-8"))

    def execute(execution_id: str, business_context: dict[str, Any] | None) -> dict[str, Any]:
        return asyncio.run(run_analysis_task(
            execution_id=execution_id,
            cancel_event=asyncio.Event(),
            input_path=str(dataset),
            mode="auto",
            explain=False,
            include_reports=True,
            business_context=business_context,
        ))

    plain = execute(f"local-e2e-{sector_label.lower()}-plain", None)
    with_context = execute(f"local-e2e-{sector_label.lower()}-abil", context)
    predictions = plain.get("predictions") or []
    context_predictions = with_context.get("predictions") or []
    if plain.get("execution", {}).get("status") != "SUCCEEDED" or with_context.get("execution", {}).get("status") != "SUCCEEDED":
        raise AssertionError(f"{sector_label}: an analysis execution did not succeed.")
    if len(predictions) != len(raw) or len(context_predictions) != len(raw):
        raise AssertionError(f"{sector_label}: prediction count differs from input row count.")
    prediction_fields = ("Predicted_Churn", "Churn_Probability")
    plain_signature = [tuple(row.get(field) for field in prediction_fields) for row in predictions]
    context_signature = [tuple(row.get(field) for field in prediction_fields) for row in context_predictions]
    if plain_signature != context_signature:
        raise AssertionError(f"{sector_label}: adding ABIL context changed labels or churn probabilities.")
    for row in predictions + context_predictions:
        probability = row.get("Churn_Probability")
        if not isinstance(probability, (int, float)) or not 0 <= probability <= 1:
            raise AssertionError(f"{sector_label}: invalid churn probability value.")
        if "Predicted_Churn" not in row:
            raise AssertionError(f"{sector_label}: prediction contract is incomplete.")

    sector = str((with_context.get("dataset") or {}).get("sector") or with_context.get("sector") or "")
    if sector.lower() != sector_label.lower():
        raise AssertionError(f"{sector_label}: detected sector was {sector!r}.")
    intelligence = with_context.get("semantic_intelligence") or {}
    canonical = intelligence.get("canonical_mapping") or {}
    meanings = intelligence.get("business_meanings") or []
    coverage = with_context.get("coverage") or {}
    routing = with_context.get("routing") or {}
    if not canonical.get("mappings"):
        raise AssertionError(f"{sector_label}: canonical mapping evidence is missing.")
    if not meanings:
        raise AssertionError(f"{sector_label}: semantic interpretation evidence is missing.")
    if not 0 <= float(coverage.get("coverage_score", -1)) <= 1:
        raise AssertionError(f"{sector_label}: coverage evidence is missing or invalid.")
    selected_model = str(routing.get("selected_model") or "UNKNOWN")
    pipeline = str(routing.get("selected_pipeline") or "")
    if selected_model == "UNIVERSAL_MODEL":
        artifact = REPO_ROOT / "outputs/universal/universal_xgb_model.pkl"
    elif selected_model == "FULL_SECTOR_MODEL":
        artifact = REPO_ROOT / SECTOR_CONFIG[sector]["model_path"]
    else:
        raise AssertionError(f"{sector_label}: unknown selected model {selected_model!r}.")
    if not artifact.is_file():
        raise AssertionError(f"{sector_label}: selected model artifact is unavailable.")

    abil = with_context.get("adaptive_business") or {}
    if abil.get("signal_count", 0) < 1 or not abil.get("signals"):
        raise AssertionError(f"{sector_label}: ABIL produced no contextual signals.")
    for signal in abil["signals"]:
        if not signal.get("evidence_id") or not signal.get("action") or not signal.get("rationale"):
            raise AssertionError(f"{sector_label}: ABIL recommendation lacks evidence or rationale.")
        if "does not establish" not in signal["rationale"]:
            raise AssertionError(f"{sector_label}: ABIL limitation language is missing.")
        source_recommendation = signal.get("source_recommendation")
        if source_recommendation and signal["action"].strip().casefold() == source_recommendation.strip().casefold():
            raise AssertionError(f"{sector_label}: ABIL merely repeated a source recommendation.")
    expected_category, expected_phrase = SECTOR_ACTIONS[sector_label]
    specific_signal = next(
        (item for item in abil["signals"] if item["name"] == expected_category),
        None,
    )
    if specific_signal is None or expected_phrase not in specific_signal["action"]:
        raise AssertionError(f"{sector_label}: expected evidence-specific ABIL recommendation is missing.")
    decision = with_context.get("decision") or {}
    recommendations = decision.get("context_recommendations") or []
    if not decision or not recommendations:
        raise AssertionError(f"{sector_label}: decision intelligence did not include ABIL recommendations.")
    if not with_context.get("diagnostics") or not with_context["diagnostics"].get("intelligence"):
        raise AssertionError(f"{sector_label}: semantic and routing diagnostics are missing.")
    report_texts = with_context.get("report_texts") or {}
    if not report_texts or not with_context.get("reports"):
        raise AssertionError(f"{sector_label}: report text or report references were not generated.")
    decision_report = report_texts.get("decision_report_text", "")
    if abil.get("signal_count") and "ADAPTIVE BUSINESS CONTEXT" not in decision_report:
        raise AssertionError(f"{sector_label}: ABIL evidence was not appended to the decision report.")

    if sha256(dataset) != input_hash_before or sha256(context_path) != context_hash_before:
        raise AssertionError(f"{sector_label}: an external evaluation input changed during verification.")

    return {
        "sector": sector,
        "rows": len(raw),
        "predictions": len(predictions),
        "coverage": float(coverage["coverage_score"]),
        "coverage_status": coverage.get("status"),
        "pipeline": pipeline,
        "model": selected_model,
        "artifact": str(artifact.relative_to(REPO_ROOT)),
        "semantic_meanings": len(meanings),
        "canonical_mappings": len(canonical["mappings"]),
        "semantic_graph_present": bool(intelligence.get("semantic_graph")),
        "ABIL_signals": abil["signal_count"],
        "decision_recommendations": len(recommendations),
        "decision": "available",
        "diagnostics": "available",
        "prediction_explanation": "not requested (explain=False)",
        "report_sections": sorted(report_texts),
        "ABIL_appended_to_decision_report": "ADAPTIVE BUSINESS CONTEXT" in decision_report,
        "ABIL_prediction_invariance": True,
        "specific_recommendation": {
            "signal": specific_signal["name"],
            "action": specific_signal["action"],
            "evidence_id": specific_signal["evidence_id"],
        },
    }


def verify_explicit_sector_models() -> list[dict[str, str]]:
    """Exercise trained sector estimators separately from auto-routing.

    These explicit-mode checks establish model availability/compatibility;
    they do not claim the supplied external schemas qualify for auto-routing.
    """
    checks: list[dict[str, str]] = []
    if DATA_ROOT is None:
        raise RuntimeError("Evaluation root must be configured before running sector checks.")
    service = AnalysisService().initialize()
    try:
        for sector, filename, folder in (
            ("banking", "Axis_Banking_450.csv", "Banking"),
            ("healthcare", "Apollo_Healthcare_500.csv", "Healthcare"),
        ):
            dataset = DATA_ROOT / folder / filename
            model_path = REPO_ROOT / SECTOR_CONFIG[sector]["model_path"]
            if not dataset.is_file() or not model_path.is_file():
                raise FileNotFoundError(f"Sector model smoke-test input/artifact missing for {sector}.")
            result = service.execute(
                input_path=str(dataset), sector=sector, mode="sector",
                explain=False, include_reports=False,
            ).execution_result
            if result.refused or result.results_df is None or len(result.results_df) != len(pd.read_csv(dataset)):
                raise AssertionError(f"Explicit sector inference failed for {sector}.")
            if get_selected_model(result.routing) != "FULL_SECTOR_MODEL":
                raise AssertionError(f"Explicit {sector} inference did not identify its sector model.")
            checks.append({
                "sector": sector,
                "mode": "explicit sector (not auto-routing)",
                "artifact": str(model_path.relative_to(REPO_ROOT)),
                "status": "PASS",
            })
    finally:
        service.shutdown()
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        default=os.environ.get("UCIF_EXTERNAL_EVAL_ROOT"),
        help="Directory containing the sector CSV folders (or UCIF_EXTERNAL_EVAL_ROOT).",
    )
    parser.add_argument(
        "--contexts-root",
        default=os.environ.get("UCIF_EXTERNAL_ABIL_ROOT"),
        help="Directory containing the sector ABIL JSON folders (or UCIF_EXTERNAL_ABIL_ROOT).",
    )
    args = parser.parse_args()
    if not args.data_root:
        parser.error("provide --data-root or set UCIF_EXTERNAL_EVAL_ROOT")
    if not args.contexts_root:
        parser.error("provide --contexts-root or set UCIF_EXTERNAL_ABIL_ROOT")
    global DATA_ROOT, CONTEXT_ROOT
    DATA_ROOT = Path(args.data_root).expanduser().resolve()
    CONTEXT_ROOT = Path(args.contexts_root).expanduser().resolve()
    if not DATA_ROOT.is_dir():
        parser.error("--data-root must be an existing directory")
    if not CONTEXT_ROOT.is_dir():
        parser.error("--contexts-root must be an existing directory")
    if not ARTIFACT_MANIFEST.is_file():
        raise FileNotFoundError("The committed 34-artifact integrity manifest is missing.")
    artifacts_before = current_artifact_hashes()
    results = [run_case(*case) for case in CASES]
    sector_model_checks = verify_explicit_sector_models()
    artifacts_after = current_artifact_hashes()
    if artifacts_before != artifacts_after:
        raise AssertionError("An active model artifact changed during verification.")

    for result in results:
        print(json.dumps(result, sort_keys=True))
    for result in sector_model_checks:
        print(json.dumps(result, sort_keys=True))
    print(json.dumps({
        "status": "PASS",
        "cases": len(results),
        "active_model_artifacts_unchanged": len(artifacts_after),
        "explicit_sector_model_checks": len(sector_model_checks),
        "per_record_shap_available_as_optional_cli_path": SHAP_AVAILABLE,
        "per_record_shap_exercised": False,
        "backend_per_record_shap_payload_reviewed_absent": True,
        "frontend_proxy_or_hosted_authentication_tested": False,
        "training_performed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"UCIF local framework verification FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
