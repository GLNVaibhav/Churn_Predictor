"""Adapter between the FastAPI platform layer and the UCIF framework.

The backend calls the framework through this file only. Framework logic stays
inside ``universal_churn``; this adapter selects the correct entry point,
executes it once, and packages the result for the mapper.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

import pandas as pd

from universal_churn.config import SECTOR_CONFIG
from universal_churn.decision_report import build_and_attach_decision_intelligence
from universal_churn.intelligence_pipeline import infer_intelligence
from universal_churn.prediction_explanation_report import build_and_attach_explanations
from universal_churn.preprocessing import detect_sector
from universal_churn.quality_gate import run_quality_gate
from universal_churn.sector_pipeline import SectorPipeline
from universal_churn.universal_pipeline import predict_universal

from ..models.execution_result import ExecutionResult
from ..utils import to_serializable


class FrameworkAdapter:
    """Stateless anti-corruption layer from API/runtime code into UCIF."""

    @staticmethod
    def _enrich(results: pd.DataFrame, df_raw: pd.DataFrame, sector: str) -> pd.DataFrame:
        """Attach explanation and decision intelligence exactly once."""
        results = build_and_attach_explanations(results, df_raw, sector)
        prediction_explanation = results.attrs.get("prediction_explanation")
        reasoning_report = (
            prediction_explanation.reasoning_report
            if prediction_explanation is not None
            else None
        )
        return build_and_attach_decision_intelligence(
            results=results,
            sector=sector,
            reasoning_report=reasoning_report,
        )

    @staticmethod
    def _coverage_contract(coverage: Any) -> Optional[dict]:
        """Adapt typed CoverageResult to the API mapper's stable dict contract."""
        if coverage is None or isinstance(coverage, dict):
            return coverage

        summary = getattr(coverage, "summary", None)
        assessment = getattr(coverage, "assessment", None)
        if summary is None:
            return None

        readiness = str(getattr(summary, "readiness", "Unknown") or "Unknown")
        band_by_readiness = {
            "READY": "Green",
            "PARTIAL": "Yellow",
            "DEGRADED": "Yellow",
            "NOT_READY": "Red",
        }

        issues = list(getattr(assessment, "issues", ()) or ())
        metrics = list(getattr(assessment, "metrics", ()) or ())
        high_items = [
            item
            for issue in issues
            if str(getattr(issue, "severity", "")).upper() == "HIGH"
            for item in getattr(issue, "affected_items", ()) or ()
        ]
        medium_items = [
            item
            for issue in issues
            if str(getattr(issue, "severity", "")).upper() == "MEDIUM"
            for item in getattr(issue, "affected_items", ()) or ()
        ]
        metric_scores = {
            getattr(metric, "name", ""): float(getattr(metric, "score", 0.0) or 0.0)
            for metric in metrics
            if getattr(metric, "name", "")
        }
        confidence = float(getattr(summary, "confidence_coverage", 0.0) or 0.0)

        return {
            "coverage_score": float(getattr(summary, "overall_coverage", 0.0) or 0.0),
            "status": readiness,
            "coverage_band": band_by_readiness.get(readiness.upper(), readiness),
            "missing_critical": high_items,
            "missing_high_impact": medium_items,
            "missing_all": high_items + medium_items,
            "recovered_features": [],
            "semantic_matches": [
                name for name, score in metric_scores.items() if score > 0
            ],
            "concept_confidence": {
                "overall_confidence": confidence,
                "reconstructable_concepts": sum(
                    1 for score in metric_scores.values() if score > 0
                ),
                "total_concepts": len(metric_scores) or 1,
                "concepts_reconstructable": confidence >= 0.5,
                "per_concept": {
                    name: {"confidence": score, "reconstructable": score > 0}
                    for name, score in metric_scores.items()
                },
            },
        }

    @staticmethod
    def _routing_contract(
        decision: Any,
        coverage: Any,
        quality: Optional[dict],
        sector: str,
        mode: str,
    ) -> Any:
        """Adapt typed RoutingDecision to the mapper's API-facing shape."""
        if decision is None or hasattr(decision, "selected_model"):
            return decision

        coverage_dict = FrameworkAdapter._coverage_contract(coverage) or {}
        selected_pipeline = str(getattr(decision, "selected_pipeline", "") or "")
        mode_key = mode.lower()
        if mode_key == "sector":
            selected_model = "FULL_SECTOR_MODEL"
        elif mode_key == "universal":
            selected_model = "UNIVERSAL_MODEL"
        else:
            selected_model = (
                "FULL_SECTOR_MODEL"
                if selected_pipeline == f"{sector.capitalize()}Pipeline"
                else "UNIVERSAL_MODEL"
            )
        quality_passed = bool((quality or {}).get("overall_passed", True))

        return SimpleNamespace(
            selected_model=SimpleNamespace(value=selected_model),
            selected_pipeline=selected_pipeline,
            prediction_mode=mode,
            routing_reason=str(getattr(decision, "reasoning", "") or ""),
            coverage_score=coverage_dict.get("coverage_score", 0.0),
            coverage_band=coverage_dict.get("coverage_band", "Unknown"),
            quality_score=1.0 if quality_passed else 0.0,
            quality_status="Passed" if quality_passed else "Failed",
            concept_confidence=(coverage_dict.get("concept_confidence") or {}).get(
                "overall_confidence"
            ),
            reliability=(
                "High"
                if float(getattr(decision, "confidence", 0.0) or 0.0) >= 0.75
                else "Medium"
            ),
            model_artifact=selected_pipeline,
            warnings=[],
        )

    def _execution_result(
        self,
        *,
        sector: str,
        mode: str,
        input_path: str,
        results: pd.DataFrame,
        fallback_coverage: Any = None,
        fallback_quality: Optional[dict] = None,
        fallback_routing: Any = None,
        diagnostics: Optional[dict] = None,
    ) -> ExecutionResult:
        coverage = results.attrs.get("coverage", fallback_coverage)
        quality = results.attrs.get("quality", fallback_quality)
        routing = results.attrs.get("routing_decision", fallback_routing)
        intelligence = results.attrs.get("intelligence")
        if intelligence is not None:
            diagnostics = dict(diagnostics or {})
            diagnostics.setdefault("stage_timings", getattr(intelligence, "stage_timings", {}))
            diagnostics.setdefault(
                "intelligence",
                {
                    "business_meanings": to_serializable(getattr(intelligence, "business_meanings", [])),
                    "context": to_serializable(getattr(intelligence, "context", None)),
                    "semantic_graph": to_serializable(getattr(intelligence, "semantic_graph", None)),
                    "canonical_mapping": to_serializable(getattr(intelligence, "canonical_mapping", None)),
                    "coverage": to_serializable(getattr(intelligence, "coverage", None)),
                    "routing": to_serializable(getattr(intelligence, "routing", None)),
                },
            )

        return ExecutionResult.from_framework_output(
            sector=sector,
            mode=mode,
            input_path=input_path,
            results=results,
            coverage=self._coverage_contract(coverage),
            quality=quality,
            routing_decision=self._routing_contract(routing, coverage, quality, sector, mode),
            explanation_report=results.attrs.get("prediction_explanation"),
            decision_assessment=results.attrs.get("decision_assessment"),
            diagnostics=diagnostics,
        )

    def _run_sector(
        self,
        input_path: str,
        sector: Optional[str],
        explain: bool,
    ) -> ExecutionResult:
        probe_df = pd.read_csv(input_path)
        resolved_sector = sector or detect_sector(probe_df)

        try:
            results = SectorPipeline(resolved_sector).load().predict(
                input_path,
                explain=explain,
                _prediction_mode="Sector",
            )
        except ValueError as exc:
            return ExecutionResult.from_framework_output(
                sector=resolved_sector,
                mode="sector",
                refused=True,
                refusal_reason=str(exc),
                input_path=input_path,
            )

        results = self._enrich(results, probe_df, resolved_sector)
        return self._execution_result(
            sector=resolved_sector,
            mode="sector",
            input_path=input_path,
            results=results,
        )

    def _run_universal(
        self,
        input_path: str,
        sector: Optional[str],
        explain: bool,
    ) -> ExecutionResult:
        probe_df = pd.read_csv(input_path)
        sector_for_report = sector or detect_sector(probe_df)

        try:
            results = predict_universal(
                input_path,
                force_sector=sector,
                explain=explain,
                _prediction_mode="Universal",
            )
        except ValueError as exc:
            return ExecutionResult.from_framework_output(
                sector=sector_for_report,
                mode="universal",
                refused=True,
                refusal_reason=str(exc),
                input_path=input_path,
            )

        results = self._enrich(results, probe_df, sector_for_report)
        return self._execution_result(
            sector=sector_for_report,
            mode="universal",
            input_path=input_path,
            results=results,
        )

    def _run_auto(
        self,
        input_path: str,
        sector: Optional[str],
        explain: bool,
    ) -> ExecutionResult:
        """Mirror the current CLI auto flow using the typed intelligence pipeline."""
        probe_df = pd.read_csv(input_path)
        resolved_sector = sector or detect_sector(probe_df)

        intelligence = infer_intelligence(probe_df)
        coverage = intelligence.coverage
        quality = run_quality_gate(
            probe_df,
            target_col=SECTOR_CONFIG[resolved_sector]["target_col"],
        )
        decision = intelligence.routing.decision

        if decision.selected_pipeline == f"{resolved_sector.capitalize()}Pipeline":
            results = SectorPipeline(resolved_sector).load()._run_sector_model(
                probe_df,
                coverage,
                quality,
                decision,
                explain,
                None,
                "Auto",
                _intelligence=intelligence,
            )
        else:
            results = predict_universal(
                input_path,
                force_sector=resolved_sector,
                explain=explain,
                _prediction_mode="Auto",
                _intelligence=intelligence,
            )

        results.attrs["coverage"] = coverage
        results.attrs["quality"] = quality
        results.attrs["routing_decision"] = decision
        results.attrs["intelligence"] = intelligence
        results = self._enrich(results, probe_df, resolved_sector)

        return self._execution_result(
            sector=resolved_sector,
            mode="auto",
            input_path=input_path,
            results=results,
            fallback_coverage=coverage,
            fallback_quality=quality,
            fallback_routing=decision,
            diagnostics={"stage_timings": intelligence.stage_timings},
        )

    def execute(
        self,
        input_path: str,
        sector: Optional[str] = None,
        mode: str = "auto",
        explain: bool = False,
    ) -> ExecutionResult:
        """Run one prediction through UCIF and return the backend execution model."""
        if not Path(input_path).exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        if mode == "sector":
            return self._run_sector(input_path, sector, explain)
        if mode == "universal":
            return self._run_universal(input_path, sector, explain)
        if mode == "auto":
            return self._run_auto(input_path, sector, explain)

        raise ValueError(
            f"Unsupported mode '{mode}' - expected one of: 'sector', 'universal', 'auto'."
        )
