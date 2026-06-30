"""
universal_churn.routing
=========================
The Routing Engine — the ONLY module responsible for deciding which
prediction model should be used for a given input.

This module is a PURE DECISION ENGINE:
    - It reads CoverageResult, QualityResult, the user-requested mode,
      and the detected sector.
    - It returns a RoutingDecision.
    - It does NOT compute features, fit models, recover data, or call
      predict(). It does not touch the DataFrame at all.

sector_pipeline.py and universal_pipeline.py (and the future
core_pipeline.py) are expected to call route() once, then execute
whatever RoutingDecision.selected_model says — they no longer decide
this themselves.

Adapters
--------
compute_coverage_score() (coverage.py) and run_quality_gate()
(quality_gate.py) both currently return plain dicts — that is their
existing, unmodified public interface. CoverageResult and
QualityResult below are typed adapter dataclasses constructed FROM
those dicts via from_coverage_dict() / from_quality_dict(). Neither
coverage.py nor quality_gate.py is changed by this module.

Concept-layer fields (mapped_concepts, recovered_features,
concept_confidence) are part of the target CoverageResult shape per
the architecture spec, but the current coverage.py does not produce
this data (concept mapping doesn't exist yet; feature recovery is a
separate step that happens in sector_pipeline.py, outside coverage
scoring). These fields are left as None / empty here rather than
fabricated — they will be populated once a Business Concept Layer
exists upstream of coverage.py.

Quality status bands
---------------------
quality_gate.py exposes only a binary 'overall_passed' (True unless a
hard leakage flag exists) plus per-column failure lists — it does not
grade quality into bands. QualityResult.status below derives a simple
GOOD / WARN / FAIL band from that existing output:
    FAIL  — leakage_detected is True (hard block, regardless of mode)
    WARN  — no leakage, but >=1 column failed null/variance checks,
            or a leakage_warned (elevated-but-not-flagged) column exists
    GOOD  — no leakage, no failed columns, no elevated-correlation warns
This derivation lives entirely in the adapter; quality_gate.py itself
is untouched.

Feature recovery
-----------------
attempt_feature_recovery() (coverage.py) is NOT called from this
module. Recovery is a feature-engineering concern that happens upstream,
before route() is invoked — see sector_pipeline.py's predict() flow,
which calls coverage scoring, then (if Yellow) feature recovery, then
re-scores coverage before calling route() with the final, post-recovery
CoverageResult. The router only ever sees a finished coverage result;
it never decides to attempt recovery and never mutates data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from .config import PIPELINE_VERSION, COVERAGE_ALGORITHM_VERSION


# ══════════════════════════════════════════════════════════════════
# MODEL TYPES
# ══════════════════════════════════════════════════════════════════

class ModelType(str, Enum):
    """
    Every model the router can select. CORE_MODEL is defined now so the
    routing policy and RoutingDecision interface are future-ready, even
    though no CoreModelPipeline exists yet — selecting it currently
    raises NotImplementedError at the execution boundary (see
    sector_pipeline.py / universal_pipeline.py dispatch), not inside
    the router itself.
    """
    FULL_SECTOR_MODEL  = "FULL_SECTOR_MODEL"
    CORE_MODEL         = "CORE_MODEL"          # future-ready, not yet implemented
    UNIVERSAL_MODEL    = "UNIVERSAL_MODEL"
    CRITICAL_UNRELIABLE = "CRITICAL_UNRELIABLE"  # reject — no model selected


class PredictionMode(str, Enum):
    """User-requested mode, mirrors the existing --mode CLI values."""
    SECTOR    = "sector"
    UNIVERSAL = "universal"
    AUTO      = "auto"


class ReliabilityLevel(str, Enum):
    """Coarse, human-facing reliability summary attached to every decision."""
    HIGH       = "High"
    MODERATE   = "Moderate"
    LOW        = "Low"
    UNRELIABLE = "Unreliable"


# ══════════════════════════════════════════════════════════════════
# ADAPTER DATACLASSES
# ══════════════════════════════════════════════════════════════════
# Typed views over the existing dict outputs of coverage.py and
# quality_gate.py. Constructed only via the from_*_dict() classmethods
# below — never built by hand elsewhere, so there is exactly one place
# that knows how to translate the legacy dict shape into a typed object.

@dataclass
class CoverageResult:
    coverage_score   : float
    status           : str              # 'Green' | 'Yellow' | 'Red'  (as returned by coverage.py)
    missing_critical : list[str]
    missing_high_impact: list[str]
    missing_all      : list[str]
    detail           : list[dict] = field(default_factory=list)

    # Concept-layer fields — intentionally optional/None until a
    # Business Concept Layer exists upstream of coverage.py. Do not
    # populate these with placeholder or fabricated values.
    mapped_concepts     : list[str] | None = None
    recovered_features   : list[str] | None = None
    concept_confidence   : float | None = None

    @classmethod
    def from_coverage_dict(cls, d: dict) -> "CoverageResult":
        """Adapt compute_coverage_score()'s return dict (coverage.py, unmodified)."""
        return cls(
            coverage_score       = d['coverage_score'],
            status               = d['status'],
            missing_critical     = d.get('missing_critical', []),
            missing_high_impact  = d.get('missing_high_impact', []),
            missing_all          = d.get('missing_all', []),
            detail               = d.get('detail', []),
            mapped_concepts      = None,
            recovered_features   = None,
            concept_confidence   = None,
        )


