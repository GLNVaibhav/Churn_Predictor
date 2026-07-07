"""
backend.services
══════════════════════════════════════════════════════════════════════
Sprint 2 — Service Layer.

    AnalysisService   — run one full analysis (FrameworkAdapter ->
                         FrameworkMapper -> UniversalAnalysisResponse).
    PipelineService    — read-only model/pipeline registry status.
    ReportService       — render human-readable report text from
                         already-computed framework objects.

Every service follows the same explicit ``initialize()`` /
``shutdown()`` lifecycle and raises
``backend.exceptions.ServiceInitializationError`` if used beforehand.
None of these services compute anything ``universal_churn`` didn't
already compute — see ``backend/adapters`` and ``backend/mappers`` for
the layers that actually touch the framework.
"""
from __future__ import annotations

from .analysis_service import AnalysisService
from .pipeline_service import PipelineService
from .report_service import ReportService

__all__ = ["AnalysisService", "PipelineService", "ReportService"]