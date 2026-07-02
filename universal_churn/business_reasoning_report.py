"""
universal_churn/business_reasoning_report.py
══════════════════════════════════════════════════════════════════════
Business Reasoning Report — Version 7, Chunk 3, Part 4.

Human-readable formatting over a ReasoningReport (the output of
business_reasoning.BusinessReasoningEngine.analyze()), in the same
visual style as coverage.py / quality_gate.py / concept_confidence.py /
concept_graph_report.py's existing reports.

This module does NOT compute anything new — it only formats
ReasoningReport / BusinessFinding / ReasoningSummary data that already
exists. Exactly like concept_graph_report.py's relationship to
business_concept_graph.py.
"""
from __future__ import annotations

import pandas as pd

from .business_reasoning import BusinessReasoningEngine, ReasoningReport


def generate_business_reasoning_report(report: ReasoningReport) -> str:
    """
    Build the "Business Reasoning Report" text, e.g.:

        Business Findings

        1. Retention Risk
           HIGH
           Confidence   88%
           Reason       Recurring Commitment weak
                        Support Friction high
           Recommendation
                        Retention campaign
    """
    sep = '─' * 60
    lines = [sep, f"  BUSINESS REASONING REPORT  [{report.sector.upper()}]", sep]
    lines.append(f"  Generated : {report.generated_at}")

    lines.append("")
    lines.append("  Business Findings")
    if not report.findings:
        lines.append("    None — no rule in the registry fired for this input.")
    for idx, finding in enumerate(report.findings, start=1):
        lines.append("")
        lines.append(f"  {idx}. {finding.title}")
        lines.append(f"     {finding.severity.value}")
        lines.append(f"     Confidence      {finding.confidence*100:.0f}%")
        lines.append(f"     Reason          {finding.explanation}")
        lines.append(f"     Supporting      {', '.join(finding.supporting_concepts)}")
        lines.append(f"     Recommendation  {finding.recommendation}")
        if idx != len(report.findings):
            lines.append("     " + "-" * 30)

    lines.append("")
    lines.append(sep)
    lines.append("  CONCEPT INFERENCES")
    lines.append(sep)
    for concept_id, inf in report.inferences.items():
        evidence_flag = "✔" if inf.has_sufficient_evidence else "✖ (insufficient evidence)"
        lines.append(
            f"    {concept_id:<22} band={inf.band.value:<7} "
            f"value={inf.aggregate_value*100:5.1f}%  "
            f"confidence={inf.confidence*100:5.1f}%  {evidence_flag}"
        )

    if report.summary is not None:
        s = report.summary
        lines.append("")
        lines.append(sep)
        lines.append("  REASONING SUMMARY (diagnostics only)")
        lines.append(sep)
        lines.append(f"  Overall business health : {s.overall_business_health}")
        lines.append(f"  Overall customer risk    : {s.overall_customer_risk}")
        lines.append(
            f"  Business strengths       : "
            f"{', '.join(s.business_strengths) if s.business_strengths else 'None'}"
        )
        lines.append(
            f"  Business weaknesses      : "
            f"{', '.join(s.business_weaknesses) if s.business_weaknesses else 'None'}"
        )
        lines.append(f"  Dominant failure reason  : {s.dominant_failure_reason or 'None'}")
        lines.append(f"  Dominant positive signal : {s.dominant_positive_signal or 'None'}")

    lines.append(sep)
    return "\n".join(lines)


def print_business_reasoning_report(report: ReasoningReport) -> None:
    print(generate_business_reasoning_report(report))


def business_reasoning_report_for(df_input: pd.DataFrame, sector: str) -> str:
    """
    Convenience one-shot: run the reasoning engine for this input file
    and return its formatted report, without the caller needing to
    import business_reasoning directly — mirrors
    concept_graph_report.concept_graph_report_for()'s shape.
    """
    report = BusinessReasoningEngine().analyze(df_input, sector)
    return generate_business_reasoning_report(report)
