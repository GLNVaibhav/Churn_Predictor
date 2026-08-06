"""Executable bridge from UCIF intelligence to a model feature contract.

This module deliberately does *not* resolve input columns by string aliases.
It evaluates the BusinessMeaning and CanonicalMapping already produced for the
input against a semantic contract inferred for each model feature.  It is
introduced in shadow mode first: callers can inspect its bindings and coverage
without changing an established model's input vector.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd

from .business_meaning import BusinessMeaning, infer_business_meaning
from .canonical_mapping import CanonicalMappingResult
from .semantic_schema import profile_column


@dataclass(frozen=True)
class FeatureTransformation:
    name: str
    description: str


@dataclass(frozen=True)
class FeatureProvenance:
    feature: str
    original_column: str | None
    business_meaning: str | None
    canonical_concept: str | None
    transformation: FeatureTransformation
    confidence: float
    missing_reason: str | None = None
    alternative_candidates: tuple[str, ...] = ()
    closest_semantic_concept: str | None = None
    semantic_distance: float | None = None
    required_transformation: str | None = None
    failure_cause: str | None = None


@dataclass(frozen=True)
class FeatureBinding:
    feature: str
    source_column: str | None
    value: pd.Series | None
    provenance: FeatureProvenance


@dataclass(frozen=True)
class FeatureBindingResult:
    bindings: tuple[FeatureBinding, ...]
    semantic_utilization: float
    business_meaning_utilization: float
    feature_coverage: float
    default_feature_count: int

    @property
    def provenance(self) -> tuple[FeatureProvenance, ...]:
        return tuple(binding.provenance for binding in self.bindings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "semantic_utilization": self.semantic_utilization,
            "business_meaning_utilization": self.business_meaning_utilization,
            "feature_coverage": self.feature_coverage,
            "default_feature_count": self.default_feature_count,
            "features": [
                {
                    "feature": item.feature,
                    "origin_csv_column": item.provenance.original_column,
                    "business_meaning": item.provenance.business_meaning,
                    "canonical_concept": item.provenance.canonical_concept,
                    "transformation": item.provenance.transformation.name,
                    "binding_confidence": item.provenance.confidence,
                    "missing_reason": item.provenance.missing_reason,
                    "alternative_candidates": list(item.provenance.alternative_candidates),
                    "closest_semantic_concept": item.provenance.closest_semantic_concept,
                    "semantic_distance": item.provenance.semantic_distance,
                    "required_transformation": item.provenance.required_transformation,
                    "failure_cause": item.provenance.failure_cause,
                }
                for item in self.bindings
            ],
        }


@dataclass(frozen=True)
class SemanticFeatureContract:
    """Semantic intent of a saved-model feature, inferred from its name.

    The header remains a model ABI only.  It is never used to match an input
    column; matching occurs solely on the inferred semantic intent below.
    """
    feature: str
    business_meaning: BusinessMeaning


class SemanticFeatureRegistry:
    """Creates reusable semantic contracts for any existing model schema."""

    def contracts(self, feature_names: Iterable[str]) -> tuple[SemanticFeatureContract, ...]:
        contracts = []
        for feature in feature_names:
            # One-hot feature names describe a value of a parent semantic
            # feature.  The parent is the executable contract; the category
            # remains an encoder concern in the unchanged model adapter.
            parent = str(feature).rsplit("_", 1)[0] if "_" in str(feature) else str(feature)
            sample = pd.Series([0], name=parent)
            contracts.append(SemanticFeatureContract(str(feature), infer_business_meaning(profile_column(parent, sample))))
        return tuple(contracts)

    @staticmethod
    def family(meaning: BusinessMeaning, canonical: str | None = None) -> str:
        """Map ontology concepts to reusable feature families.

        This is a business-concept taxonomy, not an input-header alias table.
        It lets, for example, an account balance and a relationship-value
        feature meet through FinancialStrength rather than through the string
        ``Balance``.  Unknown/general concepts intentionally remain isolated.
        """
        concept = meaning.primary_business_concept.lower()
        canonical = (canonical or "").lower()
        vocabulary = {
            "revenue": "revenue", "averagerevenueperuser": "revenue",
            "accountbalance": "financial_strength", "creditrisk": "financial_strength",
            "financialstrength": "financial_strength", "lifecycle": "lifecycle",
            "engagement": "engagement", "frequency": "interaction", "recency": "recency",
            "orderhistory": "interaction",
            "appointmentrisk": "interaction", "productholding": "portfolio",
            "insurancetype": "contract", "insurancecoverage": "contract",
            "contract": "contract", "customersatisfaction": "satisfaction",
            "satisfaction": "satisfaction", "paymentbehavior": "payment",
            "geography": "location", "location": "location", "demographics": "demographic",
            "medicalspecialty": "service_specialty", "serviceportfolio": "portfolio",
            "demographic": "demographic", "usage": "usage", "datausage": "usage",
            "support": "support", "complaint": "support", "interaction": "interaction",
            "risk": "risk", "retention": "loyalty", "loyalty": "loyalty",
        }
        if concept in vocabulary:
            return vocabulary[concept]
        # Canonical vocabulary is a weaker, but still auditable, ontology
        # signal when the primary classifier is not sufficiently specific.
        if canonical in {"revenue", "cost"}:
            return "revenue"
        if canonical in {"account", "risk"}:
            return "financial_strength"
        if canonical in {"contract", "policy", "subscription"}:
            return "contract"
        if canonical in {"interaction", "claim"}:
            return "interaction"
        if canonical in {"customerexperience"}:
            return "satisfaction"
        return "unknown"


class SemanticFeatureResolver:
    """Bind input columns to model features through UCIF semantic outputs."""

    def __init__(self, registry: SemanticFeatureRegistry | None = None) -> None:
        self.registry = registry or SemanticFeatureRegistry()

    @staticmethod
    def _score(expected: BusinessMeaning, actual: BusinessMeaning, canonical: str) -> tuple[float, str]:
        if actual.primary_business_concept == "GenericConcept":
            return 0.0, "unknown"
        score = 0.0
        expected_family = SemanticFeatureRegistry.family(expected)
        actual_family = SemanticFeatureRegistry.family(actual, canonical)
        if expected.primary_business_concept == actual.primary_business_concept:
            score += 0.70
        if expected_family != "unknown" and expected_family == actual_family:
            score += 0.55
        if expected.domain == actual.domain and expected.domain != "General":
            score += 0.20
        if expected.metric_type == actual.metric_type:
            score += 0.15
        if expected.customer_dimension == actual.customer_dimension:
            score += 0.10
        # A high-confidence canonical concept is evidence, but it must not
        # override a contradictory BusinessMeaning.
        if canonical and canonical == expected.primary_business_concept:
            score += 0.10
        # Column confidence gauges interpretation quality.  It should temper
        # a semantic match, not erase a structurally exact ontology match
        # merely because the column has sparse values or a terse name.
        evidence = 0.50 + 0.50 * actual.confidence
        return min(1.0, score) * evidence, actual_family

    @staticmethod
    def _transformation(expected: BusinessMeaning, actual: BusinessMeaning, family: str) -> FeatureTransformation:
        if family in {"revenue", "financial_strength", "engagement", "usage", "interaction"} and expected.primary_business_concept != actual.primary_business_concept:
            return FeatureTransformation("normalized_proxy", "Reusable semantic-family proxy; model adapter performs saved-model scaling.")
        if family in {"satisfaction", "loyalty", "risk"}:
            return FeatureTransformation("score_projection", "Maps an ordinal semantic score into the model feature's score contract.")
        return FeatureTransformation("identity", "Source value is passed to the model adapter; encoding/scaling remains model-compatible.")

    def resolve(
        self,
        df: pd.DataFrame,
        *,
        business_meanings: Iterable[BusinessMeaning],
        canonical_mapping: CanonicalMappingResult,
        semantic_graph: Any,
        column_profiles: Iterable[Any] | None,
        routing: Any,
        model_features: Iterable[str],
    ) -> FeatureBindingResult:
        """Return auditable semantic bindings; graph/routing are accepted as
        first-class inputs so this remains the sole intelligence bridge.

        They are deliberately not converted into hidden header heuristics.
        Their dataset-level evidence is exposed by callers alongside the
        binding report.
        """
        del semantic_graph, column_profiles, routing  # typed architectural inputs; no duplicate interpretation
        meanings = tuple(business_meanings)
        mappings = tuple(canonical_mapping.mappings)
        candidates = tuple(zip(df.columns, meanings, mappings))
        bindings = []
        for contract in self.registry.contracts(model_features):
            scored = sorted(
                ((score, family, str(column), bm, mapping)
                 for column, bm, mapping in candidates
                 for score, family in [self._score(contract.business_meaning, bm, mapping.chosen_concept.name)]),
                reverse=True, key=lambda item: item[0]
            )
            best = scored[0] if scored else None
            alternatives = tuple(item[2] for item in scored[1:4] if item[0] > 0)
            if best is None or best[0] < 0.40:
                closest = best[3].primary_business_concept if best else None
                distance = round(1.0 - best[0], 4) if best else 1.0
                provenance = FeatureProvenance(
                    contract.feature, None, None, None,
                    FeatureTransformation("default", "All semantic binding strategies failed."),
                    0.0, "No candidate met evidence-backed semantic binding threshold.", alternatives,
                    closest, distance, "identity or semantic-family projection",
                    "weak_canonical_concept" if best else "missing_semantic_concept",
                )
                bindings.append(FeatureBinding(contract.feature, None, None, provenance))
                continue
            confidence, family, column, meaning, mapping = best
            provenance = FeatureProvenance(
                contract.feature, column, meaning.primary_business_concept,
                mapping.chosen_concept.name,
                self._transformation(contract.business_meaning, meaning, family),
                confidence, None, alternatives, meaning.primary_business_concept,
                round(1.0 - confidence, 4), None, None,
            )
            bindings.append(FeatureBinding(contract.feature, column, df[column], provenance))
        total = len(bindings)
        resolved = [item for item in bindings if item.source_column is not None]
        semantic = sum(item.provenance.confidence for item in resolved) / total if total else 0.0
        meaning = sum(item.provenance.business_meaning is not None for item in bindings) / total if total else 0.0
        coverage = len(resolved) / total if total else 0.0
        return FeatureBindingResult(tuple(bindings), semantic, meaning, coverage, total - len(resolved))


class FeatureResolverPipeline:
    """Named composition root used by prediction adapters and diagnostics."""
    def __init__(self, resolver: SemanticFeatureResolver | None = None) -> None:
        self.resolver = resolver or SemanticFeatureResolver()

    def run(self, df: pd.DataFrame, intelligence: Any, model_features: Iterable[str]) -> FeatureBindingResult:
        return self.resolver.resolve(
            df,
            business_meanings=intelligence.business_meanings,
            canonical_mapping=intelligence.canonical_mapping,
            semantic_graph=intelligence.semantic_graph,
            column_profiles=None,
            routing=intelligence.routing,
            model_features=model_features,
        )
