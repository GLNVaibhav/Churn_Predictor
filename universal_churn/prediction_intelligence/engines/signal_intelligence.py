"""
universal_churn/prediction_intelligence/engines/signal_intelligence.py
══════════════════════════════════════════════════════════════════════
Module 3 — Signal Intelligence Engine.

Answers: "does independent business reasoning agree with what the
model predicted?" — reads `context.reasoning_report`
(business_reasoning.ReasoningReport) and, opportunistically,
`context.prediction_explanation`, both of which are OPTIONAL per the
integration contract. Some framework configurations disable business
reasoning entirely; this engine must degrade gracefully, not fail,
when that happens — it still returns a result, just one that reports
"No Signal" rather than an alignment verdict it has no basis for.

Alignment heuristic (documented, not hidden)
------------------------------------------------
business_reasoning.py's Knowledge Base findings are overwhelmingly
risk-indicating (Retention Risk, Dormant Customer, Service Recovery
Needed, etc.) — a few (e.g. Retention Strength) are explicitly
positive. Rather than hardcode a list of which finding_ids count as
"positive" here (which would silently break if rules.yaml adds a new
one), this engine uses the one signal every finding already carries
generically: severity. A HIGH/CRITICAL finding firing at all is
treated as "the business-reasoning layer sees elevated risk here" —
`signal_alignment` then simply asks whether the model's own predicted
label matches that direction. This is intentionally a coarse,
directionally-honest heuristic, not a claim of semantic understanding
— see `Reason` fields on the result for the exact logic applied to a
specific row.

Never reads raw data
-----------------------
`reasoning_report` and `prediction_explanation` are themselves
framework objects (produced by business_reasoning.py /
prediction_explanation.py from the raw dataset, upstream of and
outside Prediction Intelligence). This engine reads only their already
-computed fields (`.findings`, `.summary`) — it never touches a
DataFrame.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..interfaces import PredictionIntelligenceContext, PredictionIntelligenceEngine


_SEVERITY_RANK = {'LOW': 0, 'MEDIUM': 1, 'HIGH': 2, 'CRITICAL': 3}
_ELEVATED_SEVERITIES = {'HIGH', 'CRITICAL'}


@dataclass(frozen=True)
class SignalIntelligenceResult:
    findings_count: int
    dominant_finding: str | None
    dominant_severity: str | None
    signal_alignment: str          # 'Aligned' | 'Diverging' | 'Neutral' | 'No Signal'
    signal_strength: float          # in [0, 1] — 0 when no reasoning report at all
    degraded: bool                  # True if reasoning_report was unavailable
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            'findings_count': self.findings_count,
            'dominant_finding': self.dominant_finding,
            'dominant_severity': self.dominant_severity,
            'signal_alignment': self.signal_alignment,
            'signal_strength': self.signal_strength,
            'degraded': self.degraded,
            'notes': list(self.notes),
        }


class SignalIntelligenceEngine(PredictionIntelligenceEngine[SignalIntelligenceResult]):
    """Module 3. No upstream dependencies — same fan-out tier as
    Modules 1 and 2 (Confidence / Evidence / Signal each read only the
    shared context, per the architecture's explicit note that these
    three are logically independent of one another's output)."""

    name = "signal_intelligence"
    requires: tuple[str, ...] = ()

    def analyze(
        self,
        context: PredictionIntelligenceContext,
        **prior_results,
    ) -> SignalIntelligenceResult:
        report = context.reasoning_report

        if report is None:
            return SignalIntelligenceResult(
                findings_count=0,
                dominant_finding=None,
                dominant_severity=None,
                signal_alignment="No Signal",
                signal_strength=0.0,
                degraded=True,
                notes=("Business reasoning was not supplied for this "
                       "prediction — Signal Intelligence has no basis "
                       "to confirm or contradict the model's output.",),
            )

        findings = list(report.findings)
        if not findings:
            return SignalIntelligenceResult(
                findings_count=0,
                dominant_finding=None,
                dominant_severity=None,
                signal_alignment=(
                    "Aligned" if context.predicted_churn == 'No' else "Neutral"
                ),
                signal_strength=0.3,
                degraded=False,
                notes=("No business-reasoning rule fired for this input — "
                       "absence of a finding is treated as mild, not "
                       "strong, supporting signal.",),
            )

        dominant = max(findings, key=lambda f: _SEVERITY_RANK.get(f.severity.value, 0))
        elevated = dominant.severity.value in _ELEVATED_SEVERITIES

        if elevated and context.predicted_churn == 'Yes':
            alignment = "Aligned"
        elif (not elevated) and context.predicted_churn == 'No':
            alignment = "Aligned"
        else:
            alignment = "Diverging"

        # Strength scales with the dominant finding's own confidence
        # (business_reasoning.py already floors this at
        # MIN_FINDING_CONFIDENCE) and how many findings corroborate it.
        corroboration_bonus = min(0.15, 0.05 * (len(findings) - 1))
        signal_strength = round(min(1.0, dominant.confidence + corroboration_bonus), 4)

        notes = []
        if alignment == "Diverging":
            notes.append(
                f"'{dominant.title}' ({dominant.severity.value}) fired, but the "
                f"model predicted '{context.predicted_churn}' — the business "
                f"reasoning and the model tell different stories here."
            )

        return SignalIntelligenceResult(
            findings_count=len(findings),
            dominant_finding=dominant.title,
            dominant_severity=dominant.severity.value,
            signal_alignment=alignment,
            signal_strength=signal_strength,
            degraded=False,
            notes=tuple(notes),
        )
