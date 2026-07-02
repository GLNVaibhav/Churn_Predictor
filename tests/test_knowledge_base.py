"""
tests/test_knowledge_base.py
Tests for the Business Knowledge Base loader (Version 7, Chunk 4).
"""
import textwrap
from pathlib import Path

import pytest

from universal_churn.knowledge_loader import (
    load_knowledge_base, KnowledgeValidationError, DEFAULT_KNOWLEDGE_DIR,
)

VALID_CONCEPTS = textwrap.dedent("""\
    band_thresholds:
      low_max: 0.35
      high_min: 0.65
    concepts:
      - id: CONCEPT_A
        direction: high_is_good
      - id: CONCEPT_B
        direction: high_is_bad
""")

VALID_FINDINGS = textwrap.dedent("""\
    findings:
      - id: FINDING_A
        title: Finding A
        severity: HIGH
        explanation: "Because of reasons."
""")

VALID_RECOMMENDATIONS = textwrap.dedent("""\
    recommendations:
      - finding_id: FINDING_A
        text: "Do something about it."
""")

VALID_RULES = textwrap.dedent("""\
    rules:
      - id: RULE_A
        finding_id: FINDING_A
        supporting_concepts: [CONCEPT_A, CONCEPT_B]
        conditions:
          - concept: CONCEPT_A
            band: HIGH
          - concept: CONCEPT_B
            band: LOW
""")


def _write_kb(tmp_path: Path, *, concepts=None, findings=None,
              recommendations=None, rules=None) -> Path:
    kb_dir = tmp_path / "knowledge"
    kb_dir.mkdir()
    (kb_dir / "concepts.yaml").write_text(concepts or VALID_CONCEPTS)
    (kb_dir / "findings.yaml").write_text(findings or VALID_FINDINGS)
    (kb_dir / "recommendations.yaml").write_text(recommendations or VALID_RECOMMENDATIONS)
    (kb_dir / "rules.yaml").write_text(rules or VALID_RULES)
    return kb_dir


class TestValidLoad:
    def test_loads_valid_minimal_kb(self, tmp_path):
        kb = load_knowledge_base(_write_kb(tmp_path))
        assert kb.concept_ids() == ["CONCEPT_A", "CONCEPT_B"]
        assert kb.band_thresholds.low_max == 0.35
        assert kb.band_thresholds.high_min == 0.65
        rule = kb.get_rule("RULE_A")
        assert rule is not None and rule.finding_id == "FINDING_A"
        assert kb.get_finding("FINDING_A").title == "Finding A"
        assert kb.get_recommendation("FINDING_A") == "Do something about it."

    def test_loads_real_production_knowledge_base(self):
        kb = load_knowledge_base(DEFAULT_KNOWLEDGE_DIR)
        assert len(kb.rules) == 4
        for rule in kb.rules:
            assert kb.get_finding(rule.finding_id) is not None
            assert kb.get_recommendation(rule.finding_id)


class TestMissingFiles:
    def test_missing_directory_raises(self, tmp_path):
        with pytest.raises(KnowledgeValidationError):
            load_knowledge_base(tmp_path / "does_not_exist")

    def test_missing_file_raises(self, tmp_path):
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()
        (kb_dir / "concepts.yaml").write_text(VALID_CONCEPTS)
        with pytest.raises(KnowledgeValidationError):
            load_knowledge_base(kb_dir)


