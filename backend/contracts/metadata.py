"""
backend.contracts.metadata
══════════════════════════════════════════════════════════════════════
``FrameworkMetadata`` — version stamps for every framework subsystem
that contributed to one analysis run.

Every field here is a straight passthrough of a version constant the
framework already defines (``config.py``'s ``PIPELINE_VERSION`` /
``COVERAGE_ALGORITHM_VERSION``, ``routing.py``'s reads of the same,
``knowledge_base.py``'s ``KnowledgeBase.version``,
``prediction_intelligence``'s ``PREDICTION_INTELLIGENCE_VERSION``,
etc.) — this module invents no version numbers of its own.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..utils import to_serializable


@dataclass
class FrameworkMetadata:
    """
    Attributes
    ----------
    framework_version : str | None
        Overall pipeline version (``config.PIPELINE_VERSION``).
    knowledge_base_version : str | None
        ``knowledge_base.KnowledgeBase.version``.
    coverage_version : str | None
        ``config.COVERAGE_ALGORITHM_VERSION``.
    routing_version : str | None
        Routing policy version, if/when routing.py exposes one
        (currently piggy-backs on ``framework_version`` since
        routing.py has no independent version constant yet).
    prediction_version : str | None
        Sector/Universal model version relevant to this run
        (``config.SECTOR_MODEL_VERSION`` or
        ``config.UNIVERSAL_MODEL_VERSION``, whichever applies).
    decision_version : str | None
        Decision Intelligence layer version, if exposed.
    prediction_intelligence_version : str | None
        ``prediction_intelligence.PREDICTION_INTELLIGENCE_VERSION``.
    """
    framework_version: Optional[str] = None
    knowledge_base_version: Optional[str] = None
    coverage_version: Optional[str] = None
    routing_version: Optional[str] = None
    prediction_version: Optional[str] = None
    decision_version: Optional[str] = None
    prediction_intelligence_version: Optional[str] = None

    def to_dict(self) -> dict:
        return to_serializable(self)

    @classmethod
    def from_dict(cls, d: dict) -> "FrameworkMetadata":
        return cls(
            framework_version=d.get("framework_version"),
            knowledge_base_version=d.get("knowledge_base_version"),
            coverage_version=d.get("coverage_version"),
            routing_version=d.get("routing_version"),
            prediction_version=d.get("prediction_version"),
            decision_version=d.get("decision_version"),
            prediction_intelligence_version=d.get("prediction_intelligence_version"),
        )
