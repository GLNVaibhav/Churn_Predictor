"""
universal_churn/knowledge_base.py
══════════════════════════════════════════════════════════════════════
Typed Business Knowledge Base — Version 7, Chunk 4.
Extended in Version 8, Chunk 1 (Business Intelligence Expansion) with:

    - FindingKnowledge.category           (Part 5 — required, validated
                                            against VALID_CATEGORIES)
    - RuleKnowledge.priority              (Part 4 — numeric sort order,
                                            higher fires/reports first)
    - RuleKnowledge.sectors               (Part 1 — optional sector
                                            scoping; empty = all sectors)
    - RecommendationKnowledge.priority /
      .business_impact / .expected_outcome (Part 6 — recommendation
                                            ranking / richer text)

Pure data + typed accessors. Contains NO YAML parsing and NO
validation logic (that lives in knowledge_loader.py) and NO business
reasoning logic (that stays in business_reasoning.py, which only
*reads* a KnowledgeBase instance). This separation mirrors the rest of
the package's "single responsibility per module" convention.

Every dataclass here is frozen — a KnowledgeBase, once loaded, is
immutable for the lifetime of the process. Reloading (e.g. after
editing YAML during development) goes through
knowledge_loader.reset_default_knowledge_base() +
knowledge_loader.get_default_knowledge_base(), never in-place mutation.

Non-interference note
----------------------
Every field added in this chunk is either new (category, priority,
sectors, business_impact, expected_outcome) or has a safe default —
nothing here removes or renames a pre-existing field, so every
pre-V8 caller (business_reasoning.py's old call sites, tests,
reporting.py) continues to work unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, field


VALID_DIRECTIONS = {"high_is_good", "high_is_bad", "neutral"}
VALID_BANDS = {"LOW", "MEDIUM", "HIGH"}
VALID_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

# Version 8, Chunk 1 additions ---------------------------------------

# Part 6: recommendation action-priority labels. Deliberately the same
# vocabulary as VALID_SEVERITIES (LOW/MEDIUM/HIGH/CRITICAL) since both
# describe "how urgently should a human act", just on different
# objects (a finding's severity vs. a recommendation's priority) —
# reusing the vocabulary avoids inventing a second, subtly different
# urgency scale.
VALID_RECOMMENDATION_PRIORITIES = set(VALID_SEVERITIES)

# Part 5: every finding must belong to exactly one of these categories.
# This set is intentionally the same list enumerated in the Version 8
# spec ("These categories will later support dashboards.") — adding a
# new category later means adding one string here plus updating any
# findings.yaml entries that use it; nothing else needs to change.
VALID_CATEGORIES = {
    "Retention",
    "Revenue",
    "Customer Experience",
    "Operations",
    "Support",
    "Financial",
    "Engagement",
    "Healthcare Quality",
    "Digital Adoption",
}

# Known sector keys a rule may scope itself to (mirrors config.SECTOR_CONFIG's
# keys). Kept as a plain tuple here — not imported from config.py — so this
# module has zero dependency on config.py or any prediction-path module,
# preserving "nothing on the prediction path imports this module".
KNOWN_SECTORS = ("telecom", "ecommerce", "banking", "healthcare")

DEFAULT_RULE_PRIORITY = 50
DEFAULT_RECOMMENDATION_PRIORITY = "MEDIUM"


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
    # Version 8, Chunk 1 additions:
    priority: int = DEFAULT_RULE_PRIORITY
    sectors: tuple[str, ...] = ()  # empty = applies to every sector

    def applies_to_sector(self, sector: str) -> bool:
        """True if this rule is eligible to fire for `sector` — either
        because it is unscoped (applies everywhere) or because
        `sector` is explicitly listed."""
        return not self.sectors or sector in self.sectors


@dataclass(frozen=True)
class FindingKnowledge:
    finding_id: str
    title: str
    severity: str  # one of VALID_SEVERITIES
    explanation: str
    # Version 8, Chunk 1 addition (Part 5 — required at load time):
    category: str = "Uncategorized"


@dataclass(frozen=True)
class RecommendationKnowledge:
    finding_id: str
    text: str
    # Version 8, Chunk 1 additions (Part 6):
    priority: str = DEFAULT_RECOMMENDATION_PRIORITY   # one of VALID_RECOMMENDATION_PRIORITIES
    business_impact: str = ""
    expected_outcome: str = ""


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
        """All rules, in declaration (rules.yaml) order. Callers that
        want priority order should sort explicitly — declaration order
        is preserved here so rules_for_sector()'s stable sort has a
        deterministic tie-break, per Part 4 ("Rules with equal
        priority retain deterministic ordering")."""
        return list(self._rules)

    def get_rule(self, rule_id: str) -> RuleKnowledge | None:
        return next((r for r in self._rules if r.rule_id == rule_id), None)

    def rules_for_sector(self, sector: str) -> list[RuleKnowledge]:
        """
        Rules eligible to fire for `sector` (unscoped rules + rules
        explicitly scoped to `sector`), sorted by priority descending.
        Python's sort is stable, so rules with equal priority retain
        their rules.yaml declaration order (Part 4).
        """
        eligible = [r for r in self._rules if r.applies_to_sector(sector)]
        return sorted(eligible, key=lambda r: -r.priority)

    # ── findings ─────────────────────────────────────────────────
    def get_finding(self, finding_id: str) -> FindingKnowledge | None:
        return self._findings.get(finding_id)

    def finding_ids(self) -> list[str]:
        return list(self._findings.keys())

    def findings_by_category(self, category: str) -> list[FindingKnowledge]:
        return [f for f in self._findings.values() if f.category == category]

    # ── recommendations ─────────────────────────────────────────
    def get_recommendation(self, finding_id: str) -> str:
        """Backward-compatible accessor — text only. Pre-Chunk-1 callers
        (e.g. prediction_explanation.py's `_recommendation_for()`
        fallback) keep working unchanged."""
        rec = self._recommendations.get(finding_id)
        return rec.text if rec else ""

    def get_recommendation_details(self, finding_id: str) -> RecommendationKnowledge | None:
        """Full recommendation object, including priority/business_impact/
        expected_outcome (Part 6). New in Version 8, Chunk 1."""
        return self._recommendations.get(finding_id)

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
                    'priority': r.priority,
                    'sectors': list(r.sectors),
                }
                for r in self._rules
            ],
            'findings': {
                fid: {
                    'title': f.title, 'severity': f.severity,
                    'explanation': f.explanation, 'category': f.category,
                }
                for fid, f in self._findings.items()
            },
            'recommendations': {
                fid: {
                    'text': r.text, 'priority': r.priority,
                    'business_impact': r.business_impact,
                    'expected_outcome': r.expected_outcome,
                }
                for fid, r in self._recommendations.items()
            },
        }
