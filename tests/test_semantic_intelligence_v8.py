from __future__ import annotations
import pandas as pd

from universal_churn.semantic_intelligence import SemanticUnderstandingEngine
from universal_churn.semantic_intelligence.domain.enums import ExecutionMode, ResolutionStatus
from universal_churn.semantic_intelligence.governance.run_manifest import SemanticRunManifest
from universal_churn.semantic_intelligence.governance.replay_service import ReplayService
from universal_churn.schema_resolution import resolve_schema
from universal_churn.semantic_intelligence.application.capability_assessment_service import CapabilityAssessmentService
from universal_churn.semantic_intelligence.domain.identifiers import OntologyId


def test_v8_resolves_meaning_before_legacy_projection():
    raw = pd.DataFrame({"customer_tenure_months": [1, 2, 3]})
    result = SemanticUnderstandingEngine().understand(raw, ExecutionMode.DIAGNOSTIC)
    resolution = result.resolutions[0]
    assert resolution.status == ResolutionStatus.SEMANTIC_ACCEPTED
    assert resolution.business_meaning.selected is not None
    assert resolution.assignment.canonical_id is not None
    assert resolution.confidence.probability < 0.8


def test_v8_deterministic_precedence_is_immutable():
    raw = pd.DataFrame({"tenure": [1, 2]})
    _, deterministic = resolve_schema(raw)
    result = SemanticUnderstandingEngine().understand(raw, ExecutionMode.DIAGNOSTIC, deterministic_resolutions={r.raw_column: r for r in deterministic})
    resolution = result.resolutions[0]
    assert resolution.status == ResolutionStatus.DETERMINISTIC_EXACT
    assert resolution.deterministic_canonical_field == "Tenure_Raw"
    assert resolution.confidence.probability == 1.0


def test_legacy_default_semantic_path_uses_v8_for_unresolved_column():
    raw = pd.DataFrame({"relationship_duration": [1, 2]})
    resolved, results = resolve_schema(raw, enable_semantic=True)
    assert results[0].method == "semantic"
    assert results[0].confidence < 0.8
    assert "Tenure_Raw" in resolved.columns


def test_v8_replay_requires_identical_fingerprint():
    raw = pd.DataFrame({"customer_tenure_months": [1, 2]})
    result = SemanticUnderstandingEngine().understand(raw, ExecutionMode.DIAGNOSTIC)
    manifest = SemanticRunManifest(result.run_id, result.fingerprint, result.artifact_versions, "DIAGNOSTIC")
    replayed = ReplayService().replay(raw, manifest)
    assert replayed.fingerprint == result.fingerprint


def test_capabilities_are_dataset_level_not_column_level():
    raw = pd.DataFrame({"customer_tenure_months": [1, 2], "monthly_charges": [10, 20]})
    schema = SemanticUnderstandingEngine().understand(raw, ExecutionMode.DIAGNOSTIC)
    assessment = CapabilityAssessmentService().assess(schema, OntologyId("ucif.capability.churn_risk_assessment"), (OntologyId("ucif.meaning.customer.relationship.tenure"), OntologyId("ucif.meaning.financial.recurring_charge")))
    assert assessment.capability_id.value == "ucif.capability.churn_risk_assessment"
    assert assessment.confidence > 0
