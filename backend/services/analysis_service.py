"""
backend.services.analysis_service
══════════════════════════════════════════════════════════════════════
``AnalysisService`` — orchestrator only (Sprint 3).

Responsibilities:
    - validate request (via ``initialize()`` lifecycle)
    - call ``FrameworkAdapter`` (framework executes exactly once)
    - measure execution time / create ``ExecutionInfo``
    - apply Type-B presentation aggregation (KPI roll-ups)
    - call ``FrameworkMapper`` (pure translation → API DTO)
    - return ``UniversalAnalysisResponse``

Forbidden:
    - prediction / routing / coverage / quality / report generation logic
"""
from __future__ import annotations

import time
from typing import Optional

from ..adapters import FrameworkAdapter
from ..contracts import (
    ExecutionInfo, DatasetInfo, UniversalAnalysisResponse,
)
from ..exceptions import FrameworkExecutionError, ServiceInitializationError
from ..mappers import FrameworkMapper
from ..models.execution_result import ExecutionResult
from ..presentation import build_prediction_summary
from .report_service import ReportService


class AnalysisService:
    """
    Orchestrator — wires adapter, presentation, mapper, and reports.

    Usage::

        service = AnalysisService()
        service.initialize()
        response = service.execute(input_path="tests/golden_telecom.csv", mode="auto")
        service.shutdown()
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

    def initialize(self) -> "AnalysisService":
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
        self._initialized = False

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise ServiceInitializationError(
                "AnalysisService.execute() called before initialize(). "
                "Call service.initialize() once before running analyses."
            )

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
        """
        self._require_initialized()

        execution = ExecutionInfo.start(framework_version=self._framework_version)
        start = time.perf_counter()

        try:
            execution_result: ExecutionResult = self._adapter.execute(
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

        if include_reports:
            report_texts = self._report_service.generate_reports(execution_result)
            execution_result = execution_result.with_reports(report_texts)

        dataset = DatasetInfo(
            filename=input_path,
            sector=execution_result.sector,
            prediction_mode=mode,
            rows=len(execution_result.results_df) if execution_result.results_df is not None else None,
        )

        extra_warnings = (
            [execution_result.refusal_reason]
            if execution_result.refused and execution_result.refusal_reason
            else None
        )

        # Type-B presentation aggregation (KPI roll-ups for dashboard cards)
        prediction_summary = build_prediction_summary(execution_result.results_df)

        return self._mapper.build_response(
            execution=execution,
            execution_result=execution_result,
            dataset=dataset,
            prediction_summary=prediction_summary,
            extra_warnings=extra_warnings,
        )