class TestMalformedYaml:
    def test_malformed_yaml_syntax_raises(self, tmp_path):
        with pytest.raises(KnowledgeValidationError):
            load_knowledge_base(_write_kb(tmp_path, concepts="concepts: [unterminated"))

    def test_non_mapping_top_level_raises(self, tmp_path):
        with pytest.raises(KnowledgeValidationError):
            load_knowledge_base(_write_kb(tmp_path, concepts="- a\n- list\n"))

    def test_missing_required_key_raises(self, tmp_path):
        bad = textwrap.dedent("""\
            band_thresholds: {low_max: 0.35, high_min: 0.65}
            concepts:
              - id: CONCEPT_A
        """)
        with pytest.raises(KnowledgeValidationError):
            load_knowledge_base(_write_kb(tmp_path, concepts=bad))

    def test_invalid_direction_raises(self, tmp_path):
        bad = textwrap.dedent("""\
            band_thresholds: {low_max: 0.35, high_min: 0.65}
            concepts:
              - id: CONCEPT_A
                direction: sideways
        """)
        with pytest.raises(KnowledgeValidationError):
            load_knowledge_base(_write_kb(tmp_path, concepts=bad))

    def test_invalid_band_in_condition_raises(self, tmp_path):
        bad = textwrap.dedent("""\
            rules:
              - id: RULE_A
                finding_id: FINDING_A
                supporting_concepts: [CONCEPT_A, CONCEPT_B]
                conditions:
                  - concept: CONCEPT_A
                    band: SIDEWAYS
        """)
        with pytest.raises(KnowledgeValidationError):
            load_knowledge_base(_write_kb(tmp_path, rules=bad))

    def test_invalid_severity_raises(self, tmp_path):
        bad = textwrap.dedent("""\
            findings:
              - id: FINDING_A
                title: Finding A
                severity: EXTREME
                explanation: "..."
        """)
        with pytest.raises(KnowledgeValidationError):
            load_knowledge_base(_write_kb(tmp_path, findings=bad))

    def test_bad_band_threshold_ordering_raises(self, tmp_path):
        bad = textwrap.dedent("""\
            band_thresholds: {low_max: 0.80, high_min: 0.20}
            concepts:
              - id: CONCEPT_A
                direction: high_is_good
        """)
        with pytest.raises(KnowledgeValidationError):
            load_knowledge_base(_write_kb(tmp_path, concepts=bad))


class TestDuplicateIds:
    def test_duplicate_concept_id_raises(self, tmp_path):
        bad = textwrap.dedent("""\
            band_thresholds: {low_max: 0.35, high_min: 0.65}
            concepts:
              - id: CONCEPT_A
                direction: high_is_good
              - id: CONCEPT_A
                direction: high_is_bad
        """)
        with pytest.raises(KnowledgeValidationError):
            load_knowledge_base(_write_kb(tmp_path, concepts=bad))

    def test_duplicate_finding_id_raises(self, tmp_path):
        bad = textwrap.dedent("""\
            findings:
              - id: FINDING_A
                title: A
                severity: HIGH
                explanation: "..."
              - id: FINDING_A
                title: A2
                severity: LOW
                explanation: "..."
        """)
        with pytest.raises(KnowledgeValidationError):
            load_knowledge_base(_write_kb(tmp_path, findings=bad))

    def test_duplicate_rule_id_raises(self, tmp_path):
        bad = textwrap.dedent("""\
            rules:
              - id: RULE_A
                finding_id: FINDING_A
                supporting_concepts: [CONCEPT_A]
                conditions: [{concept: CONCEPT_A, band: HIGH}]
              - id: RULE_A
                finding_id: FINDING_A
                supporting_concepts: [CONCEPT_A]
                conditions: [{concept: CONCEPT_A, band: LOW}]
        """)
        with pytest.raises(KnowledgeValidationError):
            load_knowledge_base(_write_kb(tmp_path, rules=bad))

    def test_duplicate_recommendation_raises(self, tmp_path):
        bad = textwrap.dedent("""\
            recommendations:
              - finding_id: FINDING_A
                text: "First."
              - finding_id: FINDING_A
                text: "Second."
        """)
        with pytest.raises(KnowledgeValidationError):
            load_knowledge_base(_write_kb(tmp_path, recommendations=bad))


