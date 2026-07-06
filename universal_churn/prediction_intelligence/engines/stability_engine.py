"""
universal_churn/prediction_intelligence/engines/stability_engine.py
══════════════════════════════════════════════════════════════════════
Module 4 — Stability Engine.

The first convergence point in the pipeline (see the architecture
diagram: Confidence, Evidence, and Signal all fan INTO Stability).
Answers: "would this prediction likely hold up, or is it standing on
thin ground?" — specifically, it looks for the one pattern that matters
most in practice: the model being VERY decisive (Module 1) about a row
that has WEAK evidence behind it (Module 2). That combination —
confident conclusions from an under-informed model — is the textbook
shape of an unstable, overconfident prediction, regardless of what
Signal Intelligence (Module 3) says.

Reads prior engine results, never raw context alone
--------------------------------------------------------
This is the first engine in the pipeline whose `requires` tuple is
non-empty — it depends on PredictionConfidenceResult and
EvidenceResult (Modules 1 and 2) having already run. Signal
Intelligence (Module 3) also factors in, but only as a secondary
adjustment — the core stability question is Confidence-vs-Evidence,
per the architecture's own framing of Stability as the point where the
three-way fan-out reconverges.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..interfaces import PredictionIntelligenceContext, PredictionIntelligenceEngine
from .prediction_confidence import PredictionConfidenceResult
from .evidence_engine import EvidenceResult
from .signal_intelligence import SignalIntelligenceResult


@dataclass(frozen=True)
class StabilityResult:
    stability_score: float          # in [0, 1]
    stability_band: str              # 'Stable' | 'Moderately Stable' | 'Unstable'
    confidence_evidence_gap: float   # decisiveness - evidence_strength, can be negative
    overconfidence_flag: bool        # True when decisiveness far outruns evidence
    signal_adjustment: float         # how much Module 3 nudged the raw score
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            'stability_score': self.stability_score,
            'stability_band': self.stability_band,
            'confidence_evidence_gap': self.confidence_evidence_gap,
            'overconfidence_flag': self.overconfidence_flag,
            'signal_adjustment': self.signal_adjustment,
            'notes': list(self.notes),
        }


def _band_for(score: float) -> str:
    if score >= 0.70:
        return "Stable"
    if score >= 0.40:
        return "Moderately Stable"
    return "Unstable"


class StabilityEngine(PredictionIntelligenceEngine[StabilityResult]):
    """Module 4. Requires Modules 1 (Confidence) and 2 (Evidence);
    reads Module 3 (Signal) as an optional secondary adjustment."""

    name = "stability_engine"
    requires: tuple[str, ...] = ("prediction_confidence", "evidence")

    #: Above this gap (decisiveness minus evidence_strength), the
    #: model is being noticeably more certain than its evidence
    #: justifies.
    OVERCONFIDENCE_THRESHOLD = 0.35

    def analyze(
        self,
        context: PredictionIntelligenceContext,
        **prior_results,
    ) -> StabilityResult:
        confidence: PredictionConfidenceResult = prior_results["prediction_confidence"]
        evidence: EvidenceResult = prior_results["evidence"]
        signal: SignalIntelligenceResult | None = prior_results.get("signal")

        gap = round(confidence.decisiveness - evidence.evidence_strength, 4)
        overconfidence_flag = gap >= self.OVERCONFIDENCE_THRESHOLD

        # Base stability: how well confidence and evidence agree,
        # penalized by how far apart they are (a big gap in EITHER
        # direction — confident-but-unsupported, or hesitant-despite-
        # strong-evidence — reduces stability).
        base = (confidence.decisiveness + evidence.evidence_strength) / 2
        gap_penalty = min(0.5, abs(gap) * 0.6)
        raw_score = max(0.0, base - gap_penalty)

        # Secondary adjustment from Signal Intelligence: a Diverging
        # signal nudges stability down further; an Aligned signal with
        # real strength nudges it back up. Kept small and explicit —
        # Stability's core question is Confidence-vs-Evidence, Signal
        # only refines it.
        signal_adjustment = 0.0
        notes = []
        if signal is not None and not signal.degraded:
            if signal.signal_alignment == "Diverging":
                signal_adjustment = -0.10
                notes.append("Business reasoning diverges from the model's "
                             "own decisiveness — treated as a stability drag.")
            elif signal.signal_alignment == "Aligned" and signal.signal_strength >= 0.5:
                signal_adjustment = 0.05
                notes.append("Business reasoning aligns with the prediction — "
                             "a small stability boost.")

        stability_score = round(max(0.0, min(1.0, raw_score + signal_adjustment)), 4)

        if overconfidence_flag:
            notes.append(
                f"Model decisiveness ({confidence.decisiveness*100:.0f}%) "
                f"substantially outruns evidence strength "
                f"({evidence.evidence_strength*100:.0f}%) — this looks like "
                f"an overconfident call on a thin input."
            )

        return StabilityResult(
            stability_score=stability_score,
            stability_band=_band_for(stability_score),
            confidence_evidence_gap=gap,
            overconfidence_flag=overconfidence_flag,
            signal_adjustment=signal_adjustment,
            notes=tuple(notes),
        )
