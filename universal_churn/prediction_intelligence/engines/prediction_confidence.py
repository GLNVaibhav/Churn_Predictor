"""
universal_churn/prediction_intelligence/engines/prediction_confidence.py
══════════════════════════════════════════════════════════════════════
Module 1 — Prediction Confidence Engine.

Answers exactly one question, deliberately narrow: "how decisively did
the model call THIS row?" — nothing about whether the model was fed
good data (that's Module 2, Evidence), nothing about whether business
reasoning agrees (Module 3, Signal). This is the model-agnostic
analogue of "distance from the coin-flip line."

Model-agnostic by construction
--------------------------------
This engine reads exactly one number — `context.churn_probability`, a
float in [0, 1] — and nothing else. It does not know or care whether
that probability came from a Sector XGBoost model, the Universal
model, or a future neural/ensemble model (per the architecture's
"Prediction Intelligence should behave identically" requirement). A
probability is a probability.

Relationship to existing "Prediction Confidence" column
------------------------------------------------------------
reporting.py already attaches a `Prediction_Confidence` label via
utils.prediction_confidence_label() (Very High/High/Medium/Low/Very
Low, on fixed thresholds). This engine is NOT a duplicate of that
column — it exists at a different layer (Prediction Intelligence,
not the per-row reporting attach step) and produces a distinct,
richer result object (with a continuous decisiveness score plus a
band) that later PIE modules (Stability, Consistency) can combine
with Evidence/Signal — something a bare string label can't be
combined with numerically. Two independent implementations computing
a similar-shaped label is intentional here, not a code smell: PIE
must never import reporting.py or depend on its output shape, since
reporting.py is a presentation layer PIE has to remain agnostic to.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..interfaces import PredictionIntelligenceContext, PredictionIntelligenceEngine


@dataclass(frozen=True)
class PredictionConfidenceResult:
    probability: float
    decisiveness: float          # abs(p - 0.5) * 2, in [0, 1] — 0 = coin flip, 1 = certain
    confidence_band: str          # 'Very High' | 'High' | 'Moderate' | 'Low' | 'Very Low'
    near_boundary: bool           # True if the probability sits close to the decision threshold

    def to_dict(self) -> dict:
        return {
            'probability': self.probability,
            'decisiveness': self.decisiveness,
            'confidence_band': self.confidence_band,
            'near_boundary': self.near_boundary,
        }


def _band_for(decisiveness: float) -> str:
    if decisiveness >= 0.80:
        return "Very High"
    if decisiveness >= 0.60:
        return "High"
    if decisiveness >= 0.35:
        return "Moderate"
    if decisiveness >= 0.15:
        return "Low"
    return "Very Low"


class PredictionConfidenceEngine(PredictionIntelligenceEngine[PredictionConfidenceResult]):
    """Module 1. No upstream dependencies — the first thing the
    orchestrator runs, per the architecture diagram's three-way fan-out
    (Confidence / Evidence / Signal all read only the raw context)."""

    name = "prediction_confidence"
    requires: tuple[str, ...] = ()

    #: Distance from 0.5 within which a probability is considered
    #: "close enough to the fence" to flag explicitly — independent of
    #: whatever sector-specific decision threshold
    #: (config.SECTOR_THRESHOLDS) the model itself used to label
    #: Predicted_Churn, since PIE never reads sector config.
    NEAR_BOUNDARY_WINDOW = 0.10

    def analyze(
        self,
        context: PredictionIntelligenceContext,
        **prior_results,
    ) -> PredictionConfidenceResult:
        p = max(0.0, min(1.0, context.churn_probability))
        decisiveness = round(abs(p - 0.5) * 2, 4)
        near_boundary = abs(p - 0.5) <= self.NEAR_BOUNDARY_WINDOW

        return PredictionConfidenceResult(
            probability=p,
            decisiveness=decisiveness,
            confidence_band=_band_for(decisiveness),
            near_boundary=near_boundary,
        )
