"""
backend.mappers.framework_mapper
══════════════════════════════════════════════════════════════════════
``FrameworkMapper`` — PURE TRANSLATION LAYER.

Converts ``ExecutionResult`` → ``UniversalAnalysisResponse`` (API DTOs).

FORBIDDEN in this module:
    - computing averages, scores, counts, confidence
    - generating business summaries
    - modifying framework output
    - any Type-A business aggregation

ALLOWED:
    ExecutionResult → API DTO (field-for-field translation only)

Type-B presentation aggregation (KPI roll-ups) lives in
``backend.presentation`` and is applied by ``AnalysisService`` before
this mapper is invoked.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..contracts.analysis_response import (
    UniversalAnalysisResponse,
    CoverageSummary,
    ConceptConfidenceSummary,
    QualitySummary,
    RoutingSummary,
    PredictionSummary,
    PredictionExplanationSummary,
    DecisionSummary,
    ReportReference,
)
from ..contracts.execution import ExecutionInfo
from ..contracts.dataset import DatasetInfo
from ..contracts.pipeline import PipelineSummary
from ..contracts.metadata import FrameworkMetadata
from ..exceptions import UnsupportedFrameworkOutputError
from ..models.execution_result import ExecutionResult
from ..utils import safe_get


class FrameworkMapper:
    """
    Stateless pure translator — ``ExecutionResult`` in, API DTO out.
    """

    # ── section translators (field-for-field only) ───────────────

    def map_coverage(self, coverage: Optional[Dict[str, Any]]) -> Optional[CoverageSummary]:
        if coverage is None:
            return None
        if not isinstance(coverage, dict):
            raise UnsupportedFrameworkOutputError(
                "map_coverage() expects the API coverage contract adapted "
                "from a typed UCIF CoverageResult; got "
                f"{type(coverage).__name__}."
            )
        return CoverageSummary.from_dict(coverage)

    def map_concept_confidence(
        self, coverage: Optional[Dict[str, Any]],
    ) -> Optional[ConceptConfidenceSummary]:
        if not coverage or not isinstance(coverage, dict):
            return None
        concept_data = coverage.get("concept_confidence")
        if not concept_data or concept_data.get("error"):
            return None
        return ConceptConfidenceSummary.from_dict(concept_data)

    def map_quality(self, quality: Optional[Dict[str, Any]]) -> Optional[QualitySummary]:
        if quality is None:
            return None
        if not isinstance(quality, dict):
            raise UnsupportedFrameworkOutputError(
                "map_quality() expects the dict returned by "
                "quality_gate.run_quality_gate(); got "
                f"{type(quality).__name__}."
            )
        return QualitySummary.from_dict(quality)

    def map_routing(self, routing_decision: Optional[Any]) -> Optional[RoutingSummary]:
        if routing_decision is None:
            return None

        selected_model = safe_get(routing_decision, "selected_model")
        selected_model_value = getattr(selected_model, "value", selected_model)
        reliability = safe_get(routing_decision, "reliability")
        reliability_value = getattr(reliability, "value", reliability)

        return RoutingSummary(
            selected_model=selected_model_value or "UNKNOWN",
            selected_pipeline=safe_get(routing_decision, "selected_pipeline", "") or "",
            prediction_mode=str(safe_get(routing_decision, "prediction_mode", "") or ""),
            routing_reason=safe_get(routing_decision, "routing_reason", "") or "",
            coverage_score=safe_get(routing_decision, "coverage_score", 0.0) or 0.0,
            coverage_band=safe_get(routing_decision, "coverage_band", "Unknown") or "Unknown",
            quality_score=safe_get(routing_decision, "quality_score", 0.0) or 0.0,
            quality_status=safe_get(routing_decision, "quality_status", "Unknown") or "Unknown",
            concept_confidence=safe_get(routing_decision, "concept_confidence"),
            reliability=reliability_value or "Unknown",
            model_artifact=safe_get(routing_decision, "model_artifact"),
            warnings=list(safe_get(routing_decision, "warnings", []) or []),
        )

    def map_prediction_explanation(
        self, explanation_report: Optional[Any],
    ) -> Optional[PredictionExplanationSummary]:
        if explanation_report is None:
            return None

        narrative = safe_get(explanation_report, "dataset_narrative")
        dataset = safe_get(explanation_report, "dataset_explanation")

        return PredictionExplanationSummary(
            headline=safe_get(narrative, "headline"),
            reason_text=safe_get(narrative, "reason_text"),
            recommendation_text=safe_get(narrative, "recommendation_text"),
            overall_business_health=safe_get(dataset, "overall_business_health"),
            overall_customer_risk=safe_get(dataset, "overall_customer_risk"),
            dominant_findings=list(safe_get(dataset, "dominant_findings", []) or []),
        )

    def map_decision(self, assessment: Optional[Any]) -> Optional[DecisionSummary]:
        if assessment is None:
            return None

        decision_readiness = safe_get(assessment, "decision_readiness")
        decision_readiness_value = getattr(decision_readiness, "value", decision_readiness)
        risk_level = safe_get(assessment, "risk_level")
        risk_level_value = getattr(risk_level, "value", risk_level)

        return DecisionSummary(
            decision_readiness=decision_readiness_value,
            overall_confidence=safe_get(assessment, "overall_confidence"),
            business_confidence=safe_get(assessment, "business_confidence"),
            technical_confidence=safe_get(assessment, "technical_confidence"),
            evidence_strength=safe_get(assessment, "evidence_strength"),
            risk_level=risk_level_value,
            recommended_action=safe_get(assessment, "recommended_action"),
            warnings=list(safe_get(assessment, "warnings", []) or []),
        )

    def map_reports(
        self, report_texts: Optional[Dict[str, str]], execution_id: str
    ) -> Optional[List[ReportReference]]:
        if not report_texts:
            return None
        from datetime import datetime, timezone
        now_str = datetime.now(timezone.utc).isoformat()
        refs = []
        for key, text in report_texts.items():
            if not text:
                continue
            report_type = key.replace("_report_text", "")
            report_id = f"{execution_id}_{report_type}"
            title = report_type.replace("_", " ").title()
            refs.append(ReportReference(
                id=report_id,
                type=report_type,
                title=title,
                created_at=now_str,
                location=f"/reports/{report_id}"
            ))
        return refs

    def collect_warnings(
        self,
        routing_summary: Optional[RoutingSummary] = None,
        quality_summary: Optional[QualitySummary] = None,
        decision_summary: Optional[DecisionSummary] = None,
        extra: Optional[List[str]] = None,
    ) -> List[str]:
        """Flatten and de-duplicate warnings already produced by sections."""
        collected: List[str] = []
        if routing_summary is not None:
            collected.extend(routing_summary.warnings)
        if quality_summary is not None and quality_summary.leakage_warned:
            collected.extend(
                f"Elevated correlation with target ({c})" for c in quality_summary.leakage_warned
            )
        if decision_summary is not None:
            collected.extend(decision_summary.warnings)
        if extra:
            collected.extend(extra)

        seen: List[str] = []
        for w in collected:
            if w not in seen:
                seen.append(w)
        return seen

    # ── full response assembly ──────────────────────────────────

    def build_response(
        self,
        execution: ExecutionInfo,
        execution_result: ExecutionResult,
        dataset: Optional[DatasetInfo] = None,
        pipeline: Optional[PipelineSummary] = None,
        prediction_summary: Optional[PredictionSummary] = None,
        metadata: Optional[FrameworkMetadata] = None,
        extra_warnings: Optional[List[str]] = None,
    ) -> UniversalAnalysisResponse:
        """
        Translate ``ExecutionResult`` → ``UniversalAnalysisResponse``.

        Pure field-for-field translation — no computation.
        ``prediction_summary`` must be pre-built by the presentation layer.
        """
        coverage_summary = self.map_coverage(execution_result.coverage)
        concept_confidence_summary = self.map_concept_confidence(execution_result.coverage)
        quality_summary = self.map_quality(execution_result.quality)
        routing_summary = self.map_routing(execution_result.routing)
        explanation_summary = self.map_prediction_explanation(execution_result.reasoning)
        decision_summary = self.map_decision(execution_result.decision)
        reports_list = self.map_reports(execution_result.reports, execution.execution_id)

        warnings = self.collect_warnings(
            routing_summary=routing_summary,
            quality_summary=quality_summary,
            decision_summary=decision_summary,
            extra=extra_warnings,
        )

        return UniversalAnalysisResponse(
            execution=execution,
            dataset=dataset,
            pipeline=pipeline,
            coverage=coverage_summary,
            concept_confidence=concept_confidence_summary,
            quality=quality_summary,
            routing=routing_summary,
            prediction=prediction_summary,
            prediction_explanation=explanation_summary,
            decision=decision_summary,
            reports=reports_list,
            warnings=warnings,
            metadata=metadata,
        )

    # ── backward-compatible convenience (individual map_* callers) ──

    def map_prediction(self, results: Optional[Any]) -> Optional[PredictionSummary]:
        """
        Deprecated path — delegates to presentation layer.

        Kept for existing unit tests that call ``map_prediction`` directly.
        """
        from ..presentation.prediction_rollup import build_prediction_summary
        return build_prediction_summary(results)
