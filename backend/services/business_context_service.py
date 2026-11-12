"""Adapt validated ABIL context into execution-scoped API evidence."""
from __future__ import annotations

from typing import Any

from universal_churn.adaptive_business import AdaptiveBusinessEngine, ExecutionContext
from backend.utils import to_serializable


def evaluate_business_context(
    document: dict[str, Any], *, sector: str, execution_id: str
) -> dict[str, Any]:
    """Evaluate supplied business events without touching prediction output."""
    bundle = AdaptiveBusinessEngine().evaluate(ExecutionContext(
        sector=sector,
        execution_id=execution_id,
        events=tuple(document.get("events") or []),
    ))
    source_events = tuple(document.get("events") or [])
    signals = [
        {
            "name": item.category,
            "impact": item.severity,
            "value": item.description,
            "confidence": item.confidence,
            "department": item.source,
            "source": item.source,
            "affected_segments": list(item.affected_segments),
            "recommendation_influence": item.recommendation,
            "evidence_id": item.evidence_id,
            "department": source_events[index].get("department") if index < len(source_events) else None,
            "priority": source_events[index].get("priority") if index < len(source_events) else None,
        }
        for index, item in enumerate(bundle.evidences)
    ]
    return {
        "status": "AVAILABLE" if signals else "NO_SIGNALS",
        "sector": sector,
        "signal_count": len(signals),
        "overall_business_impact": bundle.overall_business_impact,
        "evidence_confidence": bundle.confidence,
        "summary": bundle.summary,
        "assessment": to_serializable(bundle.assessment),
        "signals": signals,
    }
