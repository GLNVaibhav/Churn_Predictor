"""Immutable contracts for the Adaptive Business Intelligence Layer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BusinessEvidence:
    evidence_id: str
    category: str
    description: str
    source: str
    severity: str
    confidence: float
    affected_segments: tuple[str, ...] = ()
    recommendation: str = "Review this business signal alongside the customer prediction."
    timestamp: str = ""


@dataclass(frozen=True)
class BusinessEvidenceBundle:
    evidences: tuple[BusinessEvidence, ...] = ()
    overall_business_impact: str = "NONE"
    confidence: float = 0.0
    summary: str = "No external business context supplied. Prediction generated using internal customer evidence only."
    assessment: "BusinessImpactAssessment | None" = None


@dataclass(frozen=True)
class BusinessImpactAssessment:
    signals_evaluated: int
    dominant_driver: str
    affected_segments: tuple[str, ...]
    operational_impact: str
    priority: str
    recommended_action: str
    supporting_evidence: tuple[str, ...]


@dataclass(frozen=True)
class ExecutionContext:
    sector: str
    execution_id: str
    events: tuple[dict[str, Any], ...] = ()
