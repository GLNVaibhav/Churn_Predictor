"""
backend.mappers.framework_mapper
══════════════════════════════════════════════════════════════════════
``FrameworkMapper`` — converts existing framework result objects into
``backend.contracts.UniversalAnalysisResponse``.

NON-NEGOTIABLE RULE: this class performs NO business logic.

    NO calculations   — every number here was already computed by
                        coverage.py / quality_gate.py / routing.py /
                        decision_intelligence.py / prediction_intelligence.
    NO validation      — the framework's own gates (quality_gate.py's
                        leakage check, routing.py's CRITICAL_UNRELIABLE
                        rejection) already ran before this mapper is
                        ever called.
    NO routing          — routing.route() already decided which model
                        ran; this mapper only reads the resulting
                        RoutingDecision.
    NO reasoning        — business_reasoning.py / prediction_explanation.py
                        already produced whatever narrative exists.

Every method below is a pure, side-effect-free reshape: read fields
off a framework object (dict OR typed dataclass — see
``backend.utils.safe_get``), construct the matching
``backend.contracts`` section, and return it. If a framework object is
``None`` or missing entirely, the corresponding section is ``None`` —
never fabricated, never defaulted to a "plausible-looking" value.

Input shapes accepted
------------------------
Every ``build_*`` method accepts EITHER the raw dict a framework
function returns (e.g. ``coverage.compute_coverage_score()``'s dict,
``quality_gate.run_quality_gate()``'s dict) OR the typed object a
framework module already wraps it in (e.g. ``routing.RoutingDecision``,
``decision_intelligence.DecisionAssessment``). This mirrors the
dict-or-adapter convenience ``routing.route()`` itself already offers
its callers — the mapper does not force every caller to pre-adapt
framework output before handing it over.
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
from ..contracts.pipeline import PipelineSummary, PipelineStageInfo
from ..contracts.metadata import FrameworkMetadata
from ..exceptions import UnsupportedFrameworkOutputError
from ..utils import safe_get


class FrameworkMapper:
    """
    Stateless — every method is effectively a ``@staticmethod``
    (kept as instance methods so a future caller can subclass this to
    add, e.g., logging/telemetry around each mapping call without
    touching the mapping logic itself).
    """

    # ── coverage ─────────────────────────────────────────────────

    def map_coverage(self, coverage: Optional[Dict[str, Any]]) -> Optional[CoverageSummary]:
        """``coverage`` is ``coverage.compute_coverage_score()``'s
        return dict, or ``None`` if coverage was never computed for
        this run."""
        if coverage is None:
            return None
        if not isinstance(coverage, dict):
            raise UnsupportedFrameworkOutputError(
                "map_coverage() expects the dict returned by "
                "coverage.compute_coverage_score(); got "
                f"{type(coverage).__name__}."
            )
        return CoverageSummary.from_dict(coverage)

    # ── concept confidence ──────────────────────────────────────

    def map_concept_confidence(
        self, coverage: Optional[Dict[str, Any]],
    ) -> Optional[ConceptConfidenceSummary]:
        """
        Concept confidence is embedded INSIDE the coverage dict by
        ``coverage.compute_coverage_score()`` (its ``'concept_confidence'``
        key) rather than returned separately — this mapper reads it
        from there rather than requiring a second framework call.
        """
        if not coverage or not isinstance(coverage, dict):
            return None
        concept_data = coverage.get("concept_confidence")
        if not concept_data or concept_data.get("error"):
            return None
        return ConceptConfidenceSummary.from_dict(concept_data)

    # ── quality ──────────────────────────────────────────────────

    def map_quality(self, quality: Optional[Dict[str, Any]]) -> Optional[QualitySummary]:
        """``quality`` is ``quality_gate.run_quality_gate()``'s return
        dict, or ``None`` if the quality gate was never run for this
        call path (e.g. a universal-mode fallback that reused a
        precomputed coverage — see ``universal_pipeline.predict_universal``'s
        docstring)."""
        if quality is None:
            return None
        if not isinstance(quality, dict):
            raise UnsupportedFrameworkOutputError(
                "map_quality() expects the dict returned by "
                "quality_gate.run_quality_gate(); got "
                f"{type(quality).__name__}."
            )
        return QualitySummary.from_dict(quality)

    # ── routing ──────────────────────────────────────────────────

    def map_routing(self, routing_decision: Optional[Any]) -> Optional[RoutingSummary]:
        """
        ``routing_decision`` is a ``routing.RoutingDecision`` instance
        (or ``None`` if routing never ran — e.g. an error before
        reaching ``routing.route()``). Reads only already-computed
        attributes/``report_fields()`` — never re-derives a reliability
        band or routing reason.
        """
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

    # ── prediction (dataset-level roll-up) ──────────────────────

    def map_prediction(self, results: Optional[Any]) -> Optional[PredictionSummary]:
        """
        ``results`` is the prediction ``results`` DataFrame every
        ``sector_pipeline.py`` / ``universal_pipeline.py`` call
        produces, or ``None`` if prediction never ran (e.g. a refused
        input). Reads only already-computed columns — no aggregation
        logic beyond counting/averaging values that already exist
        per-row.
        """
        if results is None:
            return None
        try:
            n_rows = len(results)
        except TypeError:
            raise UnsupportedFrameworkOutputError(
                "map_prediction() expects a DataFrame-like object "
                "(supports len()) with Predicted_Churn/Churn_Probability/"
                "Risk_Level/Prediction_Model/Prediction_Mode columns."
            )
        if n_rows == 0:
            return PredictionSummary(rows=0)

        churn_col = results["Predicted_Churn"] if "Predicted_Churn" in results.columns else None
        prob_col = results["Churn_Probability"] if "Churn_Probability" in results.columns else None
        risk_col = results["Risk_Level"] if "Risk_Level" in results.columns else None

        predicted_churners = int((churn_col == "Yes").sum()) if churn_col is not None else 0
        average_probability = float(prob_col.mean()) if prob_col is not None else 0.0
        risk_distribution = (
            {str(k): int(v) for k, v in risk_col.value_counts().to_dict().items()}
            if risk_col is not None else {}
        )
        prediction_model = (
            str(results["Prediction_Model"].iloc[0])
            if "Prediction_Model" in results.columns else None
        )
        prediction_mode = (
            str(results["Prediction_Mode"].iloc[0])
            if "Prediction_Mode" in results.columns else None
        )

        return PredictionSummary(
            rows=n_rows,
            predicted_churners=predicted_churners,
            average_probability=round(average_probability, 4),
            risk_distribution=risk_distribution,
            prediction_model=prediction_model,
            prediction_mode=prediction_mode,
        )

    # ── prediction explanation ──────────────────────────────────

    def map_prediction_explanation(
        self, explanation_report: Optional[Any],
    ) -> Optional[PredictionExplanationSummary]:
        """``explanation_report`` is a
        ``prediction_explanation.PredictionExplanationReport``, or
        ``None`` if explanation was never built for this run."""
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

    # ── decision ─────────────────────────────────────────────────

    def map_decision(self, assessment: Optional[Any]) -> Optional[DecisionSummary]:
        """``assessment`` is a
        ``decision_intelligence.DecisionAssessment``, or ``None`` if
        Decision Intelligence was never invoked for this run."""
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

    # ── reports (independent references) ─────────────────────────

    def map_reports(
        self, report_texts: Optional[Dict[str, str]], execution_id: str
    ) -> Optional[List[ReportReference]]:
        """
        Build the list of ReportReference objects.
        """
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

    # ── warnings roll-up ─────────────────────────────────────────

    def collect_warnings(
        self,
        routing_summary: Optional[RoutingSummary] = None,
        quality_summary: Optional[QualitySummary] = None,
        decision_summary: Optional[DecisionSummary] = None,
        extra: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Flatten and de-duplicate warnings already produced by other
        sections — no new warning conditions are invented here.
        """
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
        dataset: Optional[DatasetInfo] = None,
        pipeline: Optional[PipelineSummary] = None,
        coverage: Optional[Dict[str, Any]] = None,
        quality: Optional[Dict[str, Any]] = None,
        routing_decision: Optional[Any] = None,
        results: Optional[Any] = None,
        explanation_report: Optional[Any] = None,
        decision_assessment: Optional[Any] = None,
        report_texts: Optional[Dict[str, str]] = None,
        metadata: Optional[FrameworkMetadata] = None,
        extra_warnings: Optional[List[str]] = None,
    ) -> UniversalAnalysisResponse:
        """
        One-call convenience: map every optional framework output and
        assemble the final ``UniversalAnalysisResponse``. Every
        parameter beyond ``execution`` is optional — callers pass
        whatever their run actually produced (e.g. a refused
        prediction passes ``coverage``/``quality``/``routing_decision``
        but leaves ``results``/``explanation_report``/
        ``decision_assessment`` as ``None``).

        This method still performs no computation of its own — it is
        purely sequential delegation to the ``map_*`` methods above,
        followed by one aggregation step (``collect_warnings``) that
        only flattens/deduplicates values those methods already
        produced.
        """
        coverage_summary = self.map_coverage(coverage)
        concept_confidence_summary = self.map_concept_confidence(coverage)
        quality_summary = self.map_quality(quality)
        routing_summary = self.map_routing(routing_decision)
        prediction_summary = self.map_prediction(results)
        explanation_summary = self.map_prediction_explanation(explanation_report)
        decision_summary = self.map_decision(decision_assessment)
        reports_list = self.map_reports(report_texts, execution.execution_id)

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
