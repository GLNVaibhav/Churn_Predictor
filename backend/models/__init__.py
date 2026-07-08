"""
backend.models
══════════════════════════════════════════════════════════════════════
Backend-owned domain models that sit between the framework adapter
and the API translation layer.  ``ExecutionResult`` is the canonical
immutable execution model — it is NOT a framework object.
"""
from __future__ import annotations

from .execution_result import ExecutionMetadata, ExecutionResult, PredictionsSection

__all__ = ["ExecutionMetadata", "ExecutionResult", "PredictionsSection"]
