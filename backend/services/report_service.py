"""
backend.services.report_service
══════════════════════════════════════════════════════════════════════
``ReportService`` — renders the human-readable report text a
``backend.contracts.ReportsBundle`` carries, using ONLY the
framework's own existing printers/generators.

No new report logic lives here. Two shapes of framework functions
exist and this service adapts to both, without duplicating either:

    generate_*() -> str
        Already returns text directly — called and used as-is.
        (``reporting.generate_prediction_quality_report``,
        ``business_reasoning_report.generate_business_reasoning_report``,
        ``decision_report.generate_decision_report``)

    print_*() -> None
        Writes straight to stdout with no text-returning counterpart
        (``quality_gate.print_quality_report``,
        ``routing.print_routing_decision`` /
        ``reporting.print_routing_decision``). For these, this service
        captures stdout via ``contextlib.redirect_stdout`` rather than
        reimplementing the formatting — the exact bytes a human running
        the CLI would see are what a consumer of this bundle gets too.

Every method degrades to ``None`` (that field simply absent from the
bundle) when its required input is unavailable — e.g. no
``business_reasoning_report_text`` when no ``ReasoningReport`` was
produced for this run — never fabricates report text for data that
was never computed.
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


class ReportService:
    """Stateless — every method is a pure read of already-computed
    framework objects, formatted via the framework's own printers."""

    @staticmethod
    def _captured(fn, *args, **kwargs) -> Optional[str]:
        buffer = io.StringIO()
        try:
            with redirect_stdout(buffer):
                fn(*args, **kwargs)
        except Exception:
            return None
        text = buffer.getvalue().strip()
        return text or None

    def quality_report_text(self, quality: Optional[dict]) -> Optional[str]:
        if quality is None:
            return None
        return self._captured(print_quality_report, quality)

    def routing_report_text(self, routing_decision: Any) -> Optional[str]:
        if routing_decision is None:
            return None
        return self._captured(_routing_print_routing_decision, routing_decision)

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

    # ── one-shot helper, matching FrameworkExecutionResult's shape ──

    def generate_reports(self, result) -> dict:
        """
        Build the full ``report_texts`` dict ``FrameworkMapper.
        map_reports()`` / ``ReportsBundle.from_dict()`` expects, from
        one ``backend.adapters.FrameworkExecutionResult``. Any section
        whose inputs are unavailable is simply omitted (``ReportsBundle``
        treats a missing key the same as an explicit ``None``).
        """
        texts = {
            "quality_report_text": self.quality_report_text(result.quality),
            "routing_report_text": self.routing_report_text(result.routing_decision),
            "prediction_quality_report_text": self.prediction_quality_report_text(
                result.results, result.coverage, result.sector, result.routing_decision,
            ),
            "business_reasoning_report_text": self.business_reasoning_report_text(
                result.explanation_report,
            ),
            "decision_report_text": self.decision_report_text(result.decision_assessment),
        }
        return {k: v for k, v in texts.items() if v is not None}