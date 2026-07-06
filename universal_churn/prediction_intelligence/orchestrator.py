"""
universal_churn/prediction_intelligence/orchestrator.py
══════════════════════════════════════════════════════════════════════
PredictionIntelligenceOrchestrator — the ONE public entry point for
the Prediction Intelligence Engine (PIE), per the Version 8.2
architecture contract's "expose only one public entry point" rule.

Responsibilities
----------------
    1. build_context()  — adapt whatever shape the caller has on hand
       (typed framework objects OR the raw dicts coverage.py /
       quality_gate.py already produce) into one frozen
       PredictionIntelligenceContext, recording every degraded/missing
       input along the way.
    2. analyze()          — run every registered engine, in sequence,
       against that context, and assemble a PredictionIntelligenceReport.

Sequencing note
-----------------
The full target pipeline is:

    Prediction Assurance -> (future) Evidence Engine
                          -> (future) Robustness Engine
                          -> (future) Prediction Intelligence Score Engine

Today the orchestrator executes exactly one engine by default
(`PredictionConfidenceEngine`, kept as the default for backward
compatibility with every existing caller of this class — see
`self.engines`'s docstring below). `PredictionAssuranceEngine` — the
differently-named, differently-scoped successor concept described in
engines/prediction_assurance.py — is fully implemented and available,
but is opt-in via the `engines=` constructor argument rather than
silently replacing the default, so no existing caller's report shape
changes underneath it:

    PredictionIntelligenceOrchestrator(engines=[PredictionAssuranceEngine()])

`_assemble_report()` reads BOTH `prediction_confidence` and
`prediction_assurance` out of `prior_results` via `.get()` — whichever
engines actually ran populate their corresponding
`PredictionIntelligenceReport` field; whichever didn't, stay `None`.
This is the general pattern every future engine (Evidence, Robustness,
Score, and beyond) follows: `_assemble_report()` grows one more
`.get("engine_name")` line per new engine, and `PredictionIntelligenceReport`
(models.py) grows one more optional field — `analyze()` and
`build_context()` themselves never change, satisfying "the public API
must never change when future engines are added."

Evidence Strength and Signal Intelligence (once implemented) are
logically independent of each other's OUTPUT (both would read the same
concept-level inputs, not each other) — the orchestrator sequences
engines for report assembly, but does not force an artificial data
dependency between them. Engines that legitimately need an earlier
engine's result read it from `prior_results` (passed by name); engines
that don't, ignore `**prior_results` entirely.

Non-interference guarantee
-----------------------------
This orchestrator never mutates results DataFrames, `.attrs`, or any
framework object it's handed — it only reads them to build a context,
exactly as decision_intelligence.DecisionIntelligenceEngine does.
Nothing on the prediction path calls this today; a future integration
point (a `--pie` CLI flag, or prediction_explanation.py) can opt in.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .constants import (
    DEGRADED_NO_ROUTING_DECISION,
    DEGRADED_NO_QUALITY_RESULT,
    DEGRADED_NO_CONCEPT_CONFIDENCE,
    DEGRADED_NO_REASONING_REPORT,
    DEGRADED_NO_PREDICTION_EXPLANATION,
)
from .engines.prediction_confidence import PredictionConfidenceEngine
from .engines.prediction_assurance import PredictionAssuranceEngine
from .interfaces import PredictionIntelligenceEngine
from .models import PredictionIntelligenceContext, PredictionIntelligenceReport


def _adapt_coverage(coverage: Any) -> Any:
    """
    Accept either a routing.CoverageResult already, or the raw dict
    compute_coverage_score() returns — adapt the latter via routing.py's
    own from_coverage_dict(), exactly as routing.route() already does
    for caller convenience. Imported lazily so this module has no
    import-time dependency on routing.py (keeps PIE constructible/
    testable in isolation, per the "framework contracts only" rule —
    routing.py itself has zero ML dependency, so this import is safe
    at call time, just deferred to avoid a hard package-load coupling).
    """
    if coverage is None or isinstance(coverage, dict):
        from ..routing import CoverageResult
        if coverage is None:
            return None
        return CoverageResult.from_coverage_dict(coverage)
    return coverage


def _adapt_quality(quality: Any) -> Any:
    if quality is None:
        return None
    if isinstance(quality, dict):
        from ..routing import QualityResult
        return QualityResult.from_quality_dict(quality)
    return quality


class PredictionIntelligenceOrchestrator:
    """
    The single public entry point for Prediction Intelligence.

    `engines`, if omitted, defaults to `[PredictionConfidenceEngine()]`
    — preserved exactly as-is for backward compatibility with every
    existing caller. To run Prediction Assurance instead (or as well),
    pass it explicitly:

        PredictionIntelligenceOrchestrator(engines=[PredictionAssuranceEngine()])
        PredictionIntelligenceOrchestrator(
            engines=[PredictionConfidenceEngine(), PredictionAssuranceEngine()]
        )

    Every engine's result is stored in `prior_results` keyed by its
    `name` and made available to later engines in the same run; the
    report fields each engine feeds are read out of `prior_results` via
    `.get()` in `_assemble_report()`, so an engine that did not run
    simply leaves its corresponding report field at its default `None`.
    """

    def __init__(self, engines: list[PredictionIntelligenceEngine] | None = None) -> None:
        self.engines: list[PredictionIntelligenceEngine] = (
            list(engines) if engines is not None else [PredictionConfidenceEngine()]
        )

    # ── context construction ────────────────────────────────────

    @staticmethod
    def build_context(
        sector: str,
        predicted_churn: str,
        churn_probability: float,
        risk_level: str,
        coverage: Any,
        routing_decision: Any = None,
        quality: Any = None,
        concept_confidence: dict | None = None,
        customer_id: str | None = None,
        reasoning_report: Any = None,
        prediction_explanation: Any = None,
    ) -> PredictionIntelligenceContext:
        """
        Build one PredictionIntelligenceContext for a single prediction
        row. `coverage` / `quality` may be passed as either the typed
        routing.py adapter objects OR the raw dicts coverage.py /
        quality_gate.py produce — both are accepted, mirroring
        routing.route()'s own dict-or-adapter convenience.

        `concept_confidence`, when not supplied explicitly, is read
        from `coverage`'s embedded 'concept_confidence' dict if the raw
        coverage dict form was passed (coverage.py always embeds it
        there — see coverage.py's compute_coverage_score() docstring).
        """
        degraded: list[str] = []

        coverage_dict_form = coverage if isinstance(coverage, dict) else None
        adapted_coverage = _adapt_coverage(coverage)
        adapted_quality = _adapt_quality(quality)

        if concept_confidence is None and coverage_dict_form is not None:
            concept_confidence = coverage_dict_form.get("concept_confidence")
        if not concept_confidence:
            degraded.append(DEGRADED_NO_CONCEPT_CONFIDENCE)

        if routing_decision is None:
            degraded.append(DEGRADED_NO_ROUTING_DECISION)

        if adapted_quality is None:
            degraded.append(DEGRADED_NO_QUALITY_RESULT)

        if reasoning_report is None:
            degraded.append(DEGRADED_NO_REASONING_REPORT)

        if prediction_explanation is None:
            degraded.append(DEGRADED_NO_PREDICTION_EXPLANATION)

        return PredictionIntelligenceContext(
            sector=sector,
            customer_id=customer_id,
            predicted_churn=predicted_churn,
            churn_probability=churn_probability,
            risk_level=risk_level,
            coverage=adapted_coverage,
            concept_confidence=concept_confidence,
            routing_decision=routing_decision,
            quality=adapted_quality,
            reasoning_report=reasoning_report,
            prediction_explanation=prediction_explanation,
            degraded_inputs=tuple(degraded),
        )

    # ── execution ────────────────────────────────────────────────

    def analyze(self, context: PredictionIntelligenceContext) -> PredictionIntelligenceReport:
        """
        Run every registered engine against `context` and assemble the
        PredictionIntelligenceReport. Engines run in `self.engines`
        order; each engine's result is made available to subsequent
        engines via `prior_results` (keyed by `engine.name`), though no
        current engine (Module 1 only) actually depends on another.
        """
        prior_results: dict[str, Any] = {}
        for engine in self.engines:
            prior_results[engine.name] = engine.analyze(context, **prior_results)

        return self._assemble_report(context, prior_results)

    def analyze_prediction(
        self,
        sector: str,
        predicted_churn: str,
        churn_probability: float,
        risk_level: str,
        coverage: Any,
        routing_decision: Any = None,
        quality: Any = None,
        concept_confidence: dict | None = None,
        customer_id: str | None = None,
        reasoning_report: Any = None,
        prediction_explanation: Any = None,
    ) -> PredictionIntelligenceReport:
        """One-call convenience: build_context() + analyze() together."""
        context = self.build_context(
            sector=sector,
            predicted_churn=predicted_churn,
            churn_probability=churn_probability,
            risk_level=risk_level,
            coverage=coverage,
            routing_decision=routing_decision,
            quality=quality,
            concept_confidence=concept_confidence,
            customer_id=customer_id,
            reasoning_report=reasoning_report,
            prediction_explanation=prediction_explanation,
        )
        return self.analyze(context)

    # ── report assembly ─────────────────────────────────────────

    def _assemble_report(
        self,
        context: PredictionIntelligenceContext,
        prior_results: dict[str, Any],
    ) -> PredictionIntelligenceReport:
        return PredictionIntelligenceReport(
            sector=context.sector,
            customer_id=context.customer_id,
            predicted_churn=context.predicted_churn,
            churn_probability=context.churn_probability,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            prediction_confidence=prior_results.get("prediction_confidence"),
            prediction_assurance=prior_results.get("prediction_assurance"),
            evidence_strength=prior_results.get("evidence_strength"),
            signal_intelligence=prior_results.get("signal_intelligence"),
            stability=prior_results.get("stability"),
            consistency=prior_results.get("consistency"),
            intelligence_score=prior_results.get("intelligence_score"),
            degraded_inputs=context.degraded_inputs,
        )


def run_prediction_intelligence(
    sector: str,
    predicted_churn: str,
    churn_probability: float,
    risk_level: str,
    coverage: Any,
    routing_decision: Any = None,
    quality: Any = None,
    concept_confidence: dict | None = None,
    customer_id: str | None = None,
    reasoning_report: Any = None,
    prediction_explanation: Any = None,
) -> PredictionIntelligenceReport:
    """
    Module-level convenience wrapper around a default-configured
    orchestrator — mirrors business_reasoning.run_business_reasoning()
    and decision_intelligence.run_decision_intelligence()'s shape.
    """
    return PredictionIntelligenceOrchestrator().analyze_prediction(
        sector=sector,
        predicted_churn=predicted_churn,
        churn_probability=churn_probability,
        risk_level=risk_level,
        coverage=coverage,
        routing_decision=routing_decision,
        quality=quality,
        concept_confidence=concept_confidence,
        customer_id=customer_id,
        reasoning_report=reasoning_report,
        prediction_explanation=prediction_explanation,
    )