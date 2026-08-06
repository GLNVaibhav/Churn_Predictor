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
from ..presentation import build_prediction_summary
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
    """Build the API-visible execution timeline for the new UCIF architecture."""
    stages: List[PipelineStageInfo] = []
    timings = (result.diagnostics or {}).get("stage_timings") if result.diagnostics else {}
    timings = timings if isinstance(timings, dict) else {}

    def _stage(stage_id: str, name: str, present: bool, desc: str, status: str = "OK") -> None:
        if present:
            duration = timings.get(stage_id)
            stages.append(PipelineStageInfo(
                id=stage_id,
                name=name,
                status=status,
                description=desc,
                execution_time=round(duration * 1000, 2) if isinstance(duration, (int, float)) else None,
            ))

    _stage("frontend_intake", "Frontend Intake", bool(result.metadata.input_path), "Dataset submitted from the web console")
    _stage("api_contract", "API Contract", True, "FastAPI accepted the request and execution context")
    _stage("framework_mapper", "Framework Mapper", True, "Framework output mapped into public API sections")
    _stage("business_meaning", "Business Meaning", "business_meaning" in timings, "Column-level business meanings inferred")
    _stage("context_validation", "Context Validation", "context_validation" in timings, "Dataset domain context validated")
    _stage("semantic_graph", "Semantic Graph", "semantic_graph" in timings, "Semantic relationships assembled")
    _stage("canonical_mapping", "Canonical Mapping", "canonical_mapping" in timings, "Dataset fields mapped to canonical concepts")
    _stage("coverage", "Coverage Intelligence", result.coverage is not None, _coverage_desc(result.coverage))
    _stage("quality_gate", "Quality Gate", result.quality is not None, _quality_desc(result.quality))
    _stage("routing", "Routing Intelligence", result.routing is not None, _routing_desc(result.routing))
    if result.refused:
        _stage("prediction", "Prediction", False, result.refusal_reason or "Prediction refused", "FAILED")
    else:
        _stage("prediction", "Prediction", result.results_df is not None, "Prediction completed")
    _stage("prediction_explanation", "Prediction Explanation", result.reasoning is not None, "Prediction explanation attached")
    _stage("decision_intelligence", "Decision Intelligence", result.decision is not None, "Decision intelligence attached")
    _stage("reports", "Reports", bool(result.reports), "Reports generated")

    return PipelineSummary.from_stages(stages)


def build_semantic_intelligence_section(result: ExecutionResult) -> Optional[Dict[str, Any]]:
    """Expose typed UCIF intelligence evidence produced before prediction."""
    intelligence = (result.diagnostics or {}).get("intelligence") if result.diagnostics else None
    if not isinstance(intelligence, dict):
        return None
    return {
        "business_meanings": intelligence.get("business_meanings") or [],
        "context_validation": intelligence.get("context"),
        "semantic_graph": intelligence.get("semantic_graph"),
        "canonical_mapping": intelligence.get("canonical_mapping"),
        "coverage_typed": intelligence.get("coverage"),
        "routing_typed": intelligence.get("routing"),
        "stage_timings": (result.diagnostics or {}).get("stage_timings") or {},
    }


def build_framework_mapper_section(result: ExecutionResult) -> Dict[str, Any]:
    """Describe the API mapper boundary for consumers and the frontend."""
    mapped_sections = [
        name for name, present in {
            "coverage": result.coverage is not None,
            "quality": result.quality is not None,
            "routing": result.routing is not None,
            "predictions": result.results_df is not None,
            "prediction_explanation": result.reasoning is not None,
            "decision": result.decision is not None,
            "diagnostics": result.diagnostics is not None,
        }.items() if present
    ]
    return {
        "boundary": "API -> FrameworkMapper -> UCIF",
        "source_model": "backend.models.ExecutionResult",
        "target_contract": "backend.contracts.UniversalAnalysisResponse",
        "framework_runtime": "universal_churn",
        "mapped_sections": mapped_sections,
        "compatibility": {
            "coverage": "typed CoverageResult adapted to API CoverageSummary",
            "routing": "typed RoutingDecision adapted to API RoutingSummary",
            "pipeline": "typed stage timings exposed with stable API stage IDs",
        },
    }


