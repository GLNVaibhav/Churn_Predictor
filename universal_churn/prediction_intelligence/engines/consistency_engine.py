"""
universal_churn/prediction_intelligence/engines/consistency_engine.py
══════════════════════════════════════════════════════════════════════
Module 5 — Consistency Engine.

Answers: "do all four prior signals (Confidence, Evidence, Signal,
Stability) tell one coherent story, or do they pull in different
directions?" — this is distinct from Stability (Module 4), which only
checks Confidence-vs-Evidence; Consistency looks across the WHOLE
picture, including whether Stability's own verdict matches what you'd
expect given the other three. A prediction can be individually
"Moderately Stable" and still be internally inconsistent (e.g. strong
evidence, but business reasoning diverging AND an unstable band) —
Consistency is what surfaces that.

This engine produces flagged conflicts as short, literal statements
("Evidence is Strong but Signal is Diverging") rather than a single
opaque number — per this codebase's established convention
(routing.RoutingDecision.warnings, quality_gate's `reasons`,
concept_confidence's per-concept `reason`) of always pairing a score
with the specific, inspectable reason behind it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..interfaces import PredictionIntelligenceContext, PredictionIntelligenceEngine
from .prediction_confidence import PredictionConfidenceResult
from .evidence_engine import EvidenceResult
from .signal_intelligence import SignalIntelligenceResult
from .stability_engine import StabilityResult


@dataclass(frozen=True)
class ConsistencyResult:
    consistency_score: float          # in [0, 1]
    consistency_band: str              # 'Consistent' | 'Partially Consistent' | 'Inconsistent'
    conflicts: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            'consistency_score': self.consistency_score,
            'consistency_band': self.consistency_band,
            'conflicts': list(self.conflicts),
        }


def _band_for(score: float) -> str:
    if score >= 0.75:
        return "Consistent"
    if score >= 0.45:
        return "Partially Consistent"
    return "Inconsistent"


class ConsistencyEngine(PredictionIntelligenceEngine[ConsistencyResult]):
    """Module 5. Requires all four upstream results — the last
    cross-checking step before everything is compressed into a single
    Intelligence Score (Module 6)."""

    name = "consistency_engine"
    requires: tuple[str, ...] = (
        "prediction_confidence", "evidence", "signal", "stability",
    )

    #: A "high" band, for the purposes of flagging a conflict, is
    #: anything at or above this threshold on a [0,1]-scaled signal.
    HIGH = 0.65
    LOW = 0.35

    def analyze(
        self,
        context: PredictionIntelligenceContext,
        **prior_results,
    ) -> ConsistencyResult:
        confidence: PredictionConfidenceResult = prior_results["prediction_confidence"]
        evidence: EvidenceResult = prior_results["evidence"]
        signal: SignalIntelligenceResult = prior_results["signal"]
        stability: StabilityResult = prior_results["stability"]

        conflicts: list[str] = []

        # Conflict 1 — decisive model, weak evidence (Stability already
        # flags this as overconfidence; Consistency restates it as a
        # cross-signal conflict so it also counts toward this score).
        if confidence.decisiveness >= self.HIGH and evidence.evidence_strength <= self.LOW:
            conflicts.append(
                f"Prediction Confidence is {confidence.confidence_band} but "
                f"Evidence is {evidence.evidence_band} — a decisive call on "
                f"a thin input."
            )

        # Conflict 2 — strong evidence, but business reasoning diverges.
        if evidence.evidence_strength >= self.HIGH and signal.signal_alignment == "Diverging" and not signal.degraded:
            conflicts.append(
                f"Evidence is {evidence.evidence_band} but Signal Intelligence "
                f"is Diverging — the data is solid, but business reasoning "
                f"disagrees with the prediction's direction."
            )

        # Conflict 3 — Stability says Unstable, yet the model is highly
        # decisive. A genuinely unstable-but-confident prediction is
        # exactly the case an executive reader should not take at face
        # value.
        if stability.stability_band == "Unstable" and confidence.confidence_band in ("Very High", "High"):
            conflicts.append(
                f"Stability is Unstable despite {confidence.confidence_band} "
                f"model confidence — the certainty is not well-founded."
            )

        # Conflict 4 — everything upstream looks fine, but Stability
        # still landed low (e.g. a borderline signal adjustment pushed
        # it down) — worth surfacing even without a crisp pairwise
        # conflict above.
        if (not conflicts) and stability.stability_band != "Stable" and evidence.evidence_strength >= self.HIGH:
            conflicts.append(
                f"Evidence is {evidence.evidence_band} but Stability only "
                f"reached '{stability.stability_band}' — a softer, less "
                f"obvious tension worth a second look."
            )

        # Score: start from full consistency, subtract per conflict,
        # floor at 0. Kept simple and legible rather than a weighted
        # formula — this axis is fundamentally about COUNTING
        # disagreements, not blending continuous values.
        penalty_per_conflict = 0.28
        consistency_score = round(max(0.0, 1.0 - penalty_per_conflict * len(conflicts)), 4)

        return ConsistencyResult(
            consistency_score=consistency_score,
            consistency_band=_band_for(consistency_score),
            conflicts=tuple(conflicts),
        )
