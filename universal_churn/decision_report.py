"""
universal_churn/decision_report.py
══════════════════════════════════════════════════════════════════════
Executive Decision Report — Version 8, Chunk 1.

Formatting + CSV enrichment for the Decision Intelligence Layer
(decision_intelligence.py). Plays the same role, relative to that
module, that prediction_explanation_report.py plays for
prediction_explanation.py: this is the ONLY place that turns a
DecisionAssessment into printable text, or appends Decision_* columns
to a results DataFrame.

Diagnostics-only: nothing in this module computes a confidence score,
a readiness verdict, or a recommendation — decision_intelligence.py
already did that. This module only formats and attaches values that
already exist.

New DataFrame columns are prefixed `Decision_` specifically so they
can never collide with existing prediction, routing, or explanation
columns (which already use `Prediction_*`, `Coverage_*`, `Quality_*`,
and `Explanation_*` prefixes respectively — see reporting.py,
routing.py, and prediction_explanation_report.py).

Non-interference guarantee
-----------------------------
`attach_decision_columns()` returns a NEW DataFrame and never mutates
its input in place, and never reads, drops, or overwrites an existing
column. `build_and_attach_decision_intelligence()` is exception-safe:
on ANY failure it logs a warning and returns the original `results`
UNCHANGED, so the decision layer can never break prediction output.

This module is NOT imported by cli.py, sector_pipeline.py, or
universal_pipeline.py — Decision Intelligence is opt-in tooling,
called explicitly by whoever wants an executive decision report.
"""
from __future__ import annotations

import pandas as pd

from .decision_intelligence import (
    DecisionAssessment, DecisionIntelligenceEngine, to_mermaid,
)
from .routing import RoutingDecision
from .business_reasoning import ReasoningReport


# ══════════════════════════════════════════════════════════════════
# PRINTED REPORT
# ══════════════════════════════════════════════════════════════════

def generate_decision_report(assessment: DecisionAssessment) -> str:
    """
    Build the human-readable Executive Decision Report text, in the
    same visual style as coverage.py / quality_gate.py / routing.py /
    concept_confidence.py / concept_graph_report.py /
    business_reasoning_report.py's existing report printers.
    """
    sep = '─' * 60
    lines = [
        sep,
        "  EXECUTIVE DECISION REPORT" + (f"  [{assessment.sector.upper()}]" if assessment.sector else ""),
        sep,
    ]
    lines.append(f"  Generated                : {assessment.generated_at}")
    lines.append("")
    lines.append(f"  Decision Readiness       : {assessment.decision_readiness.value}")
    lines.append(f"  Risk Level               : {assessment.risk_level.value}")
    lines.append("")
    lines.append(f"  Overall Confidence       : {assessment.overall_confidence*100:5.1f}%")
    lines.append(f"  Business Confidence      : {assessment.business_confidence*100:5.1f}%")
    lines.append(f"  Technical Confidence     : {assessment.technical_confidence*100:5.1f}%")
    lines.append(f"  Evidence Strength        : {assessment.evidence_strength*100:5.1f}%")
    lines.append("")
    lines.append("  Recommended Action")
    lines.append(f"    {assessment.recommended_action}")

    if assessment.supporting_evidence:
        lines.append("")
        lines.append("  Supporting Evidence")
        for item in assessment.supporting_evidence:
            lines.append(f"    [{item.source}] {item.name}: {item.value}")

    if assessment.warnings:
        lines.append("")
        lines.append("  Warnings")
        for w in assessment.warnings:
            lines.append(f"    ⚠ {w}")

    lines.append(sep)
    return "\n".join(lines)


def print_decision_report(assessment: DecisionAssessment) -> None:
    report = "\n" + generate_decision_report(assessment)
    # The report content is ASCII-safe after replacement on Windows consoles
    # configured with CP1252; assessment data itself remains unchanged.
    try:
        print(report)
    except UnicodeEncodeError:
        print(report.encode("ascii", "replace").decode("ascii"))


# ══════════════════════════════════════════════════════════════════
# CSV ENRICHMENT
# ══════════════════════════════════════════════════════════════════

