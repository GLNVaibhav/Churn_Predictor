"""
backend.mappers.platform_enricher
══════════════════════════════════════════════════════════════════════
Platform enrichment — packages ``ExecutionResult`` data for full API
exposure without modifying ``ExecutionResult`` or computing business values.

Pure structural translation: reads framework-produced fields and maps
them into the persisted platform payload.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from ..contracts.analysis_response import UniversalAnalysisResponse
from ..contracts.metadata import FrameworkMetadata
from ..contracts.pipeline import PipelineStageInfo, PipelineSummary
from ..models.execution_result import ExecutionResult
from ..utils import safe_get, to_serializable


def build_framework_metadata(sector: Optional[str] = None) -> FrameworkMetadata:
    """Read version constants from universal_churn — no computation."""
    try:
        from universal_churn.config import (
            PIPELINE_VERSION, COVERAGE_ALGORITHM_VERSION,
            SECTOR_MODEL_VERSION, UNIVERSAL_MODEL_VERSION,
        )
        from universal_churn.prediction_intelligence import PREDICTION_INTELLIGENCE_VERSION
        try:
            from universal_churn.knowledge_base import KnowledgeBase
            kb_version = KnowledgeBase().version
        except Exception:
            kb_version = None
        prediction_version = (
            SECTOR_MODEL_VERSION if sector else UNIVERSAL_MODEL_VERSION
        )
        return FrameworkMetadata(
            framework_version=PIPELINE_VERSION,
            knowledge_base_version=kb_version,
            coverage_version=COVERAGE_ALGORITHM_VERSION,
            routing_version=PIPELINE_VERSION,
            prediction_version=prediction_version,
            decision_version=PREDICTION_INTELLIGENCE_VERSION,
            prediction_intelligence_version=PREDICTION_INTELLIGENCE_VERSION,
        )
    except Exception:
        return FrameworkMetadata()


def build_pipeline_summary(result: ExecutionResult) -> PipelineSummary:
    """Build stage timeline from sections present in ``ExecutionResult``."""
    stages: List[PipelineStageInfo] = []

    def _stage(name: str, present: bool, desc: str, status: str = "OK") -> None:
        if present:
            stages.append(PipelineStageInfo(name=name, status=status, description=desc))

    _stage("dataset_loaded", bool(result.metadata.input_path), "Input dataset loaded")
    _stage(
        "schema_intelligence",
        bool(result.diagnostics and result.diagnostics.get("resolutions")),
        "Schema resolution completed",
    )
    _stage(
        "feature_engineering",
        bool(result.diagnostics and result.diagnostics.get("manifest")),
        "Feature engineering manifest produced",
    )
    _stage("coverage", result.coverage is not None, _coverage_desc(result.coverage))
    _stage("quality", result.quality is not None, _quality_desc(result.quality))
    _stage("routing", result.routing is not None, _routing_desc(result.routing))
    if result.refused:
        _stage("prediction", False, result.refusal_reason or "Prediction refused", "FAILED")
    else:
        _stage("prediction", result.results_df is not None, "Prediction completed")
    _stage("reasoning", result.reasoning is not None, "Business reasoning attached")
    _stage("decision", result.decision is not None, "Decision intelligence attached")
    _stage("reports", bool(result.reports), "Reports generated")

    return PipelineSummary.from_stages(stages)


def _coverage_desc(coverage: Optional[dict]) -> str:
    if not coverage:
        return ""
    return f"Coverage {coverage.get('coverage_band', coverage.get('status', ''))} ({coverage.get('coverage_score', 0):.1%})"


def _quality_desc(quality: Optional[dict]) -> str:
    if not quality:
        return ""
    passed = "passed" if quality.get("overall_passed") else "failed"
    return f"Quality gate {passed}"


def _routing_desc(routing: Any) -> str:
    if not routing:
        return ""
    model = safe_get(routing, "selected_model")
    model_val = getattr(model, "value", model)
    return f"Routed to {model_val}"


def serialize_predictions_df(df: Optional[pd.DataFrame]) -> List[Dict[str, Any]]:
    """Convert results DataFrame to JSON-safe records — no value changes."""
    if df is None or len(df) == 0:
        return []
    records = df.to_dict(orient="records")
    return [to_serializable(r) for r in records]


def build_feature_engineering_section(result: ExecutionResult) -> Optional[Dict[str, Any]]:
    """Expose feature_engineering_manifest from diagnostics."""
    if not result.diagnostics:
        return None
    manifest = result.diagnostics.get("manifest")
    resolutions = result.diagnostics.get("resolutions")
    if not manifest and not resolutions:
        return None
    section: Dict[str, Any] = {}
    if isinstance(manifest, dict):
        section["manifest"] = to_serializable(manifest)
        section["derived_features"] = list(manifest.get("derived_features", []) or [])
        section["transformed_columns"] = list(manifest.get("transformed_columns", []) or [])
        section["encoded_columns"] = list(manifest.get("encoded_columns", []) or [])
        section["dropped_columns"] = list(manifest.get("dropped_columns", []) or [])
        section["generated_features"] = list(manifest.get("generated_features", []) or [])
    if resolutions is not None:
        section["resolutions"] = to_serializable(resolutions)
    return section or None


def enrich_platform_payload(
    response: UniversalAnalysisResponse,
    execution_result: ExecutionResult,
    *,
    upload_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Merge API response with full platform exposure fields.

    Additive only — existing response keys are preserved unchanged.
    """
    payload = response.to_dict()

    metadata = build_framework_metadata(sector=execution_result.sector)
    payload["metadata"] = metadata.to_dict()

    pipeline = build_pipeline_summary(execution_result)
    payload["pipeline"] = pipeline.to_dict()
    payload["pipeline_state"] = pipeline.to_dict()

    payload["predictions"] = serialize_predictions_df(execution_result.results_df)

    payload["report_texts"] = to_serializable(execution_result.reports)

    payload["diagnostics"] = to_serializable(execution_result.diagnostics)

    fe_section = build_feature_engineering_section(execution_result)
    if fe_section:
        payload["feature_engineering"] = fe_section

    payload["execution_state"] = {
        "refused": execution_result.refused,
        "refusal_reason": execution_result.refusal_reason,
        "mode": execution_result.mode,
        "input_path": execution_result.metadata.input_path,
    }

    if execution_result.coverage and isinstance(execution_result.coverage, dict):
        detail = execution_result.coverage.get("detail")
        if detail and payload.get("coverage"):
            payload["coverage"]["detail"] = to_serializable(detail)
        explanation = execution_result.coverage.get("explanation") or execution_result.coverage.get("routing_reason")
        if explanation and payload.get("coverage"):
            payload["coverage"]["explanation"] = explanation

    if execution_result.quality and isinstance(execution_result.quality, dict):
        q = payload.get("quality") or {}
        for key in ("column_results", "leakage_flagged", "duplicate_columns", "duplicate_info"):
            if key in execution_result.quality:
                q[key] = to_serializable(execution_result.quality[key])
        payload["quality"] = q

    if upload_id:
        payload["upload_id"] = upload_id

    payload["execution_result"] = execution_result.to_dict(include_dataframe=False)

    return payload