@dataclass
class QualityResult:
    quality_score     : float            # 1.0 if overall_passed else 0.0 (binary today; see status)
    status            : str              # 'GOOD' | 'WARN' | 'FAIL'  — derived, not from quality_gate.py
    overall_passed    : bool
    failed_checks     : list[str]        # non-leakage failures (null-rate / variance)
    warnings          : list[str]        # elevated-correlation (0.80–0.95) soft warnings
    leakage_detected  : bool
    leakage_flagged   : list[str] = field(default_factory=list)

    @classmethod
    def from_quality_dict(cls, d: dict) -> "QualityResult":
        """
        Adapt run_quality_gate()'s return dict (quality_gate.py, unmodified)
        into a routing-oriented GOOD/WARN/FAIL status.

        Derivation:
            FAIL — d['leakage_detected'] is True (a hard leakage flag exists)
            WARN — no leakage, but failed_columns (excluding leaked ones)
                   is non-empty, OR leakage_warned (elevated but not
                   flagged) is non-empty
            GOOD — none of the above
        """
        leakage_detected = d.get('leakage_detected', False)
        failed_columns   = d.get('failed_columns', [])
        leakage_flagged  = d.get('leakage_flagged', [])
        leakage_warned   = d.get('leakage_warned', [])

        non_leakage_failures = [c for c in failed_columns if c not in leakage_flagged]

        if leakage_detected:
            status, quality_score = 'FAIL', 0.0
        elif non_leakage_failures or leakage_warned:
            status, quality_score = 'WARN', 0.5
        else:
            status, quality_score = 'GOOD', 1.0

        warning_messages = [
            f"Elevated correlation with target ({c})" for c in leakage_warned
        ]

        return cls(
            quality_score    = quality_score,
            status           = status,
            overall_passed   = d.get('overall_passed', not leakage_detected),
            failed_checks    = non_leakage_failures,
            warnings         = warning_messages,
            leakage_detected = leakage_detected,
            leakage_flagged  = leakage_flagged,
        )


# ══════════════════════════════════════════════════════════════════
# ROUTING DECISION
# ══════════════════════════════════════════════════════════════════

