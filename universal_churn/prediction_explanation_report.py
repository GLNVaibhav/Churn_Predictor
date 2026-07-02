"""
universal_churn/prediction_explanation_report.py
══════════════════════════════════════════════════════════════════════
Formatting + CSV enrichment + CLI wiring for the Prediction Explanation
Layer — Version 7, Chunk 5.

This module is the ONLY place that:
    - turns a PredictionExplanationReport into printable text
      (matches the visual style of coverage.py / quality_gate.py /
      routing.py / concept_graph_report.py / business_reasoning_report.py)
    - appends Explanation_* columns to a prediction results DataFrame

New columns are prefixed `Explanation_` specifically so they can never
collide with an existing prediction column (e.g. 'Prediction_Reliability'
already exists, populated by routing.py's report_fields() — this module
adds 'Explanation_Reliability' alongside it, never overwriting it).
Per Part 9's validation requirement, existing columns are never
modified — only appended.
"""
from __future__ import annotations

import pandas as pd

from .prediction_explanation import (
    PredictionExplanationBuilder, PredictionExplanationReport,
)
from .routing import RoutingDecision


# ══════════════════════════════════════════════════════════════════
# PRINTED REPORT (Part 8 — CLI integration)
# ══════════════════════════════════════════════════════════════════

def generate_prediction_explanation_text(report: PredictionExplanationReport) -> str:
    sep = "=" * 56
    d = report.dataset_explanation
    lines = [sep, "PREDICTION EXPLANATION", sep, ""]
    lines.append(f"Sector                   : {report.sector.capitalize()}")
    lines.append("")
    lines.append("Prediction")
    lines.append(f"    {report.dataset_narrative.headline}")
    lines.append("")
    lines.append("Reason")
    lines.append(f"    {report.dataset_narrative.reason_text}")
    lines.append("")

    if report.reasoning_report.findings:
        lines.append("Business Findings")
        for f in report.reasoning_report.findings:
            lines.append(f"    {f.title}")
            lines.append(f"        {f.severity.value}")
            lines.append(f"        Confidence      {f.confidence*100:.0f}%")
        lines.append("")

    lines.append("Recommendation")
    lines.append(f"    {report.dataset_narrative.recommendation_text}")
    lines.append("")

    lines.append("Prediction accepted because")
    lines.append(f"    {report.dataset_narrative.acceptance_text}")
    lines.append("")

    lines.append("Dataset Summary")
    lines.append(f"    Rows analysed            : {d.rows_analyzed}")
    lines.append(f"    Predicted churners       : {d.predicted_churners}")
    lines.append(f"    Average probability      : {d.average_probability*100:.1f}%")
    lines.append(f"    Risk distribution        : {d.risk_distribution}")
    lines.append(f"    Dominant business findings: "
                 f"{list(d.dominant_findings) if d.dominant_findings else 'None'}")
    lines.append(f"    Business strengths       : "
                 f"{list(d.business_strengths) if d.business_strengths else 'None'}")
    lines.append(f"    Business weaknesses      : "
                 f"{list(d.business_weaknesses) if d.business_weaknesses else 'None'}")
    lines.append(f"    Overall business health  : {d.overall_business_health}")
    lines.append(f"    Overall customer risk    : {d.overall_customer_risk}")
    lines.append("")

    lines.append(sep)
    return "\n".join(lines)


def print_prediction_explanation_report(report: PredictionExplanationReport) -> None:
    print("\n" + generate_prediction_explanation_text(report))


# ══════════════════════════════════════════════════════════════════
# EXECUTION SUMMARY — one screen, cross-referencing the reports that
# already printed (coverage.py / concept_confidence.py / quality_gate.py
# / routing.py), rather than repeating their content. This is the
# "--report" diagnostics summary requested for the Version 7 polish
# pass: it reads values those modules already computed and attached to
# `results.attrs` / the explanation report — it computes nothing new.
# ══════════════════════════════════════════════════════════════════

