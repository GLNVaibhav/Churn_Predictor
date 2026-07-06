"""
universal_churn/prediction_intelligence
══════════════════════════════════════════════════════════════════════
Prediction Intelligence Engine — Version 8.2.

    Prediction Layer
          │
          ▼
    Prediction Intelligence Layer
          │
     ┌────┼────┐
     ▼    ▼    ▼
  Confidence  Evidence  Signal
     └────┼────┘
          ▼
    Stability Engine
          │
          ▼
    Consistency Engine
          │
          ▼
    Intelligence Score Engine
          │
          ▼
    Prediction Intelligence Report

WHAT THIS PACKAGE IS
---------------------
A framework layer, not a prediction layer. It evaluates the OUTPUTS of
prior framework layers (Coverage, Concept Confidence, Routing, Quality,
and — optionally — Reasoning/Explanation) and never touches raw
datasets, feature matrices, model internals, or ML artifacts. It is
completely model-agnostic: whether Predicted_Churn/Churn_Probability
came from the Sector model, the Universal model, or a future
neural/ensemble model, Prediction Intelligence behaves identically,
because it only ever reads a probability and a set of already-computed
framework result objects.

WHAT THIS PACKAGE IS NOT
--------------------------
It is not wired into cli.py, sector_pipeline.py, universal_pipeline.py,
routing.py, or reporting.py. Prediction output is byte-for-byte
identical whether or not this package is ever imported — exactly the
non-interference guarantee business_reasoning.py, concept_graph_report.py,
prediction_explanation.py, and decision_intelligence.py already provide
for themselves. A future caller opts in explicitly (see
orchestrator.evaluate_prediction() / evaluate_predictions_for_results()).

PUBLIC SURFACE
---------------
Per the architecture's future-extensibility rule ("Prediction
Intelligence should expose only one public entry point"), the primary
thing external code should reach for is `PredictionIntelligenceOrchestrator`.
The context/report types are also exported here because a caller
necessarily needs to construct the former and read the latter — but no
individual engine class is re-exported at this level; engines are an
internal implementation detail the orchestrator alone sequences (see
`prediction_intelligence.engines` if you specifically need to test one
engine in isolation).
"""
from __future__ import annotations

from .interfaces import PredictionIntelligenceContext, PredictionIntelligenceEngine
from .context import build_context, build_contexts_for_results
from .report import PredictionIntelligenceReport, print_prediction_intelligence_report
from .orchestrator import (
    PredictionIntelligenceOrchestrator,
    evaluate_prediction,
    evaluate_predictions_for_results,
)

__all__ = [
    "PredictionIntelligenceOrchestrator",
    "PredictionIntelligenceContext",
    "PredictionIntelligenceEngine",
    "PredictionIntelligenceReport",
    "build_context",
    "build_contexts_for_results",
    "evaluate_prediction",
    "evaluate_predictions_for_results",
    "print_prediction_intelligence_report",
]