@dataclass
class RoutingDecision:
    """
    The single typed object the router returns. Every prediction
    pipeline (sector_pipeline.py, universal_pipeline.py, future
    core_pipeline.py) consumes exactly this object and does not make
    any further routing choices of its own.
    """
    selected_model     : ModelType
    selected_pipeline   : str            # human-readable / dispatch key, e.g. "SectorPipeline:healthcare"
    prediction_mode      : PredictionMode
    routing_reason       : str
    coverage_score       : float
    quality_score        : float
    concept_confidence    : float | None
    reliability           : ReliabilityLevel
    warnings             : list[str] = field(default_factory=list)
    metadata             : dict = field(default_factory=dict)

    @property
    def is_rejected(self) -> bool:
        return self.selected_model == ModelType.CRITICAL_UNRELIABLE

    def report_fields(self) -> dict:
        """
        The exact set of fields reporting.py should surface in every
        prediction output, per the architecture spec:
            Selected Model, Routing Reason, Coverage Score, Quality
            Score, Prediction Reliability, Concept Confidence,
            Warnings, Pipeline Version, Model Version, Timestamp.
        ('Prediction Confidence' and 'Model Version' beyond pipeline
        version are attached downstream by reporting.py's existing
        attach_common_metadata(), which already owns per-row
        probability-based confidence and sector/universal model
        version stamping — this method does not duplicate that.)
        """
        return {
            'Selected_Model'        : self.selected_model.value,
            'Routing_Reason'        : self.routing_reason,
            'Coverage_Score'        : f"{self.coverage_score*100:.1f}%",
            'Quality_Score'         : f"{self.quality_score*100:.1f}%",
            'Prediction_Reliability': self.reliability.value,
            'Concept_Confidence'    : (
                f"{self.concept_confidence*100:.1f}%"
                if self.concept_confidence is not None else 'N/A'
            ),
            'Routing_Warnings'      : '; '.join(self.warnings) if self.warnings else '',
            'Pipeline_Version'      : PIPELINE_VERSION,
            'Coverage_Algorithm_Version': COVERAGE_ALGORITHM_VERSION,
            'Routing_Timestamp'     : datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        }


# ══════════════════════════════════════════════════════════════════
# RELIABILITY DERIVATION
# ══════════════════════════════════════════════════════════════════

def _derive_reliability(
    selected_model: ModelType,
    coverage: CoverageResult,
    quality: QualityResult,
) -> ReliabilityLevel:
    """
    Coarse reliability summary combining coverage band, quality band,
    and which model was actually selected. Quality FAIL always forces
    UNRELIABLE regardless of coverage, since a quality gate failure
    means the router rejected the prediction outright.
    """
    if selected_model == ModelType.CRITICAL_UNRELIABLE or quality.status == 'FAIL':
        return ReliabilityLevel.UNRELIABLE

    if selected_model == ModelType.FULL_SECTOR_MODEL:
        if coverage.status == 'Green' and quality.status == 'GOOD':
            return ReliabilityLevel.HIGH
        return ReliabilityLevel.MODERATE  # Green coverage but WARN quality, etc.

    if selected_model == ModelType.UNIVERSAL_MODEL:
        if quality.status == 'WARN' or coverage.status == 'Red':
            return ReliabilityLevel.LOW
        return ReliabilityLevel.MODERATE

    if selected_model == ModelType.CORE_MODEL:
        return ReliabilityLevel.MODERATE  # placeholder until Core Model exists

    return ReliabilityLevel.LOW


# ══════════════════════════════════════════════════════════════════
# ROUTING POLICY
# ══════════════════════════════════════════════════════════════════

