from __future__ import annotations
from hashlib import sha256
import pandas as pd
from ..domain.enums import AbstentionStatus, ResolutionStatus
from ..domain.identifiers import ArtifactVersionSet
from ..domain.models import AssignmentDecision, BusinessMeaningResolution, CalibratedConfidence, ResolvedSchema, SemanticResolution, ValidationResult
from ..evidence import DatatypeExtractor, IdentifierExtractor, LexicalExtractor, TemporalExtractor
from ..evidence.abbreviation_extractor import AbbreviationExtractor
from ..evidence.naming_convention_extractor import NamingConventionExtractor
from ..evidence.unit_extractor import UnitExtractor
from ..evidence.distribution_extractor import DistributionExtractor
from ..evidence.cardinality_extractor import CardinalityExtractor
from ..evidence.relational_extractor import RelationalExtractor
from ..evidence.contextual_extractor import ContextualExtractor
from ..evidence.sector_extractor import SectorExtractor
from ..evidence.base import ExtractorContext
from ..inference.abstention_policy import AbstentionPolicy
from ..inference.assignment_resolver import AssignmentResolver
from ..inference.canonical_candidate_generator import CanonicalCandidateGenerator
from ..inference.confidence_calibrator import ConfidenceCalibrator
from ..inference.meaning_candidate_generator import MeaningCandidateGenerator
from ..inference.sector_inferencer import SectorInferencer
from ..knowledge.ontology_repository import OntologyRepository
from ..profiling.dataset_profiler import DatasetProfiler
from ..validation.validation_service import ValidationService

class OnlineResolutionService:
    def __init__(self, ontology: OntologyRepository | None = None) -> None:
        self._ontology = ontology or OntologyRepository()
        self._meaning = MeaningCandidateGenerator((LexicalExtractor(), AbbreviationExtractor(), NamingConventionExtractor(), UnitExtractor(), DatatypeExtractor(), DistributionExtractor(), CardinalityExtractor(), TemporalExtractor(), IdentifierExtractor(), RelationalExtractor(), ContextualExtractor(), SectorExtractor()))
        self._validation, self._canonical = ValidationService(), CanonicalCandidateGenerator()
        self._assignment, self._calibrator, self._abstention, self._sectors = AssignmentResolver(), ConfidenceCalibrator(), AbstentionPolicy(), SectorInferencer()

    def resolve_schema(self, dataset: pd.DataFrame, deterministic_resolutions: dict[str, object] | None = None, profile=None) -> ResolvedSchema:
        profiled = profile or DatasetProfiler().profile(dataset)
        sectors = self._sectors.infer(profiled.dataset)
        deterministic_resolutions = deterministic_resolutions or {}
        resolved = []
        for column in profiled.columns:
            legacy = deterministic_resolutions.get(column.raw_column)
            method = getattr(legacy, "method", None)
            canonical = getattr(legacy, "canonical_field", None)
            if method in {"exact", "regex"} and canonical:
                resolved.append(self._locked(column, method, canonical)); continue
            meaning = self._meaning.generate(ExtractorContext(column, profiled.dataset, self._ontology))
            validation = self._validation.validate(column, meaning)
            candidates = self._canonical.generate(meaning)
            assignment = self._assignment.resolve(candidates)
            scores = [c.score for c in candidates]
            confidence = self._calibrator.calibrate(scores[0] if scores else 0.0, scores[1] if len(scores) > 1 else 0.0)
            abstention = self._abstention.decide(confidence, validation)
            status = ResolutionStatus.SEMANTIC_ACCEPTED if abstention.status == AbstentionStatus.ACCEPTED and assignment.canonical_id else ResolutionStatus.SEMANTIC_REVIEW_REQUIRED if abstention.status == AbstentionStatus.REVIEW_REQUIRED else ResolutionStatus.SEMANTIC_ABSTAINED if meaning.candidates else ResolutionStatus.UNRESOLVED
            resolved.append(SemanticResolution(column.raw_column, column.position, None, None, meaning, candidates, assignment, confidence, abstention, validation, status, self._trace_id(column.raw_column), ArtifactVersionSet()))
        return ResolvedSchema(profiled.dataset.fingerprint, tuple(resolved), sectors, ArtifactVersionSet(), self._trace_id(profiled.dataset.fingerprint.value))

    def _locked(self, column, method: str, canonical: str) -> SemanticResolution:
        status = ResolutionStatus.DETERMINISTIC_EXACT if method == "exact" else ResolutionStatus.DETERMINISTIC_REGEX
        confidence = CalibratedConfidence(1.0 if method == "exact" else .8, 1.0 if method == "exact" else .8, 0.0, 1.0, "deterministic")
        meaning = BusinessMeaningResolution(None, (), AbstentionStatus.ACCEPTED, "Deterministic resolution is immutable; semantic interpretation is non-authoritative.")
        validation = ValidationResult()
        return SemanticResolution(column.raw_column, column.position, method, canonical, meaning, (), AssignmentDecision(None, "Canonical field locked by deterministic precedence."), confidence, self._abstention.decide(confidence, validation, True), validation, status, self._trace_id(column.raw_column), ArtifactVersionSet())

    @staticmethod
    def _trace_id(value: str) -> str: return sha256(value.encode()).hexdigest()[:20]
