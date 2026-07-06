"""
universal_churn.prediction_intelligence
══════════════════════════════════════════════════════════════════════
Prediction Intelligence Engine (PIE) — Version 8.2.

Sits AFTER Prediction and BEFORE Prediction Explanation / Decision
Intelligence:

    Prediction
      -> Prediction Intelligence Engine   (THIS PACKAGE)
      -> Prediction Explanation           (prediction_explanation.py)
      -> Decision Intelligence            (decision_intelligence.py)

PIE is a deterministic reasoning layer that evaluates the quality,
trustworthiness, stability, and business evidence of an ALREADY-
GENERATED prediction. It is not a model, not an LLM, not an agent.

Non-interference guarantee
-----------------------------
Nothing in this package is imported by cli.py, sector_pipeline.py,
universal_pipeline.py, routing.py, coverage.py, quality_gate.py,
concept_confidence.py, business_reasoning.py, or
prediction_explanation.py. It is opt-in, additive tooling — exactly
the pattern business_reasoning.py / decision_intelligence.py already
established for their own layers. Calling it (or not) never changes
any existing module's output.

Import discipline (per the Version 8.2 architecture contract)
------------------------------------------------------------------
This package NEVER imports:
    - ML libraries (xgboost, sklearn, imblearn, shap)
    - sector_pipeline.py / universal_pipeline.py
    - preprocessing.py / feature_engineering.py / schema_resolution.py
    - any raw dataset or feature matrix

It consumes ONLY already-computed framework result objects:
    PredictionResult (a row of a prediction results DataFrame)
    CoverageResult          (routing.py's typed adapter)
    ConceptConfidenceReport (concept_confidence.py's dict/report)
    RoutingDecision         (routing.py)
    QualityResult           (routing.py's typed adapter)
    ReasoningReport         (business_reasoning.py) — OPTIONAL
    PredictionExplanation   (prediction_explanation.py) — OPTIONAL

Public surface
--------------
Exactly one public entry point, per the architecture contract:
    PredictionIntelligenceOrchestrator

Everything else (individual engines, dataclasses, report formatting)
is available for direct use/testing but is not the intended external
integration surface — future engines (Evidence, Robustness, Prediction
Intelligence Score, and later Counterfactual, Drift, Uncertainty,
Calibration, Temporal Stability) plug into the orchestrator without
changing this public surface.

Engines implemented so far
-----------------------------
    PredictionConfidenceEngine  — the orchestrator's DEFAULT engine
                                    (kept for backward compatibility).
    PredictionAssuranceEngine  — "how strongly does the framework
                                    stand behind this prediction?" —
                                    the differently-named, differently
                                    -scoped successor concept. Fully
                                    implemented; opt-in via
                                    `PredictionIntelligenceOrchestrator(
                                    engines=[PredictionAssuranceEngine()])`.
"""
from __future__ import annotations

from .orchestrator import PredictionIntelligenceOrchestrator, run_prediction_intelligence
from .models import (
    PredictionIntelligenceContext,
    PredictionIntelligenceReport,
    PredictionConfidenceResult,
    PredictionAssuranceResult,
)

PREDICTION_INTELLIGENCE_VERSION = "8.2.1"

__all__ = [
    "PredictionIntelligenceOrchestrator",
    "run_prediction_intelligence",
    "PredictionIntelligenceContext",
    "PredictionIntelligenceReport",
    "PredictionConfidenceResult",
    "PredictionAssuranceResult",
    "PREDICTION_INTELLIGENCE_VERSION",
]