"""
backend.contracts.analysis_response
══════════════════════════════════════════════════════════════════════
``UniversalAnalysisResponse`` — the ONE canonical public response
contract every future consumer (FastAPI, frontend, CLI, AI agents,
SDKs, external integrations) receives.

Design rules
------------
    1. This is the ONLY object a future API layer exposes. Nothing
       downstream of this contract should need to reach back into
       ``universal_churn`` internals — every value a consumer could
       need is already here, in a stable shape.
    2. Every section is a plain, strongly-typed dataclass. Dataclasses
       are preferred over Pydantic per the sprint brief ("prefer
       dataclasses for now unless a compelling reason exists") — this
       package has no request-validation surface yet (that arrives
       with FastAPI in Sprint 2, at which point a thin Pydantic
       adapter can wrap these dataclasses without changing them).
    3. Every section is OPTIONAL at the type level. A given run may
       not have reached every stage (e.g. a refused prediction has no
       ``prediction`` section; a run without ``--explain`` has no
       ``prediction_explanation``). Missing sections are represented
       as ``None``, never fabricated.
    4. Nothing here computes anything. Every field is populated by
       ``backend.mappers.framework_mapper.FrameworkMapper`` from
       values the framework already produced.

Section overview
-----------------
    execution              — run identity/timing (backend-owned)
    dataset                 — what was analyzed (backend + framework)
    pipeline                 — stage-by-stage diagnostics
    coverage                  — typed coverage assessment adapted for API consumers
    concept_confidence       — business concept confidence derived from coverage
    quality                   — quality_gate.py's measurement
    routing                   — routing.py's decision
    prediction                — the prediction itself (dataset-level roll-up)
    prediction_explanation    — prediction_explanation.py's narrative
    decision                   — decision_intelligence.py's assessment
    reports                    — pre-rendered human-readable report text
    warnings                   — a flat, deduplicated warning list
    metadata                   — framework version stamps
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..utils import to_serializable
from .execution import ExecutionInfo
from .dataset import DatasetInfo
from .pipeline import PipelineSummary
from .metadata import FrameworkMetadata


# ══════════════════════════════════════════════════════════════════
# COVERAGE
# ══════════════════════════════════════════════════════════════════

@dataclass
class CoverageSummary:
    """API coverage contract adapted from the typed UCIF CoverageResult."""
    coverage_score: float
    status: str
    coverage_band: str
    missing_critical: List[str] = field(default_factory=list)
    missing_high_impact: List[str] = field(default_factory=list)
    missing_all: List[str] = field(default_factory=list)
    recovered_features: List[str] = field(default_factory=list)
    semantic_matches: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return to_serializable(self)

    @classmethod
    def from_dict(cls, d: dict) -> "CoverageSummary":
        return cls(
            coverage_score=d.get("coverage_score", 0.0),
            status=d.get("status", "Unknown"),
            coverage_band=d.get("coverage_band", d.get("status", "Unknown")),
            missing_critical=list(d.get("missing_critical", [])),
            missing_high_impact=list(d.get("missing_high_impact", [])),
            missing_all=list(d.get("missing_all", [])),
            recovered_features=list(d.get("recovered_features", [])),
            semantic_matches=list(d.get("semantic_matches", [])),
        )


# ══════════════════════════════════════════════════════════════════
# CONCEPT CONFIDENCE
# ══════════════════════════════════════════════════════════════════

@dataclass
class ConceptConfidenceSummary:
    """Business concept confidence embedded in the API coverage contract."""
    sector: str = ""
    overall_confidence: float = 0.0
    reconstructable_concepts: int = 0
    total_concepts: int = 0
    concepts_reconstructable: bool = False
    per_concept: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return to_serializable(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ConceptConfidenceSummary":
        return cls(
            sector=d.get("sector", ""),
            overall_confidence=d.get("overall_confidence", 0.0),
            reconstructable_concepts=d.get("reconstructable_concepts", 0),
            total_concepts=d.get("total_concepts", 0),
            concepts_reconstructable=d.get("concepts_reconstructable", False),
            per_concept=dict(d.get("per_concept", {})),
        )


# ══════════════════════════════════════════════════════════════════
# QUALITY
# ══════════════════════════════════════════════════════════════════

@dataclass
class QualitySummary:
    """Mirrors ``quality_gate.run_quality_gate()``'s return dict."""
    overall_passed: bool = True
    leakage_detected: bool = False
    leakage_flagged: List[str] = field(default_factory=list)
    leakage_warned: List[str] = field(default_factory=list)
    failed_columns: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return to_serializable(self)

    @classmethod
    def from_dict(cls, d: dict) -> "QualitySummary":
        return cls(
            overall_passed=d.get("overall_passed", True),
            leakage_detected=d.get("leakage_detected", False),
            leakage_flagged=list(d.get("leakage_flagged", [])),
            leakage_warned=list(d.get("leakage_warned", [])),
            failed_columns=list(d.get("failed_columns", [])),
        )


