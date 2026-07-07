"""
backend.mappers
══════════════════════════════════════════════════════════════════════
Translation layer between existing ``universal_churn`` framework
outputs and ``backend.contracts.UniversalAnalysisResponse``.

``FrameworkMapper`` (framework_mapper.py) is the only class here. It
performs NO business logic, NO calculations, NO validation, NO
routing, and NO reasoning — it only reads fields off objects the
framework already produced and reshapes them into the public contract.
"""
from __future__ import annotations

from .framework_mapper import FrameworkMapper

__all__ = ["FrameworkMapper"]
