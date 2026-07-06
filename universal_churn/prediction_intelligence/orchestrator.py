"""
universal_churn/prediction_intelligence/orchestrator.py
══════════════════════════════════════════════════════════════════════
PredictionIntelligenceOrchestrator — the ONE public entry point.

Per the architecture's future-extensibility requirement, everything
external ever needs to touch is this class. Internally it sequences
the six engines in the fixed order the architecture specifies:

    Prediction Layer
          │
          ▼
    Prediction Intelligence Layer
          │
     ┌────┼────┐
     ▼    ▼    ▼
  Confidence  Evidence  Signal          (Modules 1, 2, 3 — independent)
     └────┼────┘
          ▼
    Stability Engine                    (Module 4 — reads 1 & 2, adjusted by 3)
          │
          ▼
    Consistency Engine                  (Module 5 — reads 1, 2, 3, 4)
          │
          ▼
    Intelligence Score Engine           (Module 6 — reads everything)
          │
          ▼
    Prediction Intelligence Report

Non-interference guarantee
-----------------------------
Nothing on the live prediction path (cli.py, sector_pipeline.py,
universal_pipeline.py, routing.py, reporting.py) imports this package.
It is opt-in, additive tooling — exactly the pattern already
established by business_reasoning.py's `run_business_reasoning()` and
decision_intelligence.py's `run_decision_intelligence()` before either
was (optionally) wired into a caller. `analyze()` never mutates its
input context and returns a brand-new, frozen
PredictionIntelligenceReport every call.

Future extensibility
------------------------
A future engine (Counterfactual, Drift, Uncertainty, Calibration,
Temporal Stability — per the architecture's stated roadmap) plugs in
by:
    1. Adding one new engine module under `engines/`, implementing
       `PredictionIntelligenceEngine` with an explicit `requires`
       tuple.
    2. Adding one line to `_ENGINE_SEQUENCE` below, in dependency
       order.
    3. Optionally adding its result to `PredictionIntelligenceReport`
       (report.py) if it should appear in the final deliverable.
No existing engine, no existing report field, and no caller of
`PredictionIntelligenceOrchestrator.analyze()` needs to change for
this to work — every engine only ever reads what it explicitly
`requires` from `prior_results`, never the whole registry.
"""
from __future__ import annotations

from typing import Any

from .interfaces import PredictionIntelligenceContext
from .context import build_context, build_contexts_for_results
from .report import PredictionIntelligenceReport, build_report

from .engines.prediction_confidence import PredictionConfidenceEngine
from .engines.evidence_engine import EvidenceEngine
from .engines.signal_intelligence import SignalIntelligenceEngine
from .engines.stability_engine import StabilityEngine
from .engines.consistency_engine import ConsistencyEngine
from .engines.intelligence_score_engine import IntelligenceScoreEngine


class PredictionIntelligenceOrchestrator:
    """
    Stateless aside from its engine instances (each engine is itself
    stateless — safe to reuse across many `analyze()` calls, same as
    business_reasoning.BusinessReasoningEngine).
    """

    def __init__(self) -> None:
        self._prediction_confidence = PredictionConfidenceEngine()
        self._evidence = EvidenceEngine()
        self._signal = SignalIntelligenceEngine()
        self._stability = StabilityEngine()
        self._consistency = ConsistencyEngine()
        self._intelligence_score = IntelligenceScoreEngine()

    def analyze(self, context: PredictionIntelligenceContext) -> PredictionIntelligenceReport:
        """
        Run every engine, in the architecture's fixed order, and return
        one PredictionIntelligenceReport. Never raises on a missing
        optional input (concept_confidence / routing_decision / quality
        / reasoning_report / prediction_explanation) — every engine
        degrades gracefully on its own, per interfaces.py's contract.
        """
        prediction_confidence = self._prediction_confidence.analyze(context)
        evidence = self._evidence.analyze(context)
        signal = self._signal.analyze(context)

        stability = self._stability.analyze(
            context,
            prediction_confidence=prediction_confidence,
            evidence=evidence,
            signal=signal,
        )

        consistency = self._consistency.analyze(
            context,
            prediction_confidence=prediction_confidence,
            evidence=evidence,
            signal=signal,
            stability=stability,
        )

        intelligence_score = self._intelligence_score.analyze(
            context,
            prediction_confidence=prediction_confidence,
            evidence=evidence,
            signal=signal,
            stability=stability,
            consistency=consistency,
        )

        return build_report(
            context=context,
            prediction_confidence=prediction_confidence,
            evidence=evidence,
            signal=signal,
            stability=stability,
            consistency=consistency,
            intelligence_score=intelligence_score,
        )

    def analyze_many(
        self, contexts: list[PredictionIntelligenceContext],
    ) -> list[PredictionIntelligenceReport]:
        """Convenience: analyze a batch of contexts (e.g. every row of
        one prediction run) in one call."""
        return [self.analyze(c) for c in contexts]


# ══════════════════════════════════════════════════════════════════
# ONE-SHOT CONVENIENCE FUNCTIONS
# ══════════════════════════════════════════════════════════════════
# Mirror business_reasoning.run_business_reasoning() /
# decision_intelligence.run_decision_intelligence()'s module-level
# wrapper convention — a caller that doesn't want to instantiate the
# orchestrator itself doesn't have to.

def evaluate_prediction(
    row: Any,
    attrs: dict,
    sector: str,
    reasoning_report: Any | None = None,
    prediction_explanation: Any | None = None,
) -> PredictionIntelligenceReport:
    """One row -> one PredictionIntelligenceReport, in a single call."""
    context = build_context(
        row=row, attrs=attrs, sector=sector,
        reasoning_report=reasoning_report,
        prediction_explanation=prediction_explanation,
    )
    return PredictionIntelligenceOrchestrator().analyze(context)


def evaluate_predictions_for_results(
    results: Any,
    sector: str,
    reasoning_report: Any | None = None,
    prediction_explanation: Any | None = None,
) -> list[PredictionIntelligenceReport]:
    """
    Every row of an already-produced `results` DataFrame -> one
    PredictionIntelligenceReport each, sharing the same file-level
    coverage/quality/routing context (see context.py's docstring on
    why that sharing is architecturally correct, not a shortcut).
    """
    contexts = build_contexts_for_results(
        results=results, sector=sector,
        reasoning_report=reasoning_report,
        prediction_explanation=prediction_explanation,
    )
    return PredictionIntelligenceOrchestrator().analyze_many(contexts)
