"""
universal_churn/knowledge_loader.py
══════════════════════════════════════════════════════════════════════
Business Knowledge Base loader — Version 7, Chunk 4.
Extended in Version 8, Chunk 1 (Business Intelligence Expansion) to
parse/validate the new fields added to knowledge_base.py:

    findings.yaml        -> FindingKnowledge.category        (required)
    rules.yaml             -> RuleKnowledge.priority            (optional,
                              default DEFAULT_RULE_PRIORITY)
    rules.yaml             -> RuleKnowledge.sectors              (optional,
                              default () = all sectors)
    recommendations.yaml  -> RecommendationKnowledge.priority /
                              .business_impact / .expected_outcome
                              (all required, per Part 6)

The ONLY place YAML is parsed for business knowledge. Loads
knowledge/*.yaml, validates schema + cross-references, and returns a
typed knowledge_base.KnowledgeBase. business_reasoning.py never
touches YAML or the filesystem directly — it only calls
get_default_knowledge_base().

Validation is two-phase, matching the pattern already used by
quality_gate.py / concept_confidence.py (measurement, then a separate
pass that can block):

    1. Per-file schema validation (_parse_*): required keys present,
       correct types, enum values valid, no duplicate IDs WITHIN a
       file.
    2. Cross-file reference validation (_validate_cross_references):
       every rule's finding_id/concepts exist; every finding has a
       recommendation; every recommendation points at a real finding.

Any failure raises KnowledgeValidationError with every problem found
(not just the first), so a broken knowledge/ directory can be fixed
in one pass instead of one error at a time.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from .knowledge_base import (
    KnowledgeBase, BandThresholds, ConceptKnowledge, RuleKnowledge,
    RuleCondition, FindingKnowledge, RecommendationKnowledge,
    VALID_DIRECTIONS, VALID_BANDS, VALID_SEVERITIES,
    VALID_CATEGORIES, VALID_RECOMMENDATION_PRIORITIES,
    DEFAULT_RULE_PRIORITY, DEFAULT_RECOMMENDATION_PRIORITY,
)

DEFAULT_KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"


class KnowledgeValidationError(ValueError):
    """Raised for any missing file, malformed YAML, missing required
    key, invalid enum value, duplicate ID, or broken cross-reference."""


# ══════════════════════════════════════════════════════════════════
# FILE I/O + GENERIC SCHEMA HELPERS
# ══════════════════════════════════════════════════════════════════

def _load_yaml_file(path: Path) -> dict:
    if not path.exists():
        raise KnowledgeValidationError(f"Knowledge file not found: {path}")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise KnowledgeValidationError(f"Malformed YAML in {path}: {exc}") from exc
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise KnowledgeValidationError(
            f"{path} must contain a YAML mapping at the top level, "
            f"got {type(data).__name__}."
        )
    return data


def _require_keys(d: dict, keys: list[str], context: str) -> None:
    if not isinstance(d, dict):
        raise KnowledgeValidationError(f"{context} must be a mapping.")
    missing = [k for k in keys if k not in d]
    if missing:
        raise KnowledgeValidationError(f"{context} is missing required key(s): {missing}")


# ══════════════════════════════════════════════════════════════════
# concepts.yaml
# ══════════════════════════════════════════════════════════════════

def _parse_concepts(
    raw: dict, path: Path,
) -> tuple[dict[str, ConceptKnowledge], BandThresholds]:
    _require_keys(raw, ['concepts', 'band_thresholds'], str(path))
    concepts_list = raw['concepts']
    if not isinstance(concepts_list, list):
        raise KnowledgeValidationError(f"{path}: 'concepts' must be a list.")

    concepts: dict[str, ConceptKnowledge] = {}
    for idx, entry in enumerate(concepts_list):
        if not isinstance(entry, dict):
            raise KnowledgeValidationError(f"{path}: concepts[{idx}] must be a mapping.")
        _require_keys(entry, ['id', 'direction'], f"{path}: concepts[{idx}]")
        concept_id, direction = entry['id'], entry['direction']
        if concept_id in concepts:
            raise KnowledgeValidationError(f"{path}: duplicate concept id '{concept_id}'.")
        if direction not in VALID_DIRECTIONS:
            raise KnowledgeValidationError(
                f"{path}: concept '{concept_id}' has invalid direction '{direction}' "
                f"(expected one of {sorted(VALID_DIRECTIONS)})."
            )
        concepts[concept_id] = ConceptKnowledge(concept_id=concept_id, direction=direction)

    bt = raw['band_thresholds']
    _require_keys(bt, ['low_max', 'high_min'], f"{path}: band_thresholds")
    low_max, high_min = bt['low_max'], bt['high_min']
    if not (isinstance(low_max, (int, float)) and isinstance(high_min, (int, float))):
        raise KnowledgeValidationError(f"{path}: band_thresholds values must be numeric.")
    if not (0.0 <= low_max <= 1.0 and 0.0 <= high_min <= 1.0):
        raise KnowledgeValidationError(f"{path}: band_thresholds must be within [0, 1].")
    if low_max >= high_min:
        raise KnowledgeValidationError(
            f"{path}: band_thresholds.low_max ({low_max}) must be < high_min ({high_min})."
        )

    return concepts, BandThresholds(low_max=float(low_max), high_min=float(high_min))


# ══════════════════════════════════════════════════════════════════
# findings.yaml
# ══════════════════════════════════════════════════════════════════

def _parse_findings(raw: dict, path: Path) -> dict[str, FindingKnowledge]:
    _require_keys(raw, ['findings'], str(path))
    findings_list = raw['findings']
    if not isinstance(findings_list, list):
        raise KnowledgeValidationError(f"{path}: 'findings' must be a list.")

    findings: dict[str, FindingKnowledge] = {}
    for idx, entry in enumerate(findings_list):
        if not isinstance(entry, dict):
            raise KnowledgeValidationError(f"{path}: findings[{idx}] must be a mapping.")
        _require_keys(
            entry, ['id', 'title', 'severity', 'explanation', 'category'],
            f"{path}: findings[{idx}]",
        )
        finding_id, severity, category = entry['id'], entry['severity'], entry['category']
        if finding_id in findings:
            raise KnowledgeValidationError(f"{path}: duplicate finding id '{finding_id}'.")
        if severity not in VALID_SEVERITIES:
            raise KnowledgeValidationError(
                f"{path}: finding '{finding_id}' has invalid severity '{severity}' "
                f"(expected one of {sorted(VALID_SEVERITIES)})."
            )
        if category not in VALID_CATEGORIES:
            raise KnowledgeValidationError(
                f"{path}: finding '{finding_id}' has invalid category '{category}' "
                f"(expected one of {sorted(VALID_CATEGORIES)})."
            )
        findings[finding_id] = FindingKnowledge(
            finding_id=finding_id, title=entry['title'],
            severity=severity, explanation=entry['explanation'],
            category=category,
        )
    return findings


# ══════════════════════════════════════════════════════════════════
# recommendations.yaml
# ══════════════════════════════════════════════════════════════════

def _parse_recommendations(raw: dict, path: Path) -> dict[str, RecommendationKnowledge]:
    _require_keys(raw, ['recommendations'], str(path))
    rec_list = raw['recommendations']
    if not isinstance(rec_list, list):
        raise KnowledgeValidationError(f"{path}: 'recommendations' must be a list.")

    recommendations: dict[str, RecommendationKnowledge] = {}
    for idx, entry in enumerate(rec_list):
        if not isinstance(entry, dict):
            raise KnowledgeValidationError(f"{path}: recommendations[{idx}] must be a mapping.")
        _require_keys(
            entry,
            ['finding_id', 'text', 'priority', 'business_impact', 'expected_outcome'],
            f"{path}: recommendations[{idx}]",
        )
        finding_id = entry['finding_id']
        priority = entry['priority']
        if finding_id in recommendations:
            raise KnowledgeValidationError(
                f"{path}: duplicate recommendation for finding_id '{finding_id}'."
            )
        if priority not in VALID_RECOMMENDATION_PRIORITIES:
            raise KnowledgeValidationError(
                f"{path}: recommendation for '{finding_id}' has invalid priority "
                f"'{priority}' (expected one of {sorted(VALID_RECOMMENDATION_PRIORITIES)})."
            )
        recommendations[finding_id] = RecommendationKnowledge(
            finding_id=finding_id, text=entry['text'],
            priority=priority,
            business_impact=entry['business_impact'],
            expected_outcome=entry['expected_outcome'],
        )
    return recommendations


# ══════════════════════════════════════════════════════════════════
# rules.yaml
# ══════════════════════════════════════════════════════════════════

def _parse_rules(raw: dict, path: Path) -> list[RuleKnowledge]:
    _require_keys(raw, ['rules'], str(path))
    rules_list = raw['rules']
    if not isinstance(rules_list, list):
        raise KnowledgeValidationError(f"{path}: 'rules' must be a list.")

    seen_ids: set[str] = set()
    rules: list[RuleKnowledge] = []
    for idx, entry in enumerate(rules_list):
        if not isinstance(entry, dict):
            raise KnowledgeValidationError(f"{path}: rules[{idx}] must be a mapping.")
        _require_keys(
            entry, ['id', 'finding_id', 'supporting_concepts', 'conditions'],
            f"{path}: rules[{idx}]",
        )
        rule_id = entry['id']
        if rule_id in seen_ids:
            raise KnowledgeValidationError(f"{path}: duplicate rule id '{rule_id}'.")
        seen_ids.add(rule_id)

        supporting = entry['supporting_concepts']
        if not isinstance(supporting, list) or not supporting:
            raise KnowledgeValidationError(
                f"{path}: rule '{rule_id}' supporting_concepts must be a non-empty list."
            )

        conditions_raw = entry['conditions']
        if not isinstance(conditions_raw, list) or not conditions_raw:
            raise KnowledgeValidationError(
                f"{path}: rule '{rule_id}' conditions must be a non-empty list."
            )
        conditions: list[RuleCondition] = []
        for c_idx, cond in enumerate(conditions_raw):
            if not isinstance(cond, dict):
                raise KnowledgeValidationError(
                    f"{path}: rule '{rule_id}' conditions[{c_idx}] must be a mapping."
                )
            _require_keys(
                cond, ['concept', 'band'], f"{path}: rule '{rule_id}' conditions[{c_idx}]"
            )
            band = cond['band']
            if band not in VALID_BANDS:
                raise KnowledgeValidationError(
                    f"{path}: rule '{rule_id}' condition band '{band}' is invalid "
                    f"(expected one of {sorted(VALID_BANDS)})."
                )
            conditions.append(RuleCondition(concept=cond['concept'], band=band))

        # ── Version 8, Chunk 1: optional priority / sectors ─────────
        priority = entry.get('priority', DEFAULT_RULE_PRIORITY)
        if not isinstance(priority, int) or isinstance(priority, bool):
            raise KnowledgeValidationError(
                f"{path}: rule '{rule_id}' priority must be an integer, "
                f"got {type(priority).__name__}."
            )

        sectors_raw = entry.get('sectors', [])
        if not isinstance(sectors_raw, list) or not all(isinstance(s, str) for s in sectors_raw):
            raise KnowledgeValidationError(
                f"{path}: rule '{rule_id}' sectors must be a list of strings."
            )

        rules.append(RuleKnowledge(
            rule_id=rule_id, finding_id=entry['finding_id'],
            supporting_concepts=tuple(supporting), conditions=tuple(conditions),
            priority=priority, sectors=tuple(sectors_raw),
        ))
    return rules


# ══════════════════════════════════════════════════════════════════
# CROSS-REFERENCE VALIDATION (across all four files)
# ══════════════════════════════════════════════════════════════════

def _validate_cross_references(
    concepts: dict[str, ConceptKnowledge],
    findings: dict[str, FindingKnowledge],
    recommendations: dict[str, RecommendationKnowledge],
    rules: list[RuleKnowledge],
) -> None:
    errors: list[str] = []

    for rule in rules:
        if rule.finding_id not in findings:
            errors.append(
                f"rule '{rule.rule_id}' references unknown finding_id '{rule.finding_id}'."
            )
        elif rule.finding_id not in recommendations:
            errors.append(
                f"rule '{rule.rule_id}' references finding_id '{rule.finding_id}' "
                f"which has no entry in recommendations.yaml."
            )
        for concept_id in rule.supporting_concepts:
            if concept_id not in concepts:
                errors.append(
                    f"rule '{rule.rule_id}' supporting_concepts references "
                    f"unknown concept '{concept_id}'."
                )
        for cond in rule.conditions:
            if cond.concept not in concepts:
                errors.append(
                    f"rule '{rule.rule_id}' condition references unknown "
                    f"concept '{cond.concept}'."
                )
            if cond.concept not in rule.supporting_concepts:
                errors.append(
                    f"rule '{rule.rule_id}' condition on '{cond.concept}' is "
                    f"not listed in supporting_concepts."
                )

    for finding_id in recommendations:
        if finding_id not in findings:
            errors.append(
                f"recommendations.yaml has an entry for unknown finding_id '{finding_id}'."
            )

    if errors:
        raise KnowledgeValidationError(
            "Business Knowledge Base cross-reference validation failed:\n  - "
            + "\n  - ".join(errors)
        )


# ══════════════════════════════════════════════════════════════════
# PUBLIC ENTRY POINT
# ══════════════════════════════════════════════════════════════════

def load_knowledge_base(knowledge_dir: str | Path | None = None) -> KnowledgeBase:
    """
    Load, validate, and return the Business Knowledge Base.

    Raises KnowledgeValidationError on any missing file, malformed
    YAML, missing required key, invalid enum value, duplicate ID, or
    broken cross-reference.
    """
    directory = Path(knowledge_dir) if knowledge_dir is not None else DEFAULT_KNOWLEDGE_DIR
    if not directory.exists():
        raise KnowledgeValidationError(f"Knowledge base directory not found: {directory}")

    concepts_path = directory / "concepts.yaml"
    findings_path = directory / "findings.yaml"
    recommendations_path = directory / "recommendations.yaml"
    rules_path = directory / "rules.yaml"

    concepts_raw = _load_yaml_file(concepts_path)
    findings_raw = _load_yaml_file(findings_path)
    recommendations_raw = _load_yaml_file(recommendations_path)
    rules_raw = _load_yaml_file(rules_path)

    concepts, band_thresholds = _parse_concepts(concepts_raw, concepts_path)
    findings = _parse_findings(findings_raw, findings_path)
    recommendations = _parse_recommendations(recommendations_raw, recommendations_path)
    rules = _parse_rules(rules_raw, rules_path)

    _validate_cross_references(concepts, findings, recommendations, rules)

    return KnowledgeBase(
        concepts=concepts, band_thresholds=band_thresholds, rules=rules,
        findings=findings, recommendations=recommendations, source_dir=str(directory),
    )


# ── process-wide singleton (mirrors semantic_schema.py's resolver pattern) ──

_default_kb: KnowledgeBase | None = None


def get_default_knowledge_base() -> KnowledgeBase:
    """Process-wide singleton, built once on first use."""
    global _default_kb
    if _default_kb is None:
        _default_kb = load_knowledge_base()
    return _default_kb


def reset_default_knowledge_base() -> None:
    """Test helper — forces the next get_default_knowledge_base() call
    to reload from disk (e.g. after editing YAML during development)."""
    global _default_kb
    _default_kb = None
