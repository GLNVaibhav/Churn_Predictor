"""
backend.services.analysis_service
══════════════════════════════════════════════════════════════════════
``AnalysisService`` — the primary Sprint 2 service: run one full
analysis and return a ``UniversalAnalysisResponse``.

Layering
--------
::

    AnalysisService
        -> FrameworkAdapter   (calls universal_churn, returns raw objects)
        -> FrameworkMapper    (raw objects -> UniversalAnalysisResponse)

This class adds exactly two things neither of those layers has on its
own: execution lifecycle (``ExecutionInfo`` timing/status) and a
single, stable exception type (``FrameworkExecutionError``) for
anything that goes wrong in the framework call itself. It computes
nothing else — every value in the returned response was already
produced by ``universal_churn`` and reshaped, unmodified, by
``FrameworkMapper``.
"""
from __future__ import annotations

import time
from typing import Optional

from ..adapters import FrameworkAdapter, FrameworkExecutionResult
from ..contracts import (
    ExecutionInfo, DatasetInfo, UniversalAnalysisResponse,
)
from ..exceptions import FrameworkExecutionError, ServiceInitializationError
from ..mappers import FrameworkMapper
from .report_service import ReportService


class AnalysisService:
    """
    Usage
    -----
        service = AnalysisService()
        service.initialize()
        response = service.execute(input_path="tests/golden_telecom.csv", mode="auto")
        service.shutdown()

    ``initialize()`` / ``shutdown()`` model an explicit lifecycle so a
    future long-lived host (a FastAPI app's startup/shutdown hooks —
    see docs/BACKEND_INTEGRATION.md's Sprint 2 plan) has a clear place
    to wire this in; today ``initialize()`` only constructs its
    collaborators, but keeping the lifecycle explicit means adding
    real setup (e.g. warming the Knowledge Base singleton, verifying
    model artifacts exist) later never changes this class's public
    shape.
    """

    def __init__(
        self,
        adapter: Optional[FrameworkAdapter] = None,
        mapper: Optional[FrameworkMapper] = None,
        report_service: Optional[ReportService] = None,
        framework_version: Optional[str] = None,
    ) -> None:
        self._adapter = adapter or FrameworkAdapter()
        self._mapper = mapper or FrameworkMapper()
        self._report_service = report_service or ReportService()
        self._framework_version = framework_version
        self._initialized = False

    # ── lifecycle ────────────────────────────────────────────────

    def initialize(self) -> "AnalysisService":
        """
        Construct/validate collaborators. Wrapped in
        ServiceInitializationError so a broken environment (e.g. the
        Knowledge Base failing its own fail-fast validation at import
        time — see knowledge_loader.KnowledgeValidationError) surfaces
        as one stable backend exception type rather than an arbitrary
        framework import error.
        """
        try:
            if self._framework_version is None:
                from universal_churn.config import PIPELINE_VERSION
                self._framework_version = PIPELINE_VERSION
            self._initialized = True
        except Exception as exc:
            raise ServiceInitializationError(
                f"AnalysisService failed to initialize: {exc}"
            ) from exc
        return self

    def shutdown(self) -> None:
        """No held resources to release today (stateless collaborators)
        — exists so callers get a symmetric lifecycle regardless of
        what a later sprint adds here (connection pools, caches, ...)."""
        self._initialized = False

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise ServiceInitializationError(
                "AnalysisService.execute() called before initialize(). "
                "Call service.initialize() once before running analyses."
            )

    # ── execution ────────────────────────────────────────────────

    def execute(
        self,
        input_path: str,
        sector: Optional[str] = None,
        mode: str = "auto",
        explain: bool = False,
        include_reports: bool = False,
    ) -> UniversalAnalysisResponse:
        """
        Run one analysis end-to-end and return the public contract.

        Parameters
        ----------
        input_path : path to the input CSV (mirrors ``cli.py --input``).
        sector : explicit sector override (``cli.py --sector``); if
            omitted, the framework auto-detects it exactly as it does
            for the CLI.
        mode : ``'sector'`` | ``'universal'`` | ``'auto'`` — mirrors
            ``cli.py --mode``.
        explain : whether to run the SHAP explanation log
            (``cli.py --explain``).
        include_reports : whether to render the human-readable report
            texts (``ReportsBundle``) alongside the structured data —
            off by default since rendering text nobody asked for is
            wasted work; set True for a CLI-parity "give me everything"
            call.

        Raises
        ------
        ServiceInitializationError
            if called before ``initialize()``.
        FrameworkExecutionError
            if the framework call itself fails for a reason OTHER than
            a modeled routing refusal (see ``FrameworkAdapter``'s
            docstring for the refusal-vs-error distinction). A modeled
            refusal is NOT an error — it still returns a fully valid
            ``UniversalAnalysisResponse`` with ``coverage``/``quality``/
            ``routing`` populated and ``prediction``/
            ``prediction_explanation``/``decision`` left ``None``,
            exactly per docs/BACKEND_INTEGRATION.md's contract.
        """
        self._require_initialized()

        execution = ExecutionInfo.start(framework_version=self._framework_version)
        start = time.perf_counter()

        try:
            result: FrameworkExecutionResult = self._adapter.execute(
                input_path=input_path, sector=sector, mode=mode, explain=explain,
            )
        except Exception as exc:
            execution = execution.mark_failed(
                execution_time_ms=round((time.perf_counter() - start) * 1000, 2)
            )
            raise FrameworkExecutionError(
                f"Framework execution failed for input '{input_path}' "
                f"(mode='{mode}'): {exc}"
            ) from exc

        execution = execution.mark_succeeded(
            execution_time_ms=round((time.perf_counter() - start) * 1000, 2)
        )

        dataset = DatasetInfo(
            filename=input_path,
            sector=result.sector,
            prediction_mode=mode,
            rows=len(result.results) if result.results is not None else None,
        )

        extra_warnings = [result.refusal_reason] if result.refused and result.refusal_reason else None

        report_texts = (
            self._report_service.generate_reports(result) if include_reports else None
        )

        return self._mapper.build_response(
            execution=execution,
            dataset=dataset,
            coverage=result.coverage,
            quality=result.quality,
            routing_decision=result.routing_decision,
            results=result.results,
            explanation_report=result.explanation_report,
            decision_assessment=result.decision_assessment,
            report_texts=report_texts,
            extra_warnings=extra_warnings,
        )