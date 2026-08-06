from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from .identifiers import ArtifactVersionSet, DatasetFingerprint, OntologyId
from .enums import AbstentionStatus, EvidenceFamily, ResolutionStatus, Severity, ValidationOutcome


@dataclass(frozen=True)
class SamplingPolicy:
    mode: str = "deterministic_sample"
    max_rows: int = 10_000
    seed: int = 17
    source_pushdown: bool = True


@dataclass(frozen=True)
class ProfileProvenance:
    mode: str
    sampled_rows: int
    total_rows: int
    timestamp_utc: str
    cache_hit: bool = False


@dataclass(frozen=True)
class DatatypeProfile:
    source_dtype: str
    logical_type: str
    confidence: float


@dataclass(frozen=True)
class DistributionProfile:
    minimum: float | None = None; maximum: float | None = None
    mean: float | None = None; median: float | None = None; std: float | None = None
    integer_ratio: float | None = None; zero_ratio: float | None = None


@dataclass(frozen=True)
class CardinalityProfile:
    distinct_count: int
    uniqueness_ratio: float
    approximate: bool = False


@dataclass(frozen=True)
class ColumnProfile:
    raw_column: str
    position: int
    datatype: DatatypeProfile
    cardinality: CardinalityProfile
    null_ratio: float
    distribution: DistributionProfile
    units: tuple[str, ...] = ()
    temporal_indicators: tuple[str, ...] = ()
    identifier_likelihood: float = 0.0
    representative_values: tuple[str, ...] = ()


@dataclass(frozen=True)
class DatasetProfile:
    fingerprint: DatasetFingerprint
    row_count: int
    column_count: int
    candidate_grain: str
    candidate_sectors: tuple[tuple[OntologyId, float], ...]
    provenance: ProfileProvenance


@dataclass(frozen=True)
class RelationshipProfile:
    left_column: str; right_column: str; relation: str; confidence: float; rationale: str


@dataclass(frozen=True)
class ProfilingResult:
    dataset: DatasetProfile
    columns: tuple[ColumnProfile, ...]
    relationships: tuple[RelationshipProfile, ...] = ()


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    family: EvidenceFamily
    target: OntologyId
    score: float
    polarity: int
    rationale: str
    source: str
    provenance: dict[str, Any] = field(default_factory=dict)
    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0: raise ValueError("Evidence score must be within [0, 1].")
        if self.polarity not in (-1, 1): raise ValueError("Evidence polarity must be -1 or 1.")


@dataclass(frozen=True)
class EvidenceBundle:
    items: tuple[EvidenceItem, ...] = ()
    def for_target(self, target: OntologyId) -> tuple[EvidenceItem, ...]:
        return tuple(item for item in self.items if item.target == target)


@dataclass(frozen=True)
class SemanticInterpretation:
    meaning_id: OntologyId
    entity_id: OntologyId | None = None
    measure_id: OntologyId | None = None
    qualifier_id: OntologyId | None = None
    unit_id: OntologyId | None = None
    temporal_role_id: OntologyId | None = None


@dataclass(frozen=True)
class BusinessMeaningCandidate:
    interpretation: SemanticInterpretation
    raw_score: float
    evidence: EvidenceBundle
    uncertainty: float


@dataclass(frozen=True)
class BusinessMeaningResolution:
    selected: BusinessMeaningCandidate | None
    candidates: tuple[BusinessMeaningCandidate, ...]
    status: AbstentionStatus
    rationale: str


@dataclass(frozen=True)
class SectorHypothesis:
    sector_id: OntologyId; probability: float; rationale: str


@dataclass(frozen=True)
class SectorInferenceResult:
    hypotheses: tuple[SectorHypothesis, ...]
    selected: OntologyId | None
    uncertainty: float


@dataclass(frozen=True)
class ValidationFinding:
    rule_id: str; severity: Severity; outcome: ValidationOutcome; explanation: str
    affected_columns: tuple[str, ...] = (); evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidationResult:
    findings: tuple[ValidationFinding, ...] = ()
    score: float = 1.0
    @property
    def blocking(self) -> bool:
        return any(f.severity == Severity.CRITICAL and f.outcome == ValidationOutcome.CONTRADICTED for f in self.findings)


@dataclass(frozen=True)
class CanonicalCandidate:
    canonical_id: OntologyId; score: float; eligible: bool; rationale: str


@dataclass(frozen=True)
class AssignmentDecision:
    canonical_id: OntologyId | None; rationale: str; collision_resolved: bool = False


@dataclass(frozen=True)
class CalibratedConfidence:
    raw_score: float; probability: float; uncertainty: float; margin: float; tier: str


@dataclass(frozen=True)
class AbstentionDecision:
    status: AbstentionStatus; rationale: str


@dataclass(frozen=True)
class SemanticResolution:
    raw_column: str
    column_position: int
    deterministic_method: str | None
    deterministic_canonical_field: str | None
    business_meaning: BusinessMeaningResolution
    canonical_candidates: tuple[CanonicalCandidate, ...]
    assignment: AssignmentDecision
    confidence: CalibratedConfidence
    abstention: AbstentionDecision
    validation: ValidationResult
    status: ResolutionStatus
    trace_id: str
    artifact_versions: ArtifactVersionSet


@dataclass(frozen=True)
class ResolvedSchema:
    fingerprint: DatasetFingerprint
    resolutions: tuple[SemanticResolution, ...]
    sectors: SectorInferenceResult
    artifact_versions: ArtifactVersionSet
    run_id: str


@dataclass(frozen=True)
class CapabilityAssessment:
    capability_id: OntologyId
    available: bool
    confidence: float
    required_meanings: tuple[OntologyId, ...]
    available_meanings: tuple[OntologyId, ...]
