"""
backend.services.report_service
══════════════════════════════════════════════════════════════════════
``ReportService`` — renders human-readable report text using ONLY the
framework's own existing printers/generators.

No new report logic lives here.  Two shapes of framework functions
exist and this service adapts to both:

    generate_*() -> str
        Already returns text directly — called and used as-is.

    print_*() -> None
        Writes to stdout with no text-returning counterpart.
        Captured via ``redirect_stdout`` behind ``_StdoutCaptureBackend``.
        TODO: Remove when framework exposes structured report API.

Every method degrades to ``None`` when its required input is unavailable.
"""
from __future__ import annotations

import io
from contextlib import redirect_stdout
from typing import Any, Optional

from universal_churn.quality_gate import print_quality_report
from universal_churn.routing import print_routing_decision as _routing_print_routing_decision
from universal_churn.reporting import generate_prediction_quality_report
from universal_churn.business_reasoning_report import generate_business_reasoning_report
from universal_churn.decision_report import generate_decision_report

from ..models.execution_result import ExecutionResult


class _StdoutCaptureBackend:
    """
    Isolated stdout capture for framework print_* functions.

    TODO: Remove when framework exposes structured report API.
    """

    @staticmethod
    def capture(fn, *args, **kwargs) -> Optional[str]:
        buffer = io.StringIO()
        try:
            with redirect_stdout(buffer):
                fn(*args, **kwargs)
        except Exception:
            return None
        text = buffer.getvalue().strip()
        return text or None


class ReportService:
    """Stateless — formats already-computed framework objects via UC printers."""

    def quality_report_text(self, quality: Optional[dict]) -> Optional[str]:
        if quality is None:
            return None
        return _StdoutCaptureBackend.capture(print_quality_report, quality)

    def routing_report_text(self, routing_decision: Any) -> Optional[str]:
        if routing_decision is None:
            return None
        return _StdoutCaptureBackend.capture(_routing_print_routing_decision, routing_decision)

    def prediction_quality_report_text(
        self,
        results,
        coverage: Optional[dict],
        sector: str,
        routing_decision: Any = None,
    ) -> Optional[str]:
        if results is None or len(results) == 0:
            return None
        try:
            return generate_prediction_quality_report(
                results, coverage, sector, routing_decision=routing_decision,
            )
        except Exception:
            return None

    def business_reasoning_report_text(self, explanation_report: Any) -> Optional[str]:
        reasoning_report = getattr(explanation_report, "reasoning_report", None)
        if reasoning_report is None:
            return None
        try:
            return generate_business_reasoning_report(reasoning_report)
        except Exception:
            return None

    def decision_report_text(self, decision_assessment: Any) -> Optional[str]:
        if decision_assessment is None:
            return None
        try:
            return generate_decision_report(decision_assessment)
        except Exception:
            return None

    def generate_reports(self, execution_result: ExecutionResult) -> dict:
        """
        Build the ``report_texts`` dict from one ``ExecutionResult``.
        Sections whose inputs are unavailable are omitted.
        """
        texts = {
            "quality_report_text": self.quality_report_text(execution_result.quality),
            "routing_report_text": self.routing_report_text(execution_result.routing),
            "prediction_quality_report_text": self.prediction_quality_report_text(
                execution_result.results_df,
                execution_result.coverage,
                execution_result.sector,
                execution_result.routing,
            ),
            "business_reasoning_report_text": self.business_reasoning_report_text(
                execution_result.reasoning,
            ),
            "decision_report_text": self.decision_report_text(execution_result.decision),
        }
        return {k: v for k, v in texts.items() if v is not None}