def build_cli_output_section(result: ExecutionResult, pipeline: PipelineSummary) -> Dict[str, Any]:
    """Render the CLI-style execution output for API/UI consumers."""
    dataset_name = result.metadata.input_path or "uploaded dataset"
    coverage = result.coverage or {}
    quality = result.quality or {}
    routing = result.routing
    prediction_summary = build_prediction_summary(result.results_df)
    prediction = prediction_summary.to_dict() if prediction_summary else {}
    decision = to_serializable(result.decision) or {}
    semantic = build_semantic_intelligence_section(result) or {}
    context = semantic.get("context_validation") or {}
    graph = semantic.get("semantic_graph") or {}
    mapping = semantic.get("canonical_mapping") or {}
    meanings = semantic.get("business_meanings") or []
    timings = semantic.get("stage_timings") or {}

    def _pct(value: Any) -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "n/a"
        return f"{number * 100:.1f}%" if number <= 1 else f"{number:.1f}%"

    def _line(label: str, value: Any) -> str:
        return f"  {label:<30}: {value}"

    def _timing(stage_id: str) -> str:
        value = timings.get(stage_id)
        return f"{float(value):.3f} sec" if isinstance(value, (int, float)) else "n/a"

    selected_model = safe_get(routing, "selected_model") if routing else None
    selected_model = getattr(selected_model, "value", selected_model)

    lines: List[str] = [
        "=" * 72,
        "  UNIVERSAL CHURN INTELLIGENCE FRAMEWORK",
        "=" * 72,
        _line("Execution Mode", result.mode.upper()),
        _line("Input Dataset", dataset_name),
        _line("Detected Sector", str(result.sector or "unknown").upper()),
        _line("Framework Path", "Frontend -> API -> Framework Mapper -> UCIF"),
        "",
        "[1] Data Profiling",
        _line("Rows Analysed", prediction.get("rows", len(result.results_df) if result.results_df is not None else 0)),
        _line("Prediction Mode", prediction.get("prediction_mode", result.mode)),
        "",
        "[2] Business Meaning Intelligence",
        _line("Business Concepts Inferred", len(meanings) if isinstance(meanings, list) else 0),
        _line("Time Taken", _timing("business_meaning")),
        "",
        "[3] Context Validation",
        _line("Dominant Domain", context.get("dataset_domain", "n/a") if isinstance(context, dict) else "n/a"),
        _line("Agreement", _pct(context.get("consensus_score")) if isinstance(context, dict) else "n/a"),
        _line("Validation Result", context.get("dataset_health", "n/a") if isinstance(context, dict) else "n/a"),
        _line("Time Taken", _timing("context_validation")),
        "",
        "[4] Semantic Knowledge Graph",
        _line("Nodes / Edges", f"{graph.get('node_count', 'n/a')} / {graph.get('edge_count', 'n/a')}" if isinstance(graph, dict) else "n/a"),
        _line("Semantic Consistency", _pct(graph.get("consistency_score")) if isinstance(graph, dict) else "n/a"),
        _line("Time Taken", _timing("semantic_graph")),
        "",
        "[5] Canonical Mapping",
        _line("Resolved Columns", len(mapping.get("mappings", [])) if isinstance(mapping, dict) else "n/a"),
        _line("Mapping Quality", _pct(mapping.get("overall_confidence")) if isinstance(mapping, dict) else "n/a"),
        _line("Time Taken", _timing("canonical_mapping")),
        "",
        "[6] Coverage Intelligence",
        _line("Coverage Score", _pct(coverage.get("coverage_score"))),
        _line("Coverage Band", coverage.get("coverage_band", coverage.get("status", "n/a"))),
        _line("Concept Confidence", _pct((coverage.get("concept_confidence") or {}).get("overall_confidence"))),
        "",
        "[7] Quality Gate",
        _line("Overall Passed", quality.get("overall_passed", "n/a")),
        _line("Leakage Detected", quality.get("leakage_detected", "n/a")),
        "",
        "[8] Routing Intelligence",
        _line("Selected Model", selected_model or "n/a"),
        _line("Selected Pipeline", safe_get(routing, "selected_pipeline") if routing else "n/a"),
        _line("Routing Reason", safe_get(routing, "routing_reason") if routing else "n/a"),
        "",
        "[9] Prediction Engine",
        _line("Rows Analysed", prediction.get("rows", len(result.results_df) if result.results_df is not None else 0)),
        _line("Predicted Churners", prediction.get("predicted_churners", "n/a")),
        _line("Average Churn Probability", _pct(prediction.get("average_probability"))),
        "",
        "[10] Decision Intelligence",
        _line("Decision Readiness", decision.get("decision_readiness", "n/a") if isinstance(decision, dict) else "n/a"),
        _line("Overall Confidence", _pct(decision.get("overall_confidence")) if isinstance(decision, dict) else "n/a"),
        _line("Recommended Action", decision.get("recommended_action", "n/a") if isinstance(decision, dict) else "n/a"),
        "",
        "[11] Generated Reports",
        _line("Reports Generated", len(result.reports or {})),
        "",
        "EXECUTION SUMMARY",
        _line("Framework / Pipeline Version", "UCIF / active API contract"),
        _line("Dataset / Sector", f"{dataset_name} / {str(result.sector or 'unknown').upper()}"),
        _line("Pipeline Stages", f"{pipeline.completed}/{pipeline.total_stages} completed"),
        _line("Overall Status", pipeline.overall_status),
        "=" * 72,
    ]

    return {
        "text": "\n".join(str(line) for line in lines),
        "stages": [stage.to_dict() for stage in pipeline.stages],
        "comparison_metrics": {
            "coverage_score": coverage.get("coverage_score"),
            "concept_confidence": (coverage.get("concept_confidence") or {}).get("overall_confidence"),
            "average_churn_probability": prediction.get("average_probability"),
            "predicted_churners": prediction.get("predicted_churners"),
            "rows": prediction.get("rows", len(result.results_df) if result.results_df is not None else 0),
        },
    }


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
    dataset = payload.get("dataset") if isinstance(payload.get("dataset"), dict) else {}
    if isinstance(dataset, dict):
        dataset["sector"] = dataset.get("sector") or execution_result.sector
        payload["dataset"] = dataset
        payload["sector"] = dataset.get("sector")
        payload["filename"] = dataset.get("filename")

    metadata = build_framework_metadata(sector=execution_result.sector)
    payload["metadata"] = metadata.to_dict()

    pipeline = build_pipeline_summary(execution_result)
    payload["pipeline"] = pipeline.to_dict()
    payload["pipeline_state"] = pipeline.to_dict()
    payload["cli_output"] = to_serializable(
        build_cli_output_section(execution_result, pipeline)
    )

    payload["predictions"] = serialize_predictions_df(execution_result.results_df)

    payload["report_texts"] = to_serializable(execution_result.reports)

    payload["diagnostics"] = to_serializable(execution_result.diagnostics)
    semantic_section = build_semantic_intelligence_section(execution_result)
    if semantic_section:
        payload["semantic_intelligence"] = to_serializable(semantic_section)
    payload["framework_mapper"] = to_serializable(
        build_framework_mapper_section(execution_result)
    )

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