# ══════════════════════════════════════════════════════════════════
# ROUTING
# ══════════════════════════════════════════════════════════════════

@dataclass
class RoutingSummary:
    """Mirrors ``routing.RoutingDecision``."""
    selected_model: str = "UNKNOWN"
    selected_pipeline: str = ""
    prediction_mode: str = ""
    routing_reason: str = ""
    coverage_score: float = 0.0
    coverage_band: str = "Unknown"
    quality_score: float = 0.0
    quality_status: str = "Unknown"
    concept_confidence: Optional[float] = None
    reliability: str = "Unknown"
    model_artifact: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return to_serializable(self)

    @classmethod
    def from_dict(cls, d: dict) -> "RoutingSummary":
        return cls(
            selected_model=d.get("selected_model", "UNKNOWN"),
            selected_pipeline=d.get("selected_pipeline", ""),
            prediction_mode=d.get("prediction_mode", ""),
            routing_reason=d.get("routing_reason", ""),
            coverage_score=d.get("coverage_score", 0.0),
            coverage_band=d.get("coverage_band", "Unknown"),
            quality_score=d.get("quality_score", 0.0),
            quality_status=d.get("quality_status", "Unknown"),
            concept_confidence=d.get("concept_confidence"),
            reliability=d.get("reliability", "Unknown"),
            model_artifact=d.get("model_artifact"),
            warnings=list(d.get("warnings", [])),
        )


# ══════════════════════════════════════════════════════════════════
# PREDICTION
# ══════════════════════════════════════════════════════════════════