def generate_execution_summary(
    report: PredictionExplanationReport,
    coverage: dict | None,
) -> str:
    """
    One concise block answering "what did the pipeline actually do for
    this run" — resolved fields, semantic recoveries, reconstructed
    concepts, triggered findings, routing outcome, reliability, and
    business health. Every value here is read from `coverage` (already
    produced by coverage.py) and `report` (already produced by the
    Prediction Explanation Layer) — see those modules' own printers
    for the full detail behind each line.
    """
    sep = "─" * 60
    lines = [sep, "  EXECUTION SUMMARY", sep]

    if coverage is not None:
        resolved = [d['feature'] for d in coverage.get('detail', []) if d.get('quality') == 1]
        semantic = coverage.get('semantic_matches', [])
        lines.append(f"  Resolved fields              : {len(resolved)}")
        lines.append(
            f"  Semantically recovered fields : "
            f"{', '.join(semantic) if semantic else 'None'}"
        )
        concept_conf = coverage.get('concept_confidence') or {}
        lines.append(
            f"  Concepts reconstructed        : "
            f"{concept_conf.get('reconstructable_concepts', 0)}/"
            f"{concept_conf.get('total_concepts', 0)}"
        )
    else:
        lines.append("  Coverage data unavailable for this run.")

    findings = report.reasoning_report.findings
    lines.append(
        f"  Triggered findings            : "
        f"{', '.join(f.title for f in findings) if findings else 'None'}"
    )

    evidence = report.row_explanations[0].evidence if report.row_explanations else None
    if evidence is not None:
        lines.append(f"  Routing outcome                : {evidence.routing_selected_model}")
        lines.append(
            f"  Prediction reliability         : "
            f"{report.row_explanations[0].reliability.level}"
        )

    summary = report.dataset_explanation
    lines.append(f"  Business health                : {summary.overall_business_health}")
    lines.append(f"  Customer risk                  : {summary.overall_customer_risk}")

    lines.append(sep)
    return "\n".join(lines)


def print_execution_summary(
    report: PredictionExplanationReport,
    coverage: dict | None,
) -> None:
    print("\n" + generate_execution_summary(report, coverage))


# ══════════════════════════════════════════════════════════════════
# CSV ENRICHMENT (Part 7)
# ══════════════════════════════════════════════════════════════════

def attach_explanation_columns(
    results: pd.DataFrame,
    report: PredictionExplanationReport,
) -> pd.DataFrame:
    """
    Append Explanation_* columns to `results`, aligned by row position
    with `report.row_explanations`. Returns a NEW DataFrame (does not
    mutate `results` in place) — no existing column is read, dropped,
    or overwritten.
    """
    if len(report.row_explanations) != len(results):
        raise ValueError(
            f"Row explanation count ({len(report.row_explanations)}) does not "
            f"match results row count ({len(results)}) — refusing to attach "
            f"misaligned explanation columns."
        )

    enriched = results.copy()
    enriched['Explanation_Prediction']        = [e.narrative.headline for e in report.row_explanations]
    enriched['Explanation_Probability']       = [e.summary.probability for e in report.row_explanations]
    enriched['Explanation_Triggered_Findings'] = [
        "; ".join(e.evidence.business_finding_ids) if e.evidence.business_finding_ids else ""
        for e in report.row_explanations
    ]
    enriched['Explanation_Dominant_Concepts'] = [
        "; ".join(
            name.replace("Business Finding: ", "")
            for name in (i.name for i in e.evidence.items if i.source == 'ReasoningReport')
        )
        for e in report.row_explanations
    ]
    enriched['Explanation_Business_Reason']   = [e.narrative.reason_text for e in report.row_explanations]
    enriched['Explanation_Recommendation']    = [
        e.recommendation.recommendation_text for e in report.row_explanations
    ]
    enriched['Explanation_Reliability']       = [e.reliability.level for e in report.row_explanations]
    enriched['Explanation_Reliability_Reasons'] = [
        "; ".join(e.reliability.reasons) for e in report.row_explanations
    ]
    enriched['Explanation_Missing_Features']  = [
        "; ".join(e.reliability.missing_features) for e in report.row_explanations
    ]
    return enriched


# ══════════════════════════════════════════════════════════════════
# ONE-SHOT CLI HELPER — the only function cli.py needs to call
# ══════════════════════════════════════════════════════════════════

def build_and_attach_explanations(
    results: pd.DataFrame,
    df_raw: pd.DataFrame,
    sector: str,
) -> pd.DataFrame:
    """
    Best-effort, exception-safe enrichment: build a
    PredictionExplanationReport from results.attrs (coverage / quality /
    routing_decision, all already populated by the prediction pipeline
    that produced `results`) and attach Explanation_* columns.

    On ANY failure, logs a warning and returns `results` UNCHANGED —
    the explanation layer must never be able to break prediction
    output. The built report (if successful) is stashed on
    `enriched.attrs['prediction_explanation']` so cli.py's --report
    branch can print it without rebuilding it.
    """
    try:
        coverage = results.attrs.get('coverage')
        quality = results.attrs.get('quality')
        routing_decision: RoutingDecision | None = results.attrs.get('routing_decision')

        builder = PredictionExplanationBuilder()
        report = builder.build(
            df_raw=df_raw, sector=sector, results=results,
            coverage=coverage, quality=quality, routing_decision=routing_decision,
        )
        enriched = attach_explanation_columns(results, report)
        enriched.attrs.update(results.attrs)
        enriched.attrs['prediction_explanation'] = report
        return enriched
    except Exception as exc:
        print(f"  WARNING: prediction explanation layer failed ({exc}); "
              f"prediction output is unaffected — explanation columns omitted.")
        return results