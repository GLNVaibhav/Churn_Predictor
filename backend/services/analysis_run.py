"""
backend.services.analysis_run
══════════════════════════════════════════════════════════════════════
Internal handoff bundle from ``AnalysisService`` to the runtime layer.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..contracts.analysis_response import UniversalAnalysisResponse
from ..models.execution_result import ExecutionResult


@dataclass(frozen=True)
class AnalysisRunBundle:
    """Response contract + immutable framework snapshot for platform enrichment."""
    response: UniversalAnalysisResponse
    execution_result: ExecutionResult
