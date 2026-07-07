"""
backend.contracts
══════════════════════════════════════════════════════════════════════
The canonical public response contract for the Backend Integration
Layer. ``UniversalAnalysisResponse`` (analysis_response.py) is the
single object every future consumer (FastAPI, frontend, CLI, AI
agents, SDKs) receives; every other name exported here is one of its
sections.

Nothing in this subpackage imports ``universal_churn`` — contracts are
pure data shapes. Only ``backend.mappers`` knows how to read framework
output into these shapes.
"""
from __future__ import annotations

from .execution import ExecutionInfo
from .dataset import DatasetInfo
from .pipeline import PipelineStageInfo, PipelineSummary
from .metadata import FrameworkMetadata
from .analysis_response import (
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

__all__ = [
    "ExecutionInfo",
    "DatasetInfo",
    "PipelineStageInfo",
    "PipelineSummary",
    "FrameworkMetadata",
    "UniversalAnalysisResponse",
    "CoverageSummary",
    "ConceptConfidenceSummary",
    "QualitySummary",
    "RoutingSummary",
    "PredictionSummary",
    "PredictionExplanationSummary",
    "DecisionSummary",
    "ReportReference",
]