@dataclass
class PredictionSummary:
    """
    Dataset-level roll-up of a prediction run (the ``results``
    DataFrame every ``sector_pipeline.py`` / ``universal_pipeline.py``
    call already produces). Per-row detail is intentionally NOT
    inlined here — a future API endpoint can page/stream individual
    rows separately; this section answers "what happened, in
    aggregate" for the run as a whole.
    """
    rows: int = 0
    predicted_churners: int = 0
    average_probability: float = 0.0
    risk_distribution: Dict[str, int] = field(default_factory=dict)
    prediction_model: Optional[str] = None
    prediction_mode: Optional[str] = None

    def to_dict(self) -> dict:
        return to_serializable(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PredictionSummary":
        return cls(
            rows=d.get("rows", 0),
            predicted_churners=d.get("predicted_churners", 0),
            average_probability=d.get("average_probability", 0.0),
            risk_distribution=dict(d.get("risk_distribution", {})),
            prediction_model=d.get("prediction_model"),
            prediction_mode=d.get("prediction_mode"),
        )


# ══════════════════════════════════════════════════════════════════
# PREDICTION EXPLANATION
# ══════════════════════════════════════════════════════════════════

@dataclass
class PredictionExplanationSummary:
    """Mirrors ``prediction_explanation.PredictionExplanationReport``'s
    dataset-level narrative + roll-up."""
    headline: Optional[str] = None
    reason_text: Optional[str] = None
    recommendation_text: Optional[str] = None
    overall_business_health: Optional[str] = None
    overall_customer_risk: Optional[str] = None
    dominant_findings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return to_serializable(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PredictionExplanationSummary":
        return cls(
            headline=d.get("headline"),
            reason_text=d.get("reason_text"),
            recommendation_text=d.get("recommendation_text"),
            overall_business_health=d.get("overall_business_health"),
            overall_customer_risk=d.get("overall_customer_risk"),
            dominant_findings=list(d.get("dominant_findings", [])),
        )


# ══════════════════════════════════════════════════════════════════
# DECISION
# ══════════════════════════════════════════════════════════════════

@dataclass
class DecisionSummary:
    """Mirrors ``decision_intelligence.DecisionAssessment``."""
    decision_readiness: Optional[str] = None
    overall_confidence: Optional[float] = None
    business_confidence: Optional[float] = None
    technical_confidence: Optional[float] = None
    evidence_strength: Optional[float] = None
    risk_level: Optional[str] = None
    recommended_action: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return to_serializable(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DecisionSummary":
        return cls(
            decision_readiness=d.get("decision_readiness"),
            overall_confidence=d.get("overall_confidence"),
            business_confidence=d.get("business_confidence"),
            technical_confidence=d.get("technical_confidence"),
            evidence_strength=d.get("evidence_strength"),
            risk_level=d.get("risk_level"),
            recommended_action=d.get("recommended_action"),
            warnings=list(d.get("warnings", [])),
        )


# ══════════════════════════════════════════════════════════════════
# REPORTS (independent references)
# ══════════════════════════════════════════════════════════════════

@dataclass
class ReportReference:
    """
    Reference to an independently stored, human-readable report.
    """
    id: str
    type: str
    title: str
    created_at: str
    location: str

    def to_dict(self) -> dict:
        return to_serializable(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ReportReference":
        return cls(
            id=d.get("id", ""),
            type=d.get("type", ""),
            title=d.get("title", ""),
            created_at=d.get("created_at", ""),
            location=d.get("location", ""),
        )



# ══════════════════════════════════════════════════════════════════
# THE CANONICAL RESPONSE
# ══════════════════════════════════════════════════════════════════

@dataclass
class UniversalAnalysisResponse:
    """
    The canonical public contract. Every future consumer — FastAPI,
    frontend, CLI, AI agents, SDKs, external integrations — receives
    exactly this shape, unmodified by which consumer is asking.

    All sections beyond ``execution`` are optional: a run that
    refused prediction (routing's ``CRITICAL_UNRELIABLE``) still
    returns a valid response with ``coverage``/``quality``/``routing``
    populated and ``prediction``/``prediction_explanation``/``decision``
    left as ``None``.
    """
    execution: ExecutionInfo
    dataset: Optional[DatasetInfo] = None
    pipeline: Optional[PipelineSummary] = None

    coverage: Optional[CoverageSummary] = None
    concept_confidence: Optional[ConceptConfidenceSummary] = None
    quality: Optional[QualitySummary] = None
    routing: Optional[RoutingSummary] = None
    prediction: Optional[PredictionSummary] = None
    prediction_explanation: Optional[PredictionExplanationSummary] = None
    decision: Optional[DecisionSummary] = None
    reports: Optional[List[ReportReference]] = None

    warnings: List[str] = field(default_factory=list)
    metadata: Optional[FrameworkMetadata] = None

    # ── serialization ────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Full recursive dict form — safe to ``json.dumps()`` as-is."""
        return to_serializable(self)

    @classmethod
    def from_dict(cls, d: dict) -> "UniversalAnalysisResponse":
        """
        Reconstruct a ``UniversalAnalysisResponse`` from its
        ``to_dict()`` form (e.g. re-hydrating a persisted or
        transmitted response). Every optional section falls back to
        ``None`` rather than raising if absent, mirroring every other
        ``from_*_dict`` adapter already established in
        ``universal_churn`` (see ``routing.CoverageResult.from_coverage_dict``).
        """
        execution_dict = d.get("execution")
        if not execution_dict:
            raise ValueError(
                "UniversalAnalysisResponse.from_dict() requires an "
                "'execution' section — every response must carry run identity."
            )

        def _opt(section_cls, key):
            raw = d.get(key)
            return section_cls.from_dict(raw) if raw else None

        raw_reports = d.get("reports")
        reports_list = (
            [ReportReference.from_dict(r) for r in raw_reports]
            if isinstance(raw_reports, list) else None
        )

        return cls(
            execution=ExecutionInfo.from_dict(execution_dict),
            dataset=_opt(DatasetInfo, "dataset"),
            pipeline=_opt(PipelineSummary, "pipeline"),
            coverage=_opt(CoverageSummary, "coverage"),
            concept_confidence=_opt(ConceptConfidenceSummary, "concept_confidence"),
            quality=_opt(QualitySummary, "quality"),
            routing=_opt(RoutingSummary, "routing"),
            prediction=_opt(PredictionSummary, "prediction"),
            prediction_explanation=_opt(PredictionExplanationSummary, "prediction_explanation"),
            decision=_opt(DecisionSummary, "decision"),
            reports=reports_list,
            warnings=list(d.get("warnings", [])),
            metadata=_opt(FrameworkMetadata, "metadata"),
        )
