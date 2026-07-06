"""
universal_churn/prediction_intelligence/context.py
══════════════════════════════════════════════════════════════════════
Prediction Intelligence — Context Construction (Version 8.2, Module 0).

The ONLY place this package translates real prediction-pipeline output
shapes (a `results` DataFrame row, plus `results.attrs`) into a
PredictionIntelligenceContext. Every other module in this package only
ever reads a PredictionIntelligenceContext — this is the single seam
between "however sector_pipeline.py / universal_pipeline.py happen to
shape their output today" and "the stable contract every engine below
relies on."

Import discipline
-------------------
This module imports `routing` (for the CoverageResult/QualityResult
adapters that already exist and are already the single source of
truth for that translation) and `concept_confidence` (for the
ConceptConfidenceReport dataclass shape). It does NOT import pandas
for anything beyond type hints, does not import any sector pipeline,
does not import xgboost, and never reads a raw CSV or feature matrix.
`results` is only ever read for the small set of already-computed
columns/attrs a finished prediction carries — never for anything a
model or feature pipeline produced that Prediction Intelligence isn't
supposed to see.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from ..routing import CoverageResult, RoutingDecision, QualityResult
from ..concept_confidence import (
    ConceptConfidenceReport, ConceptConfidenceEntry,
)
from ..business_reasoning import ReasoningReport
from .interfaces import PredictionIntelligenceContext


# ══════════════════════════════════════════════════════════════════
# ADAPTER — dict embedded in coverage['concept_confidence'] -> typed
# ══════════════════════════════════════════════════════════════════
# coverage.py already embeds concept_confidence.py's report as a plain
# dict inside its own return dict (see coverage.compute_coverage_score's
# 'concept_confidence' key). concept_confidence.py itself has no
# from_dict() classmethod (it only ever produces the typed report
# directly), so this adapter exists here — read-only, additive,
# doesn't touch concept_confidence.py — mirroring exactly how
# routing.CoverageResult.from_coverage_dict() already adapts
# coverage.py's dict shape for routing.py's own purposes.

def _concept_confidence_report_from_dict(d: dict | None) -> ConceptConfidenceReport | None:
    """Rebuild a typed ConceptConfidenceReport from the dict shape
    coverage.py embeds. Returns None if the dict is missing, empty, or
    itself signals an internal computation error (coverage.py degrades
    concept confidence failures to an 'error' key rather than raising —
    Prediction Intelligence treats that the same as "not available")."""
    if not d or d.get('error'):
        return None

    per_concept = {}
    for name, entry in (d.get('per_concept') or {}).items():
        per_concept[name] = ConceptConfidenceEntry(
            concept=name,
            confidence=entry.get('confidence', 0.0),
            reconstructable=entry.get('reconstructable', False),
            reason=entry.get('reason', ''),
            canonical_field=entry.get('canonical_field'),
            source_confidence=entry.get('source_confidence'),
            resolution_confidence=entry.get('resolution_confidence'),
        )

    return ConceptConfidenceReport(
        sector=d.get('sector', ''),
        per_concept=per_concept,
        overall_confidence=d.get('overall_confidence', 0.0),
        reconstructable_concepts=d.get('reconstructable_concepts', 0),
        total_concepts=d.get('total_concepts', 0),
        concepts_reconstructable=d.get('concepts_reconstructable', False),
    )


# ══════════════════════════════════════════════════════════════════
# BUILD ONE CONTEXT PER ROW
# ══════════════════════════════════════════════════════════════════

_ID_CANDIDATES = ('CustomerID', 'customerID', 'Customer ID', 'CustomerId', 'PatientID')


def build_context(
    row: "pd.Series | dict",
    attrs: dict,
    sector: str,
    reasoning_report: ReasoningReport | None = None,
    prediction_explanation: Any | None = None,
) -> PredictionIntelligenceContext:
    """
    Build ONE row's PredictionIntelligenceContext.

    Parameters
    ----------
    row : one row of a prediction `results` DataFrame (a pandas Series
        from `results.iterrows()`, or an equivalent dict) — read only
        for `Predicted_Churn`, `Churn_Probability`, `Risk_Level`, and
        an ID column. Never for feature columns.
    attrs : `results.attrs` — the file-level context every prediction
        pipeline already attaches: `coverage` (dict), `quality` (dict
        or None), `routing_decision` (RoutingDecision or None). Shared
        across every row of the same file, per the architectural fact
        that coverage/quality/routing are computed once per batch, not
        once per row (see the Version 8.2 analysis note this package
        implements).
    sector : the sector this prediction run was for.
    reasoning_report / prediction_explanation : optional, caller-
        supplied framework objects Prediction Intelligence never
        computes itself.
    """
    coverage_dict = attrs.get('coverage')
    if coverage_dict is None:
        raise ValueError(
            "build_context() requires attrs['coverage'] — Prediction "
            "Intelligence cannot evaluate a prediction with no coverage "
            "measurement at all. (routing_decision/quality/concept_"
            "confidence may legitimately be None; coverage may not.)"
        )
    coverage = CoverageResult.from_coverage_dict(coverage_dict)
    concept_confidence = _concept_confidence_report_from_dict(
        coverage_dict.get('concept_confidence')
    )

    quality_dict = attrs.get('quality')
    quality = QualityResult.from_quality_dict(quality_dict) if quality_dict else None

    routing_decision = attrs.get('routing_decision')  # already typed, or None

    customer_id = None
    for candidate in _ID_CANDIDATES:
        if candidate in row and row[candidate] is not None:
            customer_id = str(row[candidate])
            break
    if customer_id is None:
        customer_id = str(row.get('CustomerID', 'UNKNOWN'))

    return PredictionIntelligenceContext(
        customer_id=customer_id,
        predicted_churn=str(row.get('Predicted_Churn', 'No')),
        churn_probability=float(row.get('Churn_Probability', 0.0)),
        risk_level=str(row.get('Risk_Level', 'Unknown')),
        sector=sector,
        coverage=coverage,
        concept_confidence=concept_confidence,
        routing_decision=routing_decision,
        quality=quality,
        reasoning_report=reasoning_report,
        prediction_explanation=prediction_explanation,
    )


def build_contexts_for_results(
    results: pd.DataFrame,
    sector: str,
    reasoning_report: ReasoningReport | None = None,
    prediction_explanation: Any | None = None,
) -> list[PredictionIntelligenceContext]:
    """
    Convenience: one PredictionIntelligenceContext per row of an
    already-produced `results` DataFrame, all sharing the same
    file-level `reasoning_report` / `prediction_explanation` (both are
    dataset-level objects today — see business_reasoning.py /
    prediction_explanation.py — not per-row).
    """
    return [
        build_context(
            row=row, attrs=results.attrs, sector=sector,
            reasoning_report=reasoning_report,
            prediction_explanation=prediction_explanation,
        )
        for _, row in results.iterrows()
    ]
