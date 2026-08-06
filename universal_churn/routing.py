# universal_churn/routing.py
"""Routing Intelligence

Determines the most appropriate churn pipeline for a dataset based on the deterministic
outputs of previous UCIF intelligence layers.

The implementation follows the refined plan:
- Coverage readiness is a gate‑keeper.
- Candidates are generated only for the dominant (and optional secondary) domain
  plus a GenericPipeline fallback.
- Dominant domain is taken from ContextValidation.
- Decision factors are represented with a structured `DecisionFactor` dataclass.
- `RoutingAssessment` includes the selected candidate for convenience.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Dict, Any

# Import previous intelligence outputs
from .business_meaning import BusinessMeaning
from .context_validation import ContextValidation
from .semantic_graph import SemanticKnowledgeGraph
from .canonical_mapping import CanonicalMappingResult
from .coverage import CoverageResult

# ---------------------------------------------------------------------------
# Public immutable dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DecisionFactor:
    """Structured evidence used for scoring a routing candidate.

    Attributes
    ----------
    name: str – identifier of the factor (e.g., "domain_agreement").
    score: float – factor score in [0, 1].
    weight: float – deterministic weight applied to the factor.
    reasoning: str – deterministic explanation of how the score was derived.
    """

    name: str
    score: float
    weight: float
    reasoning: str


@dataclass(frozen=True)
class RoutingCandidate:
    """A candidate pipeline with a deterministic base score and factor breakdown."""

    pipeline_name: str
    base_score: float
    reasoning: str
    factors: Tuple[DecisionFactor, ...]

    @property
    def final_score(self) -> float:
        """Combine base score with weighted factors.

        Base weight is fixed at 0.4; the remaining 0.6 is distributed among the
        decision factors (their weights sum to 0.6).
        """
        base_weight = 0.4
        factor_contrib = sum(f.weight * f.score for f in self.factors)
        return min(1.0, max(0.0, base_weight * self.base_score + factor_contrib))


@dataclass(frozen=True)
class RoutingDecision:
    """Result of the routing process – the chosen pipeline.

    Attributes
    ----------
    selected_pipeline: str – name of the pipeline selected.
    confidence: float – overall routing confidence (the final_score of the selected candidate).
    fallback_used: bool – True if the GenericPipeline was chosen due to insufficient coverage.
    reasoning: str – deterministic explanation of the decision.
    """

    selected_pipeline: str
    confidence: float
    fallback_used: bool
    reasoning: str


@dataclass(frozen=True)
class RoutingAssessment:
    """Full assessment after routing – candidates and the selected one."""

    candidates: Tuple[RoutingCandidate, ...]
    selected_candidate: RoutingCandidate
    decision_factors: Tuple[DecisionFactor, ...]


@dataclass(frozen=True)
class RoutingResult:
    """Public API return type for ``infer_routing``."""

    decision: RoutingDecision
    assessment: RoutingAssessment

# ---------------------------------------------------------------------------
# Helper constants and mappings
# ---------------------------------------------------------------------------

# Mapping from domain identifiers to pipeline names (CamelCase as required)
_PIPELINE_MAP: Dict[str, str] = {
    "Telecom": "TelecomPipeline",
    "Banking": "BankingPipeline",
    "Insurance": "InsurancePipeline",
    "Healthcare": "HealthcarePipeline",
    "Retail": "RetailPipeline",
    "Ecommerce": "EcommercePipeline",
    "SaaS": "SaaSPipeline",
    "Subscription": "SubscriptionPipeline",
    "Generic": "GenericPipeline",
}

# Factor weight configuration – sum of all factor weights = 0.6 (see RoutingCandidate.final_score)
_FACTOR_WEIGHTS: Dict[str, float] = {
    "coverage_gatekeeper": 0.30,
    "domain_agreement": 0.25,
    "canonical_coverage": 0.15,
    "business_meaning_confidence": 0.10,
    "semantic_consistency": 0.10,
    "overall_confidence": 0.10,
}

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _dominant_and_secondary_domains(context: ContextValidation) -> Tuple[str, List[str]]:
    """Return the dominant domain and optionally a secondary domain.

    The dominant domain is ``context.dataset_domain``.
    The secondary domain (if any) is the next most‑voted domain whose vote count is
    at least 80 % of the dominant vote count.
    """
    dominant = context.dataset_domain
    votes = context.domain_votes
    sorted_votes = sorted(votes.items(), key=lambda kv: kv[1], reverse=True)
    secondary_candidates: List[str] = []
    if len(sorted_votes) > 1:
        dominant_votes = votes.get(dominant, 0)
        second_domain, second_votes = sorted_votes[1]
        if dominant_votes > 0 and second_votes / dominant_votes >= 0.8:
            secondary_candidates.append(second_domain)
    return dominant, secondary_candidates


def _build_candidates(dominant: str, secondary: List[str]) -> List[RoutingCandidate]:
    """Create routing candidates for the dominant (and optional secondary) domain.

    Base scores are deterministic:
    - dominant domain pipeline: 0.90
    - secondary domain pipeline (if any): 0.80
    - GenericPipeline: 0.50
    """
    candidates: List[RoutingCandidate] = []
    # Dominant
    pipeline = _PIPELINE_MAP.get(dominant, _PIPELINE_MAP["Generic"])
    candidates.append(
        RoutingCandidate(
            pipeline_name=pipeline,
            base_score=0.90,
            reasoning=f"Dominant domain '{dominant}' maps to {pipeline}.",
            factors=(),
        )
    )
    # Secondary (optional)
    for sec in secondary:
        sec_pipeline = _PIPELINE_MAP.get(sec, _PIPELINE_MAP["Generic"])
        candidates.append(
            RoutingCandidate(
                pipeline_name=sec_pipeline,
                base_score=0.80,
                reasoning=f"Secondary domain '{sec}' maps to {sec_pipeline}.",
                factors=(),
            )
        )
    # Generic always available
    candidates.append(
        RoutingCandidate(
            pipeline_name=_PIPELINE_MAP["Generic"],
            base_score=0.50,
            reasoning="Generic fallback pipeline.",
            factors=(),
        )
    )
    return candidates


def _readiness_score(readiness: str) -> float:
    """Map readiness string to a numeric score in [0,1]."""
    mapping = {
        "READY": 1.0,
        "MOSTLY_READY": 0.8,
        "PARTIALLY_READY": 0.6,
        "NOT_READY": 0.0,
    }
    return mapping.get(readiness.upper(), 0.0)


def _evaluate_factors(
    candidate: RoutingCandidate,
    coverage: CoverageResult,
    canonical: CanonicalMappingResult,
    bms: List[BusinessMeaning],
    graph: SemanticKnowledgeGraph,
    context: ContextValidation,
) -> Tuple[RoutingCandidate, List[DecisionFactor]]:
    """Compute the full factor list for a candidate and return an updated candidate.
    """
    factors: List[DecisionFactor] = []

    # 1. Coverage gatekeeper (already ensured readiness != NOT_READY before calling)
    cov_score = _readiness_score(coverage.summary.readiness)
    factors.append(
        DecisionFactor(
            name="coverage_gatekeeper",
            score=cov_score,
            weight=_FACTOR_WEIGHTS["coverage_gatekeeper"],
            reasoning=f"Readiness '{coverage.summary.readiness}' maps to score {cov_score:.2f}.",
        )
    )

    # 2. Domain agreement – proportion of dominant votes
    total_votes = sum(context.domain_votes.values()) or 1
    dominant_votes = context.domain_votes.get(context.dataset_domain, 0)
    domain_agreement = dominant_votes / total_votes
    factors.append(
        DecisionFactor(
            name="domain_agreement",
            score=domain_agreement,
            weight=_FACTOR_WEIGHTS["domain_agreement"],
            reasoning=f"Dominant domain votes {dominant_votes}/{total_votes} ({domain_agreement:.2f}).",
        )
    )

    # 3. Canonical coverage – use concept_coverage from CoverageResult
    canonical_cov = coverage.summary.concept_coverage
    factors.append(
        DecisionFactor(
            name="canonical_coverage",
            score=canonical_cov,
            weight=_FACTOR_WEIGHTS["canonical_coverage"],
            reasoning=f"Concept coverage from CoverageResult is {canonical_cov:.2f}.",
        )
    )

    # 4. Business meaning confidence – average confidence of BusinessMeaning list
    bm_conf = sum(bm.confidence for bm in bms) / len(bms) if bms else 0.0
    factors.append(
        DecisionFactor(
            name="business_meaning_confidence",
            score=bm_conf,
            weight=_FACTOR_WEIGHTS["business_meaning_confidence"],
            reasoning=f"Average BusinessMeaning confidence is {bm_conf:.2f}.",
        )
    )

    # 5. Semantic consistency – semantic_coverage from CoverageResult
    semantic_cov = coverage.summary.semantic_coverage
    factors.append(
        DecisionFactor(
            name="semantic_consistency",
            score=semantic_cov,
            weight=_FACTOR_WEIGHTS["semantic_consistency"],
            reasoning=f"Semantic coverage is {semantic_cov:.2f}.",
        )
    )

    # 6. Overall confidence – confidence_coverage from CoverageResult
    overall_conf = coverage.summary.confidence_coverage
    factors.append(
        DecisionFactor(
            name="overall_confidence",
            score=overall_conf,
            weight=_FACTOR_WEIGHTS["overall_confidence"],
            reasoning=f"Overall confidence coverage is {overall_conf:.2f}.",
        )
    )

    new_candidate = RoutingCandidate(
        pipeline_name=candidate.pipeline_name,
        base_score=candidate.base_score,
        reasoning=candidate.reasoning,
        factors=tuple(factors),
    )
    return new_candidate, factors


def _select_best(candidates: List[RoutingCandidate]) -> Tuple[RoutingDecision, RoutingCandidate]:
    """Select the candidate with the highest final_score, deterministic tie‑break.
    """
    sorted_candidates = sorted(
        candidates,
        key=lambda c: (c.final_score, c.pipeline_name),
        reverse=True,
    )
    best = sorted_candidates[0]
    reasoning = (
        f"Selected {best.pipeline_name} with final score {best.final_score:.2f}. "
        "Factors contributed to this decision."
    )
    decision = RoutingDecision(
        selected_pipeline=best.pipeline_name,
        confidence=best.final_score,
        fallback_used=best.pipeline_name == _PIPELINE_MAP["Generic"],
        reasoning=reasoning,
    )
    return decision, best


def _fallback_decision() -> RoutingResult:
    """Return a RoutingResult that forces the GenericPipeline.
    """
    generic_candidate = RoutingCandidate(
        pipeline_name=_PIPELINE_MAP["Generic"],
        base_score=0.0,
        reasoning="Coverage readiness NOT_READY – forced GenericPipeline.",
        factors=(),
    )
    decision = RoutingDecision(
        selected_pipeline=_PIPELINE_MAP["Generic"],
        confidence=0.0,
        fallback_used=True,
        reasoning="Coverage readiness NOT_READY – fallback to GenericPipeline.",
    )
    assessment = RoutingAssessment(
        candidates=(generic_candidate,),
        selected_candidate=generic_candidate,
        decision_factors=(),
    )
    return RoutingResult(decision=decision, assessment=assessment)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def infer_routing(
    business_meanings: List[BusinessMeaning],
    context: ContextValidation,
    semantic_graph: SemanticKnowledgeGraph,
    canonical_mapping: CanonicalMappingResult,
    coverage: CoverageResult,
) -> RoutingResult:
    """Deterministic routing decision based on all prior UCIF layers.

    Parameters
    ----------
    business_meanings: List[BusinessMeaning]
        Output of Business Meaning Intelligence.
    context: ContextValidation
        Output of Context Validation Intelligence (provides dominant domain).
    semantic_graph: SemanticKnowledgeGraph
        Output of Semantic Knowledge Graph Intelligence.
    canonical_mapping: CanonicalMappingResult
        Output of Canonical Mapping Intelligence.
    coverage: CoverageResult
        Output of Coverage Intelligence – used as gate‑keeper and for factor scores.

    Returns
    -------
    RoutingResult
        Includes the selected pipeline, confidence score, fallback flag, and a full assessment.
    """
    # 1. Gate‑keeper – if coverage not ready, immediate fallback
    if coverage.summary.readiness.upper() == "NOT_READY":
        return _fallback_decision()

    # 2. Determine dominant (and possibly secondary) domain from ContextValidation
    dominant, secondary = _dominant_and_secondary_domains(context)

    # 3. Build initial candidates (without factor breakdown yet)
    raw_candidates = _build_candidates(dominant, secondary)

    # 4. Evaluate factors for each candidate
    evaluated_candidates: List[RoutingCandidate] = []
    all_factors: List[DecisionFactor] = []
    for cand in raw_candidates:
        new_cand, factors = _evaluate_factors(
            cand,
            coverage,
            canonical_mapping,
            business_meanings,
            semantic_graph,
            context,
        )
        evaluated_candidates.append(new_cand)
        all_factors.extend(factors)

    # 5. Select the best candidate deterministically
    decision, selected_candidate = _select_best(evaluated_candidates)

    # 6. Assemble assessment
    assessment = RoutingAssessment(
        candidates=tuple(evaluated_candidates),
        selected_candidate=selected_candidate,
        decision_factors=tuple(all_factors),
    )

    return RoutingResult(decision=decision, assessment=assessment)
