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
    """
    Coarse, human-facing reliability summary attached to every decision.

    This is Prediction Reliability, which is deliberately NOT the same
    thing as per-row model confidence (Churn_Probability /
    Prediction_Confidence, owned by reporting.py). Reliability answers
    "how much should you trust this prediction given what we know about
    the INPUT" (coverage + concept confidence + quality); confidence
    answers "how sure is the MODEL about this particular row's outcome."
    See _derive_reliability() for the scoring policy that produces one
    of these five levels.
    """
    VERY_HIGH  = "Very High"
    HIGH       = "High"
    MODERATE   = "Moderate"
    LOW        = "Low"
    VERY_LOW   = "Very Low"

    # Backward-compat alias — pre-Phase-5 code (and any cached reports)
    # referred to the bottom band as UNRELIABLE. Same enum member as
    # VERY_LOW, just reachable under the old name so `ReliabilityLevel.UNRELIABLE`
    # keeps working anywhere it's still referenced.
    UNRELIABLE = "Very Low"


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

    # Concept-layer fields. mapped_concepts / recovered_features remain
    # None/empty — nothing upstream populates them yet. concept_confidence
    # and concepts_reconstructable ARE now populated (Phase 4: the
    # Concept Confidence Engine, concept_confidence.py, wired into
    # coverage.py's return dict) whenever the input coverage dict
    # carries a 'concept_confidence' key. Older/cached coverage dicts
    # without that key simply leave these as None — fully backward
    # compatible, nothing fabricated.
    mapped_concepts     : list[str] | None = None
    recovered_features   : list[str] | None = None
    concept_confidence   : float | None = None
    concepts_reconstructable: bool | None = None

    @classmethod
    def from_coverage_dict(cls, d: dict) -> "CoverageResult":
        """Adapt compute_coverage_score()'s return dict (coverage.py, unmodified)."""
        concept_data = d.get('concept_confidence')
        return cls(
            coverage_score       = d['coverage_score'],
            status               = d['status'],
            missing_critical     = d.get('missing_critical', []),
            missing_high_impact  = d.get('missing_high_impact', []),
            missing_all          = d.get('missing_all', []),
            detail               = d.get('detail', []),
            mapped_concepts      = None,
            recovered_features   = None,
            concept_confidence   = (
                concept_data.get('overall_confidence') if concept_data else None
            ),
            concepts_reconstructable = (
                concept_data.get('concepts_reconstructable') if concept_data else None
            ),
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

    # Phase 5 diagnostic fields — populated by every route() branch.
    # These exist so reporting.py (and any CSV/JSON output) can surface
    # the underlying BAND labels, not just the raw scores, without
    # re-deriving them from coverage/quality dicts a second time.
    coverage_band        : str = "Unknown"     # 'Green' | 'Yellow' | 'Red' | 'Unknown'
    quality_status        : str = "Unknown"     # 'GOOD' | 'WARN' | 'FAIL' | 'Unknown'

    @property
    def is_rejected(self) -> bool:
        return self.selected_model == ModelType.CRITICAL_UNRELIABLE

    @property
    def model_artifact(self) -> str:
        """
        Human-readable identifier for whatever will actually be loaded
        to serve this prediction — distinct from `selected_pipeline`
        (a dispatch key) in that it's meant for the diagnostics/report
        surface, e.g. "sector:healthcare" or "universal" or "none".
        """
        if self.selected_model == ModelType.FULL_SECTOR_MODEL:
            return f"sector:{self.metadata.get('sector', 'unknown')}"
        if self.selected_model == ModelType.UNIVERSAL_MODEL:
            return "universal"
        if self.selected_model == ModelType.CORE_MODEL:
            return "core (not yet implemented)"
        return "none"

    @property
    def acceptance_banner(self) -> str:
        """
        The short terminal-facing verdict line, per Phase 5 item 6:
        'Prediction Accepted' / 'Prediction Accepted (Universal)' /
        'Prediction Rejected' — coverage.py never prints language like
        this; only routing.py (the decision authority) does.
        """
        if self.selected_model == ModelType.CRITICAL_UNRELIABLE:
            return "Prediction Rejected"
        if self.selected_model == ModelType.FULL_SECTOR_MODEL:
            return "Prediction Accepted (Sector)"
        if self.selected_model == ModelType.UNIVERSAL_MODEL:
            return "Prediction Accepted (Universal)"
        if self.selected_model == ModelType.CORE_MODEL:
            return "Prediction Accepted (Core)"
        return "Prediction Accepted"

    def report_fields(self) -> dict:
        """
        The exact set of fields reporting.py should surface in every
        prediction output, per the architecture spec:
            Selected Model, Routing Reason, Coverage Score, Coverage
            Band, Quality Status, Prediction Reliability, Concept
            Confidence, Warnings, Model Artifact, Pipeline Version,
            Timestamp.
        ('Prediction Confidence' and per-sector Model Version are
        attached downstream by reporting.py's existing
        attach_common_metadata(), which already owns per-row
        probability-based confidence and sector/universal model
        version stamping — this method does not duplicate that.)
        """
        return {
            'Selected_Model'        : self.selected_model.value,
            'Routing_Reason'        : self.routing_reason,
            'Coverage_Score'        : f"{self.coverage_score*100:.1f}%",
            'Coverage_Band'         : self.coverage_band,
            'Quality_Score'         : f"{self.quality_score*100:.1f}%",
            'Quality_Status'        : self.quality_status,
            'Prediction_Reliability': self.reliability.value,
            'Concept_Confidence'    : (
                f"{self.concept_confidence*100:.1f}%"
                if self.concept_confidence is not None else 'N/A'
            ),
            'Routing_Warnings'      : '; '.join(self.warnings) if self.warnings else '',
            'Model_Artifact'        : self.model_artifact,
            'Pipeline_Version'      : PIPELINE_VERSION,
            'Coverage_Algorithm_Version': COVERAGE_ALGORITHM_VERSION,
            'Routing_Timestamp'     : datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        }

    def to_diagnostics_dict(self) -> dict:
        """
        Compact machine-readable diagnostics payload, per Phase 5 item 5:
        selected_model, coverage_score, coverage_band, concept_confidence,
        quality_status, prediction_reliability, routing_reason, warnings,
        model_artifact, pipeline_version. Snake_case keys (unlike
        report_fields(), which uses the Title_Case column-naming
        convention already used across `results` DataFrames) — this is
        the shape meant for JSON diagnostics payloads, logs, or API
        responses rather than a CSV column.
        """
        return {
            'selected_model'        : self.selected_model.value,
            'coverage_score'        : self.coverage_score,
            'coverage_band'         : self.coverage_band,
            'concept_confidence'    : self.concept_confidence,
            'quality_status'        : self.quality_status,
            'prediction_reliability': self.reliability.value,
            'routing_reason'        : self.routing_reason,
            'warnings'              : list(self.warnings),
            'model_artifact'        : self.model_artifact,
            'pipeline_version'      : PIPELINE_VERSION,
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
    Prediction Reliability scoring policy (Phase 5, item 3).

    Reliability is a SEPARATE axis from per-row model confidence — it
    answers "how much should you trust this prediction given what we
    know about the input", derived from exactly three signals:
    Coverage, Concept Confidence, and the Quality Gate. It says nothing
    about any individual row's predicted probability.

    Hard override
    --------------
    Quality FAIL (leakage detected) or an outright CRITICAL_UNRELIABLE
    routing outcome always forces VERY_LOW — a quality-gate failure or
    a rejected prediction can never be "moderately reliable"; there is
    no prediction to be reliable about.

    Point-based scoring (only reached when not hard-overridden)
    -------------------------------------------------------------
    Three signals are each scored 0-2 and summed (max 6):

        Coverage band       Green = 2   Yellow = 1   Red = 0
        Quality status       GOOD = 2   WARN   = 1   (FAIL handled above)
        Concept confidence   >= 0.70 -> 2   >= 0.40 -> 1   else 0
                              (None / unavailable -> 1, i.e. neutral —
                              absence of concept-confidence data is not
                              treated as evidence of low reliability)

    Total -> level:
        5 – 6   Very High
        4       High
        2 – 3   Moderate
        1       Low
        0       Very Low

    Model-selection dampener
    --------------------------
    The universal model is a fallback by construction — even with a
    perfect point total, a UNIVERSAL_MODEL prediction is capped at
    High (never Very High), since it is, by definition, running
    without a full sector-specific feature set. CORE_MODEL is a
    future placeholder and always reports Moderate until a real
    implementation exists to score against.
    """
    if selected_model == ModelType.CRITICAL_UNRELIABLE or quality.status == 'FAIL':
        return ReliabilityLevel.VERY_LOW

    if selected_model == ModelType.CORE_MODEL:
        return ReliabilityLevel.MODERATE  # placeholder until Core Model exists

    coverage_pts = {'Green': 2, 'Yellow': 1, 'Red': 0}.get(coverage.status, 0)
    quality_pts  = {'GOOD': 2, 'WARN': 1}.get(quality.status, 0)

    if coverage.concept_confidence is None:
        concept_pts = 1
    elif coverage.concept_confidence >= 0.70:
        concept_pts = 2
    elif coverage.concept_confidence >= 0.40:
        concept_pts = 1
    else:
        concept_pts = 0

    total = coverage_pts + quality_pts + concept_pts

    if total >= 5:
        level = ReliabilityLevel.VERY_HIGH
    elif total == 4:
        level = ReliabilityLevel.HIGH
    elif total >= 2:
        level = ReliabilityLevel.MODERATE
    elif total == 1:
        level = ReliabilityLevel.LOW
    else:
        level = ReliabilityLevel.VERY_LOW

    if selected_model == ModelType.UNIVERSAL_MODEL and level == ReliabilityLevel.VERY_HIGH:
        level = ReliabilityLevel.HIGH  # fallback model is capped below Very High

    return level


def _red_coverage_decision(
    mode: PredictionMode,
    coverage: CoverageResult,
    quality: QualityResult,
    sector: str,
    warnings: list[str],
    requested_label: str,
) -> RoutingDecision:
    """
    Shared Red-coverage policy for both explicit 'sector' mode and
    'auto' mode (Phase 5 of the Schema Intelligence Layer).

    Old policy: Coverage Red -> CRITICAL_UNRELIABLE, always.

    New policy: low feature COUNT alone should not sink a prediction
    if the underlying Business Concepts can still be reconstructed
    from whatever columns the file does have (concept_confidence.py,
    wired into coverage.py's return dict). Reject only when:
        - the quality gate failed (handled earlier, before this is
          ever called), or
        - concepts_reconstructable is explicitly False/unknown, i.e.
          concept confidence data says the input can't even be
          translated into the framework's business vocabulary.

    If concept_confidence data is entirely absent (concepts_reconstructable
    is None — an older coverage dict that never ran the Concept
    Confidence Engine), this falls back to the original, strict
    reject-on-Red behavior. Nothing here changes what happens when
    concept confidence isn't available, so this is backward compatible.
    """
    if coverage.concepts_reconstructable:
        warnings = warnings + [
            f"Coverage is Red ({coverage.coverage_score*100:.1f}%) but "
            f"business concepts are still reconstructable "
            f"(concept confidence {coverage.concept_confidence*100:.1f}%) "
            f"— routed to the universal model instead of refusing outright."
        ]
        return RoutingDecision(
            selected_model      = ModelType.UNIVERSAL_MODEL,
            selected_pipeline   = "UniversalPipeline",
            prediction_mode      = mode,
            routing_reason       = (
                f"{requested_label} — coverage is Red "
                f"({coverage.coverage_score*100:.1f}% < 60%), but "
                f"business concepts remain reconstructable "
                f"(concept confidence {coverage.concept_confidence*100:.1f}%). "
                f"Missing critical features: {coverage.missing_critical}. "
                f"Routed to the universal model rather than refused, per "
                f"routing policy: reject only on quality failure or "
                f"unreconstructable concepts, not on feature count alone."
            ),
            coverage_score        = coverage.coverage_score,
            quality_score         = quality.quality_score,
            concept_confidence    = coverage.concept_confidence,
            reliability            = ReliabilityLevel.LOW,
            warnings                = warnings,
            metadata                = {
                'sector': sector, 'missing_critical': coverage.missing_critical,
                'concepts_reconstructable': True,
            },
            coverage_band          = coverage.status,
            quality_status          = quality.status,
        )

    reason_suffix = (
        "Business concepts could not be reconstructed from this input either "
        "(concept confidence engine found no usable mapping)."
        if coverage.concepts_reconstructable is False
        else "Concept confidence data unavailable for this input."
    )
    return RoutingDecision(
        selected_model      = ModelType.CRITICAL_UNRELIABLE,
        selected_pipeline   = "none",
        prediction_mode      = mode,
        routing_reason       = (
            f"{requested_label} — coverage is Red "
            f"({coverage.coverage_score*100:.1f}% < 60%). Missing critical "
            f"features: {coverage.missing_critical}. {reason_suffix} "
            f"Prediction refused — enrich the input and retry."
        ),
        coverage_score        = coverage.coverage_score,
        quality_score         = quality.quality_score,
        concept_confidence    = coverage.concept_confidence,
        reliability            = ReliabilityLevel.VERY_LOW,
        warnings                = warnings,
        metadata                = {
            'sector': sector, 'missing_critical': coverage.missing_critical,
            'concepts_reconstructable': coverage.concepts_reconstructable,
        },
        coverage_band          = coverage.status,
        quality_status          = quality.status,
    )


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
            reliability            = ReliabilityLevel.VERY_LOW,
            warnings                = warnings + [
                f"LEAKAGE: {c}" for c in quality.leakage_flagged
            ],
            metadata                = {'sector': sector, 'leakage_columns': quality.leakage_flagged},
            coverage_band          = coverage.status,
            quality_status          = quality.status,
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
            coverage_band          = coverage.status,
            quality_status          = quality.status,
        )
        return decision

    # ── 3. Explicit sector mode ─────────────────────────────────────
    if mode == PredictionMode.SECTOR:
        if coverage.status == 'Red':
            return _red_coverage_decision(
                mode, coverage, quality, sector, warnings,
                requested_label="Sector mode requested",
            )

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
            coverage_band          = coverage.status,
            quality_status          = quality.status,
        )
        return decision

    # ── 4. Auto mode ─────────────────────────────────────────────
    if mode == PredictionMode.AUTO:
        if coverage.status == 'Red':
            return _red_coverage_decision(
                mode, coverage, quality, sector, warnings,
                requested_label="Auto mode",
            )

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
                coverage_band          = coverage.status,
                quality_status          = quality.status,
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
            coverage_band          = coverage.status,
            quality_status          = quality.status,
        )
        return decision

    # Unreachable given PredictionMode is an exhaustive Enum, but kept
    # as an explicit guard rather than relying on falling off the end.
    raise ValueError(f"Unhandled prediction mode: {mode}")


# ══════════════════════════════════════════════════════════════════
# TERMINAL REPORTING — routing.py owns the accept/reject verdict
# ══════════════════════════════════════════════════════════════════
# Phase 5, item 6: decision-shaped language ("Prediction Refused", etc.)
# must never be printed by coverage.py. This is the one place that
# prints it, because this is the one place that decided it.

def print_routing_decision(decision: RoutingDecision) -> None:
    """
    Human-readable Routing Decision report, in the same visual style
    as coverage.py / quality_gate.py / concept_confidence.py's report
    printers. Intended to be called by reporting.py as the dedicated
    "Routing Decision" + "Prediction Reliability" section of the full
    diagnostic report — see reporting.py's print_full_diagnostic_report().
    """
    sep = '─' * 60
    print(f"\n{sep}")
    print(f"  ROUTING DECISION")
    print(sep)
    print(f"  Verdict                 : {decision.acceptance_banner}")
    print(f"  Selected model          : {decision.selected_model.value}")
    print(f"  Model artifact          : {decision.model_artifact}")
    print(f"  Coverage band           : {decision.coverage_band}  "
          f"({decision.coverage_score*100:.1f}%)")
    print(f"  Quality status          : {decision.quality_status}  "
          f"({decision.quality_score*100:.1f}%)")
    print(f"  Concept confidence      : "
          f"{f'{decision.concept_confidence*100:.1f}%' if decision.concept_confidence is not None else 'N/A'}")
    print(f"  Prediction reliability  : {decision.reliability.value}")
    print(f"\n  Reason:")
    print(f"    {decision.routing_reason}")
    if decision.warnings:
        print(f"\n  Warnings:")
        for w in decision.warnings:
            print(f"    ⚠ {w}")
    print(sep)
