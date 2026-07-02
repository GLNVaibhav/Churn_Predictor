"""
universal_churn/knowledge_base.py
══════════════════════════════════════════════════════════════════════
Typed Business Knowledge Base — Version 7, Chunk 4.

Pure data + typed accessors. Contains NO YAML parsing and NO
validation logic (that lives in knowledge_loader.py) and NO business
reasoning logic (that stays in business_reasoning.py, which only
*reads* a KnowledgeBase instance). This separation mirrors the rest of
the package's "single responsibility per module" convention (see
routing.py's adapter-dataclass pattern for a similar precedent).

Every dataclass here is frozen — a KnowledgeBase, once loaded, is
immutable for the lifetime of the process. Reloading (e.g. after
editing YAML during development) goes through
knowledge_loader.reset_default_knowledge_base() +
knowledge_loader.get_default_knowledge_base(), never in-place mutation.
"""
from __future__ import annotations

from dataclasses import dataclass, field


VALID_DIRECTIONS = {"high_is_good", "high_is_bad", "neutral"}
VALID_BANDS = {"LOW", "MEDIUM", "HIGH"}
VALID_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


@dataclass(frozen=True)
class BandThresholds:
    """Concept aggregate-value → band cutoffs. low_max < high_min."""
    low_max: float
    high_min: float


@dataclass(frozen=True)
class ConceptKnowledge:
    concept_id: str
    direction: str  # one of VALID_DIRECTIONS


@dataclass(frozen=True)
class RuleCondition:
    concept: str
    band: str  # one of VALID_BANDS


@dataclass(frozen=True)
class RuleKnowledge:
    rule_id: str
    finding_id: str
    supporting_concepts: tuple[str, ...]
    conditions: tuple[RuleCondition, ...]


@dataclass(frozen=True)
class FindingKnowledge:
    finding_id: str
    title: str
    severity: str  # one of VALID_SEVERITIES
    explanation: str


@dataclass(frozen=True)
class RecommendationKnowledge:
    finding_id: str
    text: str


class KnowledgeBase:
    """
    Typed, read-only handle over everything knowledge_loader.py parsed
    and validated. business_reasoning.py is the only production
    consumer; nothing on the prediction path (routing.py,
    sector_pipeline.py, universal_pipeline.py, coverage.py) imports
    this module.
    """

    def __init__(
        self,
        concepts: dict[str, ConceptKnowledge],
        band_thresholds: BandThresholds,
        rules: list[RuleKnowledge],
        findings: dict[str, FindingKnowledge],
        recommendations: dict[str, RecommendationKnowledge],
        source_dir: str | None = None,
        version: str = "1.0.0",
    ) -> None:
        self._concepts = dict(concepts)
        self.band_thresholds = band_thresholds
        self._rules = list(rules)
        self._findings = dict(findings)
        self._recommendations = dict(recommendations)
        self.source_dir = source_dir
        self.version = version

    # ── concepts ─────────────────────────────────────────────────
    def concept_ids(self) -> list[str]:
        return list(self._concepts.keys())

    def get_concept(self, concept_id: str) -> ConceptKnowledge | None:
        return self._concepts.get(concept_id)

    def concept_direction(self, concept_id: str) -> str:
        """Defaults to 'neutral' for an unknown concept id, rather than raising —
        callers (e.g. a future concept added to business_concepts.py but not
        yet documented here) should degrade gracefully in the reasoning
        summary, not crash."""
        concept = self._concepts.get(concept_id)
        return concept.direction if concept else "neutral"

    # ── rules ────────────────────────────────────────────────────
    @property
    def rules(self) -> list[RuleKnowledge]:
        return list(self._rules)

    def get_rule(self, rule_id: str) -> RuleKnowledge | None:
        return next((r for r in self._rules if r.rule_id == rule_id), None)

    # ── findings ─────────────────────────────────────────────────
    def get_finding(self, finding_id: str) -> FindingKnowledge | None:
        return self._findings.get(finding_id)

    def finding_ids(self) -> list[str]:
        return list(self._findings.keys())

    # ── recommendations ─────────────────────────────────────────
    def get_recommendation(self, finding_id: str) -> str:
        rec = self._recommendations.get(finding_id)
        return rec.text if rec else ""

    # ── diagnostics ──────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            'version': self.version,
            'source_dir': self.source_dir,
            'band_thresholds': {
                'low_max': self.band_thresholds.low_max,
                'high_min': self.band_thresholds.high_min,
            },
            'concepts': {
                cid: {'direction': c.direction} for cid, c in self._concepts.items()
            },
            'rules': [
                {
                    'id': r.rule_id,
                    'finding_id': r.finding_id,
                    'supporting_concepts': list(r.supporting_concepts),
                    'conditions': [
                        {'concept': c.concept, 'band': c.band} for c in r.conditions
                    ],
                }
                for r in self._rules
            ],
            'findings': {
                fid: {'title': f.title, 'severity': f.severity, 'explanation': f.explanation}
                for fid, f in self._findings.items()
            },
            'recommendations': {
                fid: r.text for fid, r in self._recommendations.items()
            },
        }