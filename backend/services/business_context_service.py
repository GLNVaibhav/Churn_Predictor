"""Adapt validated ABIL context into execution-scoped API evidence."""
from __future__ import annotations

from typing import Any

from universal_churn.adaptive_business import AdaptiveBusinessEngine, ExecutionContext
from backend.utils import to_serializable


def _context_action(category: str, sector: str) -> str:
    """Return a bounded, sector-aware follow-up from supplied event labels.

    The wording is operational guidance, not a claim that the event caused churn.
    It never uses the source document's recommendation as the generated action.
    """
    label = category.casefold()
    domain = sector.casefold()
    if domain == "telecom":
        if any(term in label for term in ("network", "reliability", "infrastructure", "5g", "fiber")):
            return "Review the reported network or service-reliability evidence for the stated period; validate any supplied affected areas before considering a retention response."
        if any(term in label for term in ("pricing", "competition", "revenue", "loyalty", "campaign")):
            return "Review the supplied offer, pricing, or competitor signal by available customer segment; assess a retention action only after validating the affected cohort."
        if any(term in label for term in ("customer experience", "customer insight", "digital adoption")):
            return "Review the supplied customer-experience or adoption evidence with the named owner and validate the affected cohort before prioritizing outreach."
    elif domain == "banking":
        if any(term in label for term in ("fraud", "credit risk", "cybersecurity", "regulatory", "compliance")):
            return "Route the supplied risk or compliance signal for authorized case review; validate the evidence and do not use churn risk as a substitute for a regulated risk decision."
        if any(term in label for term in ("digital banking", "technology", "branch", "customer experience")):
            return "Review the supplied channel or service evidence for the reported period; validate affected customer cohorts before selecting a service or retention follow-up."
        if any(term in label for term in ("competition", "cross sell", "loyalty", "marketing", "growth")):
            return "Review the supplied market or engagement signal against eligible customer cohorts; validate suitability before proposing a retention or product action."
    elif domain in {"ecommerce", "e-commerce", "retail"}:
        if any(term in label for term in ("logistics", "returns", "inventory", "seller", "delivery")):
            return "Review the supplied fulfillment, return, or inventory evidence for the reported period; validate any affected buyer or seller cohort before taking action."
        if any(term in label for term in ("payment", "fraud", "compliance")):
            return "Route the supplied payment or compliance signal for authorized review; validate transaction evidence before changing customer treatment."
        if any(term in label for term in ("customer experience", "customer support", "loyalty", "digital engagement")):
            return "Review the supplied experience or engagement evidence against available customer segments; validate the issue before prioritizing outreach."
    elif domain == "healthcare":
        if any(term in label for term in ("clinical", "patient safety", "emergency", "diagnostic", "pharmacy")):
            return "Route the supplied clinical or safety signal to the authorized quality or clinical-governance owner; verify it through approved records and keep it separate from churn-risk decisions."
        if any(term in label for term in ("patient experience", "customer feedback", "insurance", "digital health", "appointment")):
            return "Review the supplied access or patient-experience evidence with the named operational owner; validate the affected cohort and avoid inferring a clinical cause of churn."

    return f"Assign the supplied {category} signal to its named owner, validate it against source records, and document a proportionate follow-up; no causal link to churn is inferred."