def route(
    mode: str | PredictionMode,
    coverage: "CoverageResult | dict",
    quality: "QualityResult | dict",
    sector: str,
) -> RoutingDecision:
    """
    The single deterministic routing policy. Accepts either the typed
    adapter dataclasses directly, or the raw dicts returned by
    compute_coverage_score() / run_quality_gate() (auto-adapted here
    for caller convenience — callers are not required to construct the
    adapters themselves).

    Policy (evaluated in this order):

      1. Quality FAIL (leakage detected) → CRITICAL_UNRELIABLE, always,
         regardless of mode or coverage. A leaked feature makes the
         prediction meaningless no matter how complete the schema is.

      2. mode == 'universal' → UNIVERSAL_MODEL, always (explicit user
         request; coverage/quality still computed and attached as
         warnings/reliability, but do not change WHICH model runs).

      3. mode == 'sector':
           Coverage Green or Yellow → FULL_SECTOR_MODEL
               (Yellow still uses the sector model per spec — "Still
               use Sector Model but attach a reliability warning" —
               note: by the time route() is called, sector_pipeline.py
               has already attempted feature recovery on Yellow inputs;
               if recovery did not lift coverage to Green, the sector
               model is still used here per this explicit mode request,
               with a reliability warning attached.)
           Coverage Red → CRITICAL_UNRELIABLE (sector model coverage
               too low to trust even with an explicit sector request)

      4. mode == 'auto':
           Coverage Green  → FULL_SECTOR_MODEL
           Coverage Yellow → UNIVERSAL_MODEL (Core Model hook below)
           Coverage Red    → CRITICAL_UNRELIABLE

    The CORE_MODEL hook: per spec, "Core Model hook should exist but
    can remain disabled until implemented." The hook point is the
    auto-mode Yellow branch — once a real core model exists, routing
    there can be changed from UNIVERSAL_MODEL to CORE_MODEL without
    touching any other branch of this policy.
    """
    if isinstance(mode, str):
        mode = PredictionMode(mode)
    if isinstance(coverage, dict):
        coverage = CoverageResult.from_coverage_dict(coverage)
    if isinstance(quality, dict):
        quality = QualityResult.from_quality_dict(quality)

    warnings: list[str] = list(quality.warnings)

    # ── 1. Quality gate is the hard, mode-independent block ────────
    if quality.status == 'FAIL':
        decision = RoutingDecision(
            selected_model      = ModelType.CRITICAL_UNRELIABLE,
            selected_pipeline   = "none",
            prediction_mode      = mode,
            routing_reason       = (
                f"Quality gate FAILED — target leakage detected in: "
                f"{quality.leakage_flagged}. Prediction refused regardless "
                f"of coverage or requested mode."
            ),
            coverage_score        = coverage.coverage_score,
            quality_score         = quality.quality_score,
            concept_confidence    = coverage.concept_confidence,
            reliability            = ReliabilityLevel.UNRELIABLE,
            warnings                = warnings + [
                f"LEAKAGE: {c}" for c in quality.leakage_flagged
            ],
            metadata                = {'sector': sector, 'leakage_columns': quality.leakage_flagged},
        )
        return decision

    # ── 2. Explicit universal mode — always universal, no routing choice ──
    if mode == PredictionMode.UNIVERSAL:
        if quality.status == 'WARN':
            warnings.append("Data quality WARN — see failed_checks for detail.")
        decision = RoutingDecision(
            selected_model      = ModelType.UNIVERSAL_MODEL,
            selected_pipeline   = "UniversalPipeline",
            prediction_mode      = mode,
            routing_reason       = "User explicitly requested the universal model.",
            coverage_score        = coverage.coverage_score,
            quality_score         = quality.quality_score,
            concept_confidence    = coverage.concept_confidence,
            reliability            = _derive_reliability(ModelType.UNIVERSAL_MODEL, coverage, quality),
            warnings                = warnings,
            metadata                = {'sector': sector},
        )
        return decision

    # ── 3. Explicit sector mode ─────────────────────────────────────
    if mode == PredictionMode.SECTOR:
        if coverage.status == 'Red':
            decision = RoutingDecision(
                selected_model      = ModelType.CRITICAL_UNRELIABLE,
                selected_pipeline   = "none",
                prediction_mode      = mode,
                routing_reason       = (
                    f"Sector mode requested but coverage is Red "
                    f"({coverage.coverage_score*100:.1f}% < 60%). Missing "
                    f"critical features: {coverage.missing_critical}. "
                    f"Prediction refused — enrich the input and retry."
                ),
                coverage_score        = coverage.coverage_score,
                quality_score         = quality.quality_score,
                concept_confidence    = coverage.concept_confidence,
                reliability            = ReliabilityLevel.UNRELIABLE,
                warnings                = warnings,
                metadata                = {'sector': sector, 'missing_critical': coverage.missing_critical},
            )
            return decision

        # Green or Yellow — sector model either way, per spec
        if coverage.status == 'Yellow':
            warnings.append(
                f"Coverage is Yellow ({coverage.coverage_score*100:.1f}%) — "
                f"sector model used per explicit request, but reliability "
                f"is reduced. Missing high-impact features: "
                f"{coverage.missing_high_impact}"
            )
            reason = (
                "User explicitly requested the sector model. Coverage is "
                "Yellow (not ideal) but the explicit request is honored "
                "with a reliability warning attached, per routing policy."
            )
        else:
            reason = "User explicitly requested the sector model. Coverage is Green."

        decision = RoutingDecision(
            selected_model      = ModelType.FULL_SECTOR_MODEL,
            selected_pipeline   = f"SectorPipeline:{sector}",
            prediction_mode      = mode,
            routing_reason       = reason,
            coverage_score        = coverage.coverage_score,
            quality_score         = quality.quality_score,
            concept_confidence    = coverage.concept_confidence,
            reliability            = _derive_reliability(ModelType.FULL_SECTOR_MODEL, coverage, quality),
            warnings                = warnings,
            metadata                = {'sector': sector},
        )
        return decision

    # ── 4. Auto mode ─────────────────────────────────────────────
    if mode == PredictionMode.AUTO:
        if coverage.status == 'Red':
            decision = RoutingDecision(
                selected_model      = ModelType.CRITICAL_UNRELIABLE,
                selected_pipeline   = "none",
                prediction_mode      = mode,
                routing_reason       = (
                    f"Auto mode — coverage Red "
                    f"({coverage.coverage_score*100:.1f}% < 60%). Missing "
                    f"critical features: {coverage.missing_critical}. "
                    f"Prediction refused — enrich the input and retry."
                ),
                coverage_score        = coverage.coverage_score,
                quality_score         = quality.quality_score,
                concept_confidence    = coverage.concept_confidence,
                reliability            = ReliabilityLevel.UNRELIABLE,
                warnings                = warnings,
                metadata                = {'sector': sector, 'missing_critical': coverage.missing_critical},
            )
            return decision

        if coverage.status == 'Green':
            decision = RoutingDecision(
                selected_model      = ModelType.FULL_SECTOR_MODEL,
                selected_pipeline   = f"SectorPipeline:{sector}",
                prediction_mode      = mode,
                routing_reason       = (
                    f"Auto mode — coverage Green "
                    f"({coverage.coverage_score*100:.1f}% ≥ 85%). "
                    f"Sector model selected."
                ),
                coverage_score        = coverage.coverage_score,
                quality_score         = quality.quality_score,
                concept_confidence    = coverage.concept_confidence,
                reliability            = _derive_reliability(ModelType.FULL_SECTOR_MODEL, coverage, quality),
                warnings                = warnings,
                metadata                = {'sector': sector},
            )
            return decision

        # Yellow — CORE_MODEL hook point. Disabled until a real Core
        # Model pipeline exists; routes to UNIVERSAL_MODEL today.
        # To enable: change ModelType.UNIVERSAL_MODEL below to
        # ModelType.CORE_MODEL once core_pipeline.py is implemented,
        # and add a CORE_MODEL branch to the dispatch in
        # sector_pipeline.py / universal_pipeline.py.
        warnings.append(
            f"Coverage is Yellow ({coverage.coverage_score*100:.1f}%) — "
            f"routed to universal model. Missing high-impact features: "
            f"{coverage.missing_high_impact}"
        )
        decision = RoutingDecision(
            selected_model      = ModelType.UNIVERSAL_MODEL,  # CORE_MODEL hook — see comment above
            selected_pipeline   = "UniversalPipeline",
            prediction_mode      = mode,
            routing_reason       = (
                f"Auto mode — coverage Yellow "
                f"({coverage.coverage_score*100:.1f}%, between 60% and 85%). "
                f"Sector model coverage insufficient; routed to universal "
                f"model fallback. (Core Model hook: not yet implemented.)"
            ),
            coverage_score        = coverage.coverage_score,
            quality_score         = quality.quality_score,
            concept_confidence    = coverage.concept_confidence,
            reliability            = _derive_reliability(ModelType.UNIVERSAL_MODEL, coverage, quality),
            warnings                = warnings,
            metadata                = {'sector': sector, 'core_model_hook': 'disabled'},
        )
        return decision

    # Unreachable given PredictionMode is an exhaustive Enum, but kept
    # as an explicit guard rather than relying on falling off the end.
    raise ValueError(f"Unhandled prediction mode: {mode}")
