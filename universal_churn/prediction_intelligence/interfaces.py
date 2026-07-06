"""
universal_churn/prediction_intelligence/interfaces.py
══════════════════════════════════════════════════════════════════════
Prediction Intelligence — Core Contracts (Version 8.2, Module 0).

This module defines the ONLY two things every engine in this package
depends on:

    PredictionIntelligenceContext   — the frozen, read-only bundle of
                                       already-computed framework
                                       objects a single prediction is
                                       evaluated against.
    PredictionIntelligenceEngine    — the ABC every engine
                                       (Confidence, Evidence, Signal,
                                       Stability, Consistency, Score)
                                       implements, mirroring the
                                       PipelineStage ABC pattern
                                       already used in
                                       pipeline_stages.py — same
                                       shape, new domain.

Hard architectural rules enforced by construction here
--------------------------------------------------------
    1. Prediction Intelligence is a FRAMEWORK layer, not a prediction
       layer. PredictionIntelligenceContext holds only already-computed
       framework result objects (CoverageResult, ConceptConfidenceReport,
       RoutingDecision, QualityResult, and — opportunistically —
       ReasoningReport / PredictionExplanation). It never holds a raw
       DataFrame, a feature matrix, or a model object, and nothing in
       this package imports pandas for data access, xgboost, sklearn,
       or any sector pipeline.
    2. ReasoningReport and PredictionExplanation are the only two
       fields allowed to be None as a NORMAL, expected state (some
       framework configurations disable business reasoning or
       explanation entirely). CoverageResult, RoutingDecision, and
       QualityResult are the official "required" inputs per the
       integration contract, but real call sites (see
       universal_pipeline.predict_universal()'s `_precomputed_coverage`
       path) can legitimately produce quality=None or
       routing_decision=None too. This package therefore treats EVERY
       field beyond `coverage` itself as optional at the type level and
       degrades gracefully everywhere — never crashes because an
       optional signal is missing, only reports reduced richness.
    3. Every engine consumes a PredictionIntelligenceContext (plus, per
       the pipeline's own sequencing, any prior engine results it
       legitimately depends on) and returns its own typed,
       to_dict()-able dataclass — the same convention already used by
       ColumnQualityResult, RoutingDecision, BusinessInference, etc.
       elsewhere in this codebase.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from ..routing import CoverageResult, RoutingDecision, QualityResult
from ..concept_confidence import ConceptConfidenceReport
from ..business_reasoning import ReasoningReport


# ══════════════════════════════════════════════════════════════════
# THE CONTEXT — one prediction's worth of already-computed evidence
# ══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PredictionIntelligenceContext:
    """
    Everything Prediction Intelligence is allowed to know about ONE
    prediction. Built once per row by context.build_context() (or
    supplied directly by an advanced caller) and never mutated —
    every engine reads it, none of them write back into it.

    Required (per the integration contract)
    -----------------------------------------
    customer_id, predicted_churn, churn_probability, risk_level,
    sector, coverage — a prediction is meaningless to reason about
    without at least knowing what was predicted and how complete the
    input schema was.

    Officially required, defensively optional
    --------------------------------------------
    routing_decision / quality are contractually "required" inputs,
    but real prediction call sites can produce either as None (e.g. a
    universal-mode fallback invoked with `_precomputed_coverage` skips
    re-running the quality gate — see universal_pipeline.py's
    docstring). Rather than crash on a legitimate real-world shape,
    every engine treats a missing routing_decision/quality as reduced
    evidence and records that fact, exactly as it does for the two
    contractually-optional fields below.

    Optional (caller-supplied, normal to be absent)
    --------------------------------------------------
    concept_confidence, reasoning_report, prediction_explanation —
    Prediction Intelligence NEVER computes these itself (that would
    mean touching raw data or re-deriving framework state it doesn't
    own). A caller that already has them (e.g. cli.py, which already
    builds a ReasoningReport via prediction_explanation.py) may pass
    them in; a caller that doesn't, doesn't need to.
    """
    customer_id: str
    predicted_churn: str          # 'Yes' | 'No'
    churn_probability: float
    risk_level: str
    sector: str
    coverage: CoverageResult

    concept_confidence: ConceptConfidenceReport | None = None
    routing_decision: RoutingDecision | None = None
    quality: QualityResult | None = None
    reasoning_report: ReasoningReport | None = None
    prediction_explanation: Any | None = None  # unknown shape upstream — see module docstring

    def degraded_inputs(self) -> tuple[str, ...]:
        """
        Which optional-or-should-be-required inputs are missing for
        THIS context. Every engine that reads a missing field calls
        this (or checks the relevant field directly) to record
        richness reduction on its own result — this method is just the
        canonical list so every engine agrees on the same names.
        """
        missing = []
        if self.concept_confidence is None:
            missing.append("concept_confidence")
        if self.routing_decision is None:
            missing.append("routing_decision")
        if self.quality is None:
            missing.append("quality")
        if self.reasoning_report is None:
            missing.append("reasoning_report")
        if self.prediction_explanation is None:
            missing.append("prediction_explanation")
        return tuple(missing)

    def to_dict(self) -> dict:
        return {
            'customer_id': self.customer_id,
            'predicted_churn': self.predicted_churn,
            'churn_probability': self.churn_probability,
            'risk_level': self.risk_level,
            'sector': self.sector,
            'coverage_band': self.coverage.status,
            'coverage_score': self.coverage.coverage_score,
            'has_concept_confidence': self.concept_confidence is not None,
            'has_routing_decision': self.routing_decision is not None,
            'has_quality': self.quality is not None,
            'has_reasoning_report': self.reasoning_report is not None,
            'has_prediction_explanation': self.prediction_explanation is not None,
            'degraded_inputs': list(self.degraded_inputs()),
        }


# ══════════════════════════════════════════════════════════════════
# THE ENGINE ABC
# ══════════════════════════════════════════════════════════════════

EngineResult = TypeVar("EngineResult")


class PredictionIntelligenceEngine(ABC, Generic[EngineResult]):
    """
    Contract every Prediction Intelligence engine implements — mirrors
    pipeline_stages.PipelineStage's shape (a stable name, explicit
    upstream dependencies, one analyze-and-return method) applied to
    this new domain instead of feature preparation.

    `requires` is documentation + a cheap runtime guard, not a
    scheduler — PredictionIntelligenceOrchestrator (orchestrator.py)
    is the only thing that actually sequences engines; an engine never
    calls another engine itself.
    """
    name: str = "unnamed_engine"
    requires: tuple[str, ...] = ()  # names of prior engine results this one reads

    @abstractmethod
    def analyze(
        self,
        context: PredictionIntelligenceContext,
        **prior_results: Any,
    ) -> EngineResult:
        """
        Parameters
        ----------
        context : the shared, read-only PredictionIntelligenceContext.
        prior_results : keyword-supplied outputs of engines this one
            `requires`, e.g. `stability=<StabilityResult>`. An engine
            with an empty `requires` tuple ignores this entirely.
        """
        raise NotImplementedError

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<PredictionIntelligenceEngine:{self.name}>"