def _priority(event: dict[str, Any]) -> tuple[int, str]:
    supplied = event.get("priority")
    if isinstance(supplied, int) and not isinstance(supplied, bool):
        return supplied, "supplied"
    severity = str(event.get("severity", "MEDIUM")).upper()
    return {"CRITICAL": 1, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(severity, 3), "derived_from_severity"


def _comparative_report(signals: list[dict[str, Any]], assessment: dict[str, Any] | None) -> dict[str, Any]:
    """Summarize the ABIL assessment across the supplied events without rescoring it."""
    count = len(signals)
    if count == 0:
        return {
            "status": "NO_CONTEXT",
            "context_count": 0,
            "individual_assessments": [],
            "comparative_findings": [],
            "dominant_business_driver": None,
            "decision_justification": None,
            "limitations": ["No ABIL business context was supplied; no comparison was performed."],
        }

    individual = [
        {
            "evidence_id": signal["evidence_id"],
            "business_driver": signal["name"],
            "description": signal["value"],
            "reported_impact": signal["impact"],
            "reported_confidence": signal["confidence"],
            "affected_segments": signal["affected_segments"],
            "department": signal["department"],
            "priority": signal["priority"],
            "priority_source": signal["priority_source"],
            "source": signal["source"],
            "supplied_recommendation": signal["source_recommendation"],
            "recommended_action": signal["action"],
            "rationale": signal["rationale"],
            "limitations": signal["limitations"],
        }
        for signal in signals
    ]
    dominant = assessment.get("dominant_driver") if assessment else None
    findings: list[str] = []
    if count == 1:
        findings.append("One supplied context was assessed; there are no peer contexts to compare.")
    else:
        impact_order = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        highest = max(impact_order.get(str(signal["impact"]).upper(), -1) for signal in signals)
        highest_signals = [signal for signal in signals if impact_order.get(str(signal["impact"]).upper(), -1) == highest]
        findings.append(
            f"Highest reported impact is {highest_signals[0]['impact']} across "
            f"{len(highest_signals)} of {count} supplied contexts."
        )
        if dominant:
            findings.append(
                f"The existing ABIL assessment selected {dominant} as the dominant business driver."
            )

    justification = None
    if assessment:
        justification = (
            f"The existing ABIL assessment selected {dominant} using its established ordering: "
            "reported severity first, then supplied confidence; original event order resolves exact ties. "
            "This is a business-context assessment, not a causal finding or a change to churn predictions."
        )
    return {
        "status": "SINGLE_CONTEXT" if count == 1 else "COMPARISON_AVAILABLE",
        "context_count": count,
        "individual_assessments": individual,
        "comparative_findings": findings,
        "dominant_business_driver": dominant,
        "decision_justification": justification,
        "limitations": [
            "Impact and confidence are supplied context evidence evaluated by existing ABIL rules; they are not calibrated churn probabilities.",
            "No causal effect on churn, recommendation effectiveness, or customer outcome is measured by this comparison.",
            "Comparisons are limited to the contexts supplied with this execution.",
        ],
    }


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
            "department": source_events[index].get("department") if index < len(source_events) else None,
            "source": item.source,
            "affected_segments": list(item.affected_segments),
            "source_recommendation": (
                source_events[index].get("recommended_action")
                or source_events[index].get("recommendation")
            ) if index < len(source_events) else None,
            "action": _context_action(item.category, sector),
            "rationale": (
                f"Rule-based follow-up for the supplied {sector} event '{item.category}' "
                f"with reported {item.severity} severity. This does not establish that the event caused churn."
            ),
            "limitations": "Validate the source event and any affected segment before acting; model churn probabilities are unchanged.",
            "evidence_id": item.evidence_id,
            "priority": _priority(source_events[index])[0] if index < len(source_events) else _priority({"severity": item.severity})[0],
            "priority_source": _priority(source_events[index])[1] if index < len(source_events) else "derived_from_severity",
        }
        for index, item in enumerate(bundle.evidences)
    ]
    assessment = to_serializable(bundle.assessment)
    if isinstance(assessment, dict) and signals:
        dominant_id = next(iter(assessment.get("supporting_evidence", [])), None)
        dominant_signal = next((signal for signal in signals if signal["evidence_id"] == dominant_id), signals[0])
        assessment["recommended_action"] = dominant_signal["action"]
    return {
        "status": "AVAILABLE" if signals else "NO_SIGNALS",
        "sector": sector,
        "signal_count": len(signals),
        "overall_business_impact": bundle.overall_business_impact,
        "evidence_confidence": bundle.confidence,
        "summary": bundle.summary,
        "assessment": assessment,
        "signals": signals,
        "comparative_report": _comparative_report(signals, assessment),
    }
