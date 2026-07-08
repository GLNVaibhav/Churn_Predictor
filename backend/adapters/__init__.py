"""
backend.adapters
══════════════════════════════════════════════════════════════════════
Anti-Corruption Layer between ``backend.services`` and
``universal_churn``.  ``FrameworkAdapter`` executes the framework once
and returns ``ExecutionResult`` — the backend's canonical execution model.
"""
from __future__ import annotations

from .framework_adapter import FrameworkAdapter

__all__ = ["FrameworkAdapter"]
