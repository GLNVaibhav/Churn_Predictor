"""
universal_churn/prediction_intelligence/reports/prediction_intelligence_report.py
══════════════════════════════════════════════════════════════════════
Formatting-only module for PredictionIntelligenceReport. Same visual
style as coverage.py / quality_gate.py / routing.py /
concept_confidence.py / business_reasoning_report.py's existing report
printers. Computes nothing new — every value here already exists on
the PredictionIntelligenceReport object it's given.
"""
from __future__ import annotations

from ..models import PredictionIntelligenceReport


def generate_prediction_intelligence_report(report: PredictionIntelligenceReport) -> str:
    sep = '─' * 60
    lines = [sep, "  PREDICTION INTELLIGENCE REPORT", sep]
    lines.append(f"  Generated                : {report.generated_at}")
    lines.append(f"  Sector                   : {report.sector.capitalize()}")
    if report.customer_id is not None:
        lines.append(f"  Customer ID              : {report.customer_id}")
    lines.append(f"  Prediction               : {report.predicted_churn}")
    lines.append(f"  Churn Probability        : {report.churn_probability*100:.1f}%")

    pc = report.prediction_confidence
    if pc is not None:
        lines.append("")
        lines.append("  Prediction Confidence")
        lines.append(f"    Score                  : {pc.score:.1f}/100")
        lines.append(f"    Band                   : {pc.band}")
        lines.append("    Component Breakdown")
        for name, value in pc.components.items():
            contribution = pc.weighted_contributions.get(name, 0.0)
            lines.append(f"      {name:<24} raw={value:6.1f}  weighted={contribution:6.1f}")
        lines.append("    Reasons")
        for reason in pc.reasons:
            lines.append(f"      - {reason}")

    pa = report.prediction_assurance
    if pa is not None:
        lines.append("")
        lines.append("  Prediction Assurance")
        lines.append(f"    Assurance Score        : {pa.assurance_score:.1f}/100")
        lines.append(f"    Assurance Band         : {pa.assurance_band}")
        lines.append("    Positive Factors")
        if pa.positive_factors:
            for factor in pa.positive_factors:
                lines.append(f"      + {factor}")
        else:
            lines.append("      None")
        lines.append("    Penalties")
        if pa.penalties:
            for penalty in pa.penalties:
                lines.append(f"      - {penalty}")
        else:
            lines.append("      None")
        lines.append("    Summary")
        lines.append(f"      {pa.summary}")
        if pa.warnings:
            lines.append("    Warnings")
            for w in pa.warnings:
                lines.append(f"      ⚠ {w}")
        if pa.metadata:
            lines.append("    Metadata")
            for key, value in pa.metadata.items():
                lines.append(f"      {key:<24}: {value}")

    for label, value in (
        ("Evidence Strength", report.evidence_strength),
        ("Signal Intelligence", report.signal_intelligence),
        ("Prediction Stability", report.stability),
        ("Consistency", report.consistency),
        ("Prediction Intelligence Score", report.intelligence_score),
    ):
        lines.append("")
        lines.append(f"  {label}")
        if value is None:
            lines.append("    Not yet available — engine not implemented in this build.")
        else:
            lines.append(f"    {value}")

    if report.degraded_inputs:
        lines.append("")
        lines.append("  Degraded Inputs (evidence reduced, not treated as failure)")
        for code in report.degraded_inputs:
            lines.append(f"    - {code}")

    lines.append("")
    lines.append(sep)
    return "\n".join(lines)


def print_prediction_intelligence_report(report: PredictionIntelligenceReport) -> None:
    print(generate_prediction_intelligence_report(report))


def to_mermaid() -> str:
    """
    Static architecture diagram for the Prediction Intelligence layer
    and its place in the wider pipeline. Purely descriptive — has no
    effect on, and reads no state from, the live pipeline. Mirrors
    decision_intelligence.to_mermaid()'s shape.

    PC (Prediction Confidence Engine) is the orchestrator's default
    engine, kept for backward compatibility. PA (Prediction Assurance
    Engine) is the differently-named, differently-scoped successor
    concept — fully implemented, available today, and opt-in via
    `PredictionIntelligenceOrchestrator(engines=[PredictionAssuranceEngine()])`.
    Evidence / Robustness / Score are future engines that will plug in
    downstream of PA without changing the orchestrator's public API.
    """
    return (
        "graph TD\n"
        "    Prediction[Prediction] --> PIE[Prediction Intelligence Orchestrator]\n"
        "    PIE --> PC[Prediction Confidence Engine - default]\n"
        "    PIE --> PA[Prediction Assurance Engine]\n"
        "    PA --> EV[Future: Evidence Engine]\n"
        "    EV --> ROB[Future: Robustness Engine]\n"
        "    ROB --> SCORE[Future: Prediction Intelligence Score Engine]\n"
        "    PC --> Report[Prediction Intelligence Report]\n"
        "    SCORE --> Report\n"
        "    Report --> Explanation[Prediction Explanation]\n"
        "    Explanation --> DI[Decision Intelligence]\n"
        "    Coverage[Coverage Result] --> PIE\n"
        "    ConceptConf[Concept Confidence Report] --> PIE\n"
        "    Routing[Routing Decision] --> PIE\n"
        "    Quality[Quality Result] --> PIE\n"
        "    Reasoning[Reasoning Report - optional] -.-> PIE\n"
        "    PredExpl[Prediction Explanation - optional] -.-> PIE\n"
    )