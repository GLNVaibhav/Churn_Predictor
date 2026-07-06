"""
universal_churn/prediction_intelligence/report.py
══════════════════════════════════════════════════════════════════════
Prediction Intelligence Report — the final deliverable.

PredictionIntelligenceReport bundles every engine's result for ONE
prediction, plus the degradation notice the integration contract
requires ("if [ReasoningReport/PredictionExplanation] is absent...
record this in the Prediction Intelligence Report"). This module also
owns the only human-readable text formatting in this package, in the
same visual style already established by coverage.py / quality_gate.py
/ routing.py / concept_confidence.py / business_reasoning_report.py's
printers — a bordered section header, plain-English lines, no jargon
beyond what's already been named.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .interfaces import PredictionIntelligenceContext
from .engines.prediction_confidence import PredictionConfidenceResult
from .engines.evidence_engine import EvidenceResult
from .engines.signal_intelligence import SignalIntelligenceResult
from .engines.stability_engine import StabilityResult
from .engines.consistency_engine import ConsistencyResult
from .engines.intelligence_score_engine import IntelligenceScoreResult


@dataclass(frozen=True)
class PredictionIntelligenceReport:
    customer_id: str
    sector: str
    generated_at: str

    prediction_confidence: PredictionConfidenceResult
    evidence: EvidenceResult
    signal: SignalIntelligenceResult
    stability: StabilityResult
    consistency: ConsistencyResult
    intelligence_score: IntelligenceScoreResult

    degraded_inputs: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            'customer_id': self.customer_id,
            'sector': self.sector,
            'generated_at': self.generated_at,
            'prediction_confidence': self.prediction_confidence.to_dict(),
            'evidence': self.evidence.to_dict(),
            'signal': self.signal.to_dict(),
            'stability': self.stability.to_dict(),
            'consistency': self.consistency.to_dict(),
            'intelligence_score': self.intelligence_score.to_dict(),
            'degraded_inputs': list(self.degraded_inputs),
        }

    def report_fields(self) -> dict:
        """
        Flat Title_Case fields, mirroring routing.RoutingDecision.
        report_fields()'s convention — suitable for attaching to a
        results DataFrame the same way Explanation_* / Decision_*
        columns already are elsewhere (see
        prediction_explanation_report.py / decision_report.py), should
        a future caller choose to. Not attached automatically by this
        package — Prediction Intelligence stays opt-in, per the
        non-interference guarantee.
        """
        return {
            'PIE_Intelligence_Score': f"{self.intelligence_score.intelligence_score*100:.1f}%",
            'PIE_Intelligence_Band': self.intelligence_score.intelligence_band,
            'PIE_Prediction_Confidence_Band': self.prediction_confidence.confidence_band,
            'PIE_Evidence_Band': self.evidence.evidence_band,
            'PIE_Signal_Alignment': self.signal.signal_alignment,
            'PIE_Stability_Band': self.stability.stability_band,
            'PIE_Consistency_Band': self.consistency.consistency_band,
            'PIE_Degraded_Inputs': '; '.join(self.degraded_inputs) if self.degraded_inputs else '',
        }


def build_report(
    context: PredictionIntelligenceContext,
    prediction_confidence: PredictionConfidenceResult,
    evidence: EvidenceResult,
    signal: SignalIntelligenceResult,
    stability: StabilityResult,
    consistency: ConsistencyResult,
    intelligence_score: IntelligenceScoreResult,
) -> PredictionIntelligenceReport:
    return PredictionIntelligenceReport(
        customer_id=context.customer_id,
        sector=context.sector,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        prediction_confidence=prediction_confidence,
        evidence=evidence,
        signal=signal,
        stability=stability,
        consistency=consistency,
        intelligence_score=intelligence_score,
        degraded_inputs=context.degraded_inputs(),
    )


# ══════════════════════════════════════════════════════════════════
# HUMAN-READABLE FORMATTING
# ══════════════════════════════════════════════════════════════════

def generate_prediction_intelligence_text(report: PredictionIntelligenceReport) -> str:
    sep = '─' * 60
    s = report.intelligence_score
    lines = [sep, f"  PREDICTION INTELLIGENCE REPORT  [{report.sector.upper()}]", sep]
    lines.append(f"  Customer                 : {report.customer_id}")
    lines.append(f"  Generated                : {report.generated_at}")
    lines.append("")
    lines.append(f"  Intelligence Score       : {s.intelligence_score*100:5.1f}%  ({s.intelligence_band})")
    lines.append(f"    {s.headline}")
    lines.append("")
    lines.append("  Module Breakdown")
    pc, ev, sg, st, co = (
        report.prediction_confidence, report.evidence, report.signal,
        report.stability, report.consistency,
    )
    lines.append(f"    1. Prediction Confidence : {pc.confidence_band:<18} (decisiveness {pc.decisiveness*100:.0f}%)")
    lines.append(f"    2. Evidence Engine       : {ev.evidence_band:<18} (strength {ev.evidence_strength*100:.0f}%)")
    lines.append(f"    3. Signal Intelligence   : {sg.signal_alignment:<18} "
                 f"({'no reasoning supplied' if sg.degraded else str(sg.findings_count) + ' finding(s)'})")
    lines.append(f"    4. Stability Engine      : {st.stability_band:<18} (gap {st.confidence_evidence_gap:+.2f})")
    lines.append(f"    5. Consistency Engine    : {co.consistency_band:<18} ({len(co.conflicts)} conflict(s))")

    if st.overconfidence_flag:
        lines.append("")
        lines.append("  ⚠ Overconfidence flag: model decisiveness outruns its evidence.")

    if co.conflicts:
        lines.append("")
        lines.append("  Flagged conflicts")
        for c in co.conflicts:
            lines.append(f"    ⚠ {c}")

    if report.degraded_inputs:
        lines.append("")
        lines.append("  Reduced richness (inputs unavailable for this prediction)")
        for name in report.degraded_inputs:
            lines.append(f"    · {name}")

    lines.append(sep)
    return "\n".join(lines)


def print_prediction_intelligence_report(report: PredictionIntelligenceReport) -> None:
    print(generate_prediction_intelligence_text(report))