class TestCrossReferences:
    def test_rule_referencing_unknown_finding_raises(self, tmp_path):
        bad = textwrap.dedent("""\
            rules:
              - id: RULE_A
                finding_id: NO_SUCH_FINDING
                supporting_concepts: [CONCEPT_A, CONCEPT_B]
                conditions: [{concept: CONCEPT_A, band: HIGH}]
        """)
        with pytest.raises(KnowledgeValidationError, match="unknown finding_id"):
            load_knowledge_base(_write_kb(tmp_path, rules=bad))

    def test_condition_referencing_unknown_concept_raises(self, tmp_path):
        bad = textwrap.dedent("""\
            rules:
              - id: RULE_A
                finding_id: FINDING_A
                supporting_concepts: [CONCEPT_A, CONCEPT_B]
                conditions: [{concept: CONCEPT_ZZZ, band: HIGH}]
        """)
        with pytest.raises(KnowledgeValidationError, match="unknown concept"):
            load_knowledge_base(_write_kb(tmp_path, rules=bad))

    def test_condition_not_in_supporting_concepts_raises(self, tmp_path):
        bad = textwrap.dedent("""\
            rules:
              - id: RULE_A
                finding_id: FINDING_A
                supporting_concepts: [CONCEPT_A]
                conditions: [{concept: CONCEPT_B, band: LOW}]
        """)
        with pytest.raises(KnowledgeValidationError, match="not listed in supporting_concepts"):
            load_knowledge_base(_write_kb(tmp_path, rules=bad))

    def test_finding_without_recommendation_raises(self, tmp_path):
        with pytest.raises(KnowledgeValidationError, match="no entry in recommendations"):
            load_knowledge_base(_write_kb(tmp_path, recommendations="recommendations: []\n"))

    def test_recommendation_for_unknown_finding_raises(self, tmp_path):
        bad = textwrap.dedent("""\
            recommendations:
              - finding_id: FINDING_A
                text: "Do it."
              - finding_id: GHOST_FINDING
                text: "Ghost."
        """)
        with pytest.raises(KnowledgeValidationError, match="unknown finding_id"):
            load_knowledge_base(_write_kb(tmp_path, recommendations=bad))


class TestBusinessReasoningIntegration:
    def test_module_loads_default_kb_and_exposes_legacy_names(self):
        from universal_churn import business_reasoning as br
        assert callable(br.rule_retention_risk)
        assert callable(br.rule_retention_strength)
        assert callable(br.rule_dormant_customer)
        assert callable(br.rule_service_recovery_needed)
        assert br.rule_retention_risk in br.DEFAULT_RULES
        assert len(br.DEFAULT_RULES) == 4
        assert br.LOW_BAND_MAX == 0.35
        assert br.HIGH_BAND_MIN == 0.65

    def test_retention_risk_rule_fires_on_matching_inferences(self):
        from universal_churn import business_reasoning as br
        inferences = {
            "RECURRING_COMMITMENT": br.BusinessInference(
                concept_id="RECURRING_COMMITMENT", aggregate_value=0.1,
                band=br.ConceptBand.LOW, confidence=0.9, reconstructable=True,
                dependency_health="GOOD",
            ),
            "SUPPORT_FRICTION": br.BusinessInference(
                concept_id="SUPPORT_FRICTION", aggregate_value=0.9,
                band=br.ConceptBand.HIGH, confidence=0.9, reconstructable=True,
                dependency_health="GOOD",
            ),
        }
        finding = br.rule_retention_risk(inferences)
        assert finding is not None
        assert finding.finding_id == "RETENTION_RISK"
        assert finding.severity == br.Severity.HIGH
        assert finding.recommendation

    def test_rule_does_not_fire_on_insufficient_evidence(self):
        from universal_churn import business_reasoning as br
        inferences = {
            "RECURRING_COMMITMENT": br.BusinessInference(
                concept_id="RECURRING_COMMITMENT", aggregate_value=0.1,
                band=br.ConceptBand.LOW, confidence=0.0, reconstructable=False,
                dependency_health="POOR",
            ),
            "SUPPORT_FRICTION": br.BusinessInference(
                concept_id="SUPPORT_FRICTION", aggregate_value=0.9,
                band=br.ConceptBand.HIGH, confidence=0.9, reconstructable=True,
                dependency_health="GOOD",
            ),
        }
        assert br.rule_retention_risk(inferences) is None