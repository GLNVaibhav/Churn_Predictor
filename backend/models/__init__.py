"""
backend.models
══════════════════════════════════════════════════════════════════════
Backend-owned domain models that sit between the framework adapter
and the API translation layer.  ``ExecutionResult`` is the canonical
immutable execution model — it is NOT a framework object.
"""
from __future__ import annotations

from .execution_result import ExecutionMetadata, ExecutionResult, PredictionsSection
from .execution_record import ExecutionRecord, ExecutionEvent

__all__ = [
    "ExecutionMetadata", "ExecutionResult", "PredictionsSection",
    "ExecutionRecord", "ExecutionEvent",
]