def attach_decision_columns(
    results: pd.DataFrame,
    assessment: DecisionAssessment,
) -> pd.DataFrame:
    """
    Append dataset-level `Decision_*` columns to `results`.

    The DecisionAssessment this chunk produces is a single, dataset-
    level assessment (not per-row), so every row receives the same
    values — mirroring how `Coverage_Score` / `Quality_Status` /
    `Selected_Model` are already broadcast to every row elsewhere in
    this codebase (see reporting.attach_common_metadata() and
    routing.RoutingDecision.report_fields()).

    Returns a NEW DataFrame; `results` is never mutated in place, and
    no existing column is read, dropped, or overwritten.
    """
    enriched = results.copy()
    enriched['Decision_Readiness']            = assessment.decision_readiness.value
    enriched['Decision_Overall_Confidence']   = f"{assessment.overall_confidence*100:.1f}%"
    enriched['Decision_Business_Confidence']  = f"{assessment.business_confidence*100:.1f}%"
    enriched['Decision_Technical_Confidence'] = f"{assessment.technical_confidence*100:.1f}%"
    enriched['Decision_Evidence_Strength']    = f"{assessment.evidence_strength*100:.1f}%"
    enriched['Decision_Risk_Level']           = assessment.risk_level.value
    enriched['Decision_Recommended_Action']   = assessment.recommended_action
    enriched['Decision_Warnings']             = (
        "; ".join(assessment.warnings) if assessment.warnings else ""
    )
    return enriched


# ══════════════════════════════════════════════════════════════════
# ONE-SHOT HELPER
# ══════════════════════════════════════════════════════════════════
# Mirrors prediction_explanation_report.py's build_and_attach_explanations(),
# but is NOT wired into cli.py by this chunk. Callers that want Decision
# Intelligence in a prediction run invoke this explicitly — exactly how
# the Prediction Explanation Layer worked before it was wired into
# cli.py — keeping Chunk 1 strictly additive/opt-in per "No prediction
# behaviour may change."

def build_and_attach_decision_intelligence(
    results: pd.DataFrame,
    sector: str,
    reasoning_report: ReasoningReport | None = None,
) -> pd.DataFrame:
    """
    Best-effort, exception-safe enrichment: build a DecisionAssessment
    from `results.attrs` (coverage / quality / routing_decision, all
    already populated by the prediction pipeline that produced
    `results` — see sector_pipeline.py / universal_pipeline.py) and
    attach `Decision_*` columns.

    On ANY failure, logs a warning and returns `results` UNCHANGED —
    the decision layer must never be able to break prediction output.
    The built assessment (if successful) is stashed on
    `enriched.attrs['decision_assessment']` so a caller can print the
    full report without rebuilding it.

    Parameters
    ----------
    results : the ALREADY-COMPUTED prediction results DataFrame, with
        `.attrs['coverage']` / `.attrs['quality']` /
        `.attrs['routing_decision']` already populated (as every
        sector_pipeline.py / universal_pipeline.py prediction call
        already does). Not mutated here.
    sector : the sector this prediction run was for.
    reasoning_report : optional precomputed ReasoningReport; if
        omitted, business_confidence / risk_level fall back to
        Coverage/Quality/Routing-only signals and the dataset's
        predicted-churn rate — a caller that already has a
        ReasoningReport (e.g. from prediction_explanation.py's
        builder) should pass it in to avoid recomputation.
    """
    try:
        coverage = results.attrs.get('coverage')
        quality = results.attrs.get('quality')
        routing_decision: RoutingDecision | None = results.attrs.get('routing_decision')

        assessment = DecisionIntelligenceEngine().assess(
            sector=sector, results=results, coverage=coverage, quality=quality,
            routing_decision=routing_decision, reasoning_report=reasoning_report,
        )
        enriched = attach_decision_columns(results, assessment)
        enriched.attrs.update(results.attrs)
        enriched.attrs['decision_assessment'] = assessment
        return enriched
    except Exception as exc:
        print(f"  WARNING: decision intelligence layer failed ({exc}); "
              f"prediction output is unaffected — decision columns omitted.")
        return results


def print_architecture_diagram() -> None:
    """Print the Mermaid architecture diagram for this layer."""
    print(to_mermaid())
