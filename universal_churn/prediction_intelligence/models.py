"""
universal_churn/prediction_intelligence/models.py
══════════════════════════════════════════════════════════════════════
Typed dataclasses for the Prediction Intelligence Engine (PIE).

Every dataclass here is frozen — a built context or result never
mutates. This mirrors routing.py's RoutingDecision / CoverageResult /
QualityResult convention: read-only value objects, constructed once,
carried through the pipeline by value.

Pure data + to_dict() only. No PIE reasoning logic lives here — that
belongs to engines/*.py. This module has zero knowledge of HOW a
score is computed, only what shape a score/result takes.

Type hints for framework objects (RoutingDecision, CoverageResult,
QualityResult, ReasoningReport, PredictionExplanation) are imported
only under TYPE_CHECKING. At runtime, PredictionIntelligenceContext
stores whatever object (typed or a plain dict) the caller/orchestrator
already adapted — this keeps the package import-light and consistent
with the "never hard-depend on ML/sector modules" rule, while still
giving IDEs/type-checkers full type information.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - import-time only, no runtime dependency
    from ..routing import RoutingDecision, CoverageResult, QualityResult
    from ..business_reasoning import ReasoningReport


# ══════════════════════════════════════════════════════════════════
# CONTEXT — the single object every engine reads from
# ══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PredictionIntelligenceContext:
    """
    Everything a PIE engine is allowed to see for one prediction row,
    plus the file-level (not per-row) framework context that row's
    prediction was produced under.

    Coverage, Concept Confidence, Quality, and Routing are computed
    ONCE per input file/batch by the existing framework (see
    sector_pipeline.py / universal_pipeline.py) — they do not vary
    row to row. Only predicted_churn / churn_probability / risk_level
    / customer_id are genuinely per-row. This dataclass intentionally
    keeps that distinction visible rather than flattening everything
    into one undifferentiated bag of fields.

    Required inputs (per the architecture contract) are typed as
    non-Optional where the contract calls them required; NOTE that
    `routing_decision` and `quality` are still typed as
    `| None` at the PYTHON level despite being "required" in the
    spec, because real framework call sites can genuinely produce
    `results.attrs['quality'] is None` (see universal_pipeline.py's
    docstring: "_quality = None — already evaluated by the caller's
    route() call") and `routing_decision` can be absent on some
    sector-mode call paths. PIE must degrade gracefully rather than
    raise in these cases, exactly as instructed — the type hint
    reflects that reality; degraded_inputs records when it happens.
    """
    sector: str
    customer_id: str | None
    predicted_churn: str            # 'Yes' | 'No'
    churn_probability: float        # 0..1
    risk_level: str

    coverage: "CoverageResult"                    # required
    concept_confidence: dict | None                # required by contract; dict form of
                                                     # ConceptConfidenceReport.to_dict()
    routing_decision: "RoutingDecision | None"     # required by contract; see docstring
    quality: "QualityResult | None"                # required by contract; see docstring

    # Optional, caller-supplied — absent when explanation/reasoning are
    # disabled for this run. PIE must never compute these itself (it
    # would need raw data to do so) and must never treat their absence
    # as an error.
    reasoning_report: "ReasoningReport | None" = None
    prediction_explanation: Any | None = None

    # Populated by PredictionIntelligenceOrchestrator.build_context() —
    # every optional/expected-but-missing input that was defaulted
    # gets one entry here, verbatim from constants.py's DEGRADED_*
    # codes, so the final report can say exactly what evidence was
    # reduced and why, per the "record this in the report" rule.
    degraded_inputs: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "sector": self.sector,
            "customer_id": self.customer_id,
            "predicted_churn": self.predicted_churn,
            "churn_probability": self.churn_probability,
            "risk_level": self.risk_level,
            "degraded_inputs": list(self.degraded_inputs),
        }


# ══════════════════════════════════════════════════════════════════
# MODULE 1 RESULT — Prediction Confidence Engine
# ══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PredictionConfidenceResult:
    """
    Output of engines.prediction_confidence.PredictionConfidenceEngine.

    Attributes
    ----------
    score : float
        0-100. "How much does the framework trust this prediction?"
    band : str
        One of constants.ALL_BANDS.
    components : dict[str, float]
        Each weighted component's RAW (pre-weight) 0-100 score, keyed
        by the same names as weights.PREDICTION_CONFIDENCE_WEIGHTS —
        e.g. {'coverage': 92.0, 'concept_confidence': 40.0, ...}.
        Exposed so a report/consumer can see WHICH signal drove the
        score, not just the final number.
    weighted_contributions : dict[str, float]
        Each component's contribution to the final score after its
        weight is applied (components[k] * weight[k]) — these sum to
        `score`. Useful for "what moved the needle" diagnostics
        without the reader having to re-multiply weights themselves.
    reasons : tuple[str, ...]
        Human-readable explanation lines, one per component plus any
        degradation notes — same "narrate, don't just number" pattern
        routing.py's `warnings` list and business_reasoning.py's
        `explanation` fields already use.
    """
    score: float
    band: str
    components: dict[str, float] = field(default_factory=dict)
    weighted_contributions: dict[str, float] = field(default_factory=dict)
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 2),
            "band": self.band,
            "components": {k: round(v, 2) for k, v in self.components.items()},
            "weighted_contributions": {
                k: round(v, 2) for k, v in self.weighted_contributions.items()
            },
            "reasons": list(self.reasons),
        }


# ══════════════════════════════════════════════════════════════════
# PREDICTION ASSURANCE RESULT
# ══════════════════════════════════════════════════════════════════
# Output of engines.prediction_assurance.PredictionAssuranceEngine.
#
# Distinct from PredictionConfidenceResult above by design, not a
# rename of it: the framework already has Concept Confidence and
# Coverage Confidence, and the prediction itself carries a probability
# — introducing a second, differently-scoped "confidence" number
# invites exactly the ambiguity the architecture contract calls out.
# Assurance answers a narrower, single question — "how strongly does
# the framework stand behind this prediction, after weighing every
# upstream layer?" — and is built to read as a short narrative
# (positive_factors / penalties / summary / warnings), not just a
# number, which PredictionConfidenceResult does not attempt.

@dataclass(frozen=True)
class PredictionAssuranceResult:
    """
    Attributes
    ----------
    assurance_score : float
        0-100. The single weighted Prediction Assurance number.
    assurance_band : str
        One of constants.ALL_BANDS — reuses the same five-band
        vocabulary every PIE engine shares (see constants.py).
    positive_factors : tuple[str, ...]
        One line per component whose raw score cleared
        constants.ASSURANCE_STRONG_SIGNAL_MIN — the specific reasons
        the framework trusts this prediction. Empty if nothing did.
    penalties : tuple[str, ...]
        One line per component whose raw score fell at/under
        constants.ASSURANCE_WEAK_SIGNAL_MAX — the specific reasons
        assurance was reduced. Empty if nothing did.
    summary : str
        One deterministic, template-assembled sentence (no LLM, no
        generative text — pure string formatting, same convention as
        prediction_explanation.py's narrative templates) combining the
        band, the strongest positive factor (if any), and the
        strongest penalty (if any).
    warnings : tuple[str, ...]
        Framework-level cautionary notes distinct from `penalties` —
        e.g. a hard Quality FAIL, a rejected routing decision, or a
        list of inputs that were unavailable and forced a neutral
        default (mirrors `context.degraded_inputs`, formatted as a
        single warning line here for the reader's convenience).
    metadata : dict
        Diagnostic detail: per-component raw scores, weighted
        contributions, the weight vector used, sector, and which
        optional inputs were degraded. Never used for scoring itself —
        purely for audit/debugging, same role coverage.py's `detail`
        list and routing.py's `metadata` dict already play.
    """
    assurance_score: float
    assurance_band: str
    positive_factors: tuple[str, ...] = field(default_factory=tuple)
    penalties: tuple[str, ...] = field(default_factory=tuple)
    summary: str = ""
    warnings: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "assurance_score": round(self.assurance_score, 2),
            "assurance_band": self.assurance_band,
            "positive_factors": list(self.positive_factors),
            "penalties": list(self.penalties),
            "summary": self.summary,
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PredictionAssuranceResult":
        """
        Reconstruct a PredictionAssuranceResult from its to_dict() form
        — e.g. when reloading a persisted PIE report from JSON. Missing
        keys fall back to safe defaults rather than raising, mirroring
        every other `from_*_dict` adapter already established in this
        codebase (routing.CoverageResult.from_coverage_dict(), etc.).
        """
        return cls(
            assurance_score=float(d.get("assurance_score", 0.0)),
            assurance_band=str(d.get("assurance_band", "")),
            positive_factors=tuple(d.get("positive_factors", ())),
            penalties=tuple(d.get("penalties", ())),
            summary=str(d.get("summary", "")),
            warnings=tuple(d.get("warnings", ())),
            metadata=dict(d.get("metadata", {})),
        )

    def pretty_print(self) -> None:
        """Print a self-contained, human-readable block. Uses the same
        bordered-section visual style as every other report printer in
        this codebase (coverage.py, quality_gate.py, routing.py, ...)."""
        print(self.to_text())

    def to_text(self) -> str:
        """String form of `pretty_print()` — split out so the exact
        rendered text is independently testable without capturing
        stdout."""
        sep = "─" * 60
        lines = [sep, "  PREDICTION ASSURANCE", sep]
        lines.append(f"  Assurance Score   : {self.assurance_score:.1f}/100")
        lines.append(f"  Assurance Band    : {self.assurance_band}")
        lines.append("")
        lines.append("  Positive Factors")
        if self.positive_factors:
            lines.extend(f"    + {f}" for f in self.positive_factors)
        else:
            lines.append("    None")
        lines.append("")
        lines.append("  Penalties")
        if self.penalties:
            lines.extend(f"    - {p}" for p in self.penalties)
        else:
            lines.append("    None")
        lines.append("")
        lines.append("  Summary")
        lines.append(f"    {self.summary}")
        if self.warnings:
            lines.append("")
            lines.append("  Warnings")
            for w in self.warnings:
                lines.append(f"    ⚠ {w}")
        lines.append(sep)
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
# FINAL REPORT — provisional shape, extended additively as later
# modules (Evidence Strength, Signal Intelligence, Stability,
# Consistency, Prediction Intelligence Score) are implemented.
# ══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PredictionIntelligenceReport:
    """
    The Prediction Intelligence deliverable for one prediction row.

    Fields for engines not yet implemented (Modules 2-6) default to
    `None` rather than being absent — this dataclass's shape is
    additive-only across the Version 8.2 build: adding a field with a
    default never breaks an existing caller that only reads
    `prediction_confidence`. This is the same non-breaking-extension
    discipline `CoverageResult` / `RoutingDecision` already follow
    elsewhere in this codebase (e.g. `concept_confidence` was added to
    `CoverageResult` as an optional field, not a breaking change).
    """
    sector: str
    customer_id: str | None
    predicted_churn: str
    churn_probability: float
    generated_at: str

    # Optional, not required: `None` unless the orchestrator was
    # configured to run PredictionConfidenceEngine (still the default
    # — see orchestrator.py). Widened from a required field to
    # `| None` so that an orchestrator configured with ONLY
    # PredictionAssuranceEngine (or a future engine) never has to
    # fabricate a PredictionConfidenceResult it never computed.
    prediction_confidence: PredictionConfidenceResult | None = None

    # Prediction Assurance — additive field. `None` unless the
    # orchestrator was configured to run PredictionAssuranceEngine
    # (see orchestrator.py). Kept separate from `prediction_confidence`
    # rather than replacing it, preserving backward compatibility with
    # every existing caller of this dataclass.
    prediction_assurance: PredictionAssuranceResult | None = None

    # Populated by future modules — intentionally `Any | None` until
    # each module defines its own frozen result dataclass here.
    evidence_strength: Any | None = None      # Module 2
    signal_intelligence: Any | None = None    # Module 3
    stability: Any | None = None               # Module 4
    consistency: Any | None = None             # Module 5
    intelligence_score: Any | None = None      # Module 6

    degraded_inputs: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "sector": self.sector,
            "customer_id": self.customer_id,
            "predicted_churn": self.predicted_churn,
            "churn_probability": self.churn_probability,
            "generated_at": self.generated_at,
            "prediction_confidence": (
                self.prediction_confidence.to_dict()
                if self.prediction_confidence is not None else None
            ),
            "prediction_assurance": (
                self.prediction_assurance.to_dict()
                if self.prediction_assurance is not None else None
            ),
            "evidence_strength": (
                self.evidence_strength.to_dict()
                if hasattr(self.evidence_strength, "to_dict") else self.evidence_strength
            ),
            "signal_intelligence": (
                self.signal_intelligence.to_dict()
                if hasattr(self.signal_intelligence, "to_dict") else self.signal_intelligence
            ),
            "stability": (
                self.stability.to_dict()
                if hasattr(self.stability, "to_dict") else self.stability
            ),
            "consistency": (
                self.consistency.to_dict()
                if hasattr(self.consistency, "to_dict") else self.consistency
            ),
            "intelligence_score": (
                self.intelligence_score.to_dict()
                if hasattr(self.intelligence_score, "to_dict") else self.intelligence_score
            ),
            "degraded_inputs": list(self.degraded_inputs),
        }