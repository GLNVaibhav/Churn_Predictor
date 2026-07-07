"""
backend.adapters
══════════════════════════════════════════════════════════════════════
Orchestration layer between ``backend.services`` and
``universal_churn``. ``FrameworkAdapter`` (framework_adapter.py) is the
only class here — it performs NO business logic, NO calculations, NO
validation, NO routing, and NO reasoning of its own. It calls the
framework's existing functions in the same sequence ``cli.py`` already
uses per mode, and returns a plain ``FrameworkExecutionResult`` bundle
of whatever those calls produced.
"""
from __future__ import annotations

from .framework_adapter import FrameworkAdapter, FrameworkExecutionResult

__all__ = ["FrameworkAdapter", "FrameworkExecutionResult"]