import pandas as pd

from universal_churn.intelligence_pipeline import infer_intelligence
from universal_churn.semantic_feature_resolver import FeatureResolverPipeline


def test_resolver_binds_saved_feature_from_intelligence_not_input_header_equality():
    # The input column is not named Balance.  Its meaning is nevertheless an
    # account balance and is bound through BusinessMeaning/CanonicalMapping.
    frame = pd.DataFrame({"Account Balance Value": [50000, 12000]})
    intelligence = infer_intelligence(frame)
    result = FeatureResolverPipeline().run(frame, intelligence, ["Balance"])

    binding = result.bindings[0]
    assert binding.source_column == "Account Balance Value"
    assert binding.provenance.business_meaning == "AccountBalance"
    assert binding.provenance.canonical_concept == "Account"
    assert binding.provenance.transformation.name == "identity"
    assert binding.provenance.missing_reason is None


def test_resolver_reports_auditable_default_when_no_semantic_binding_exists():
    frame = pd.DataFrame({"Unrelated Signal": [1, 2]})
    intelligence = infer_intelligence(frame)
    result = FeatureResolverPipeline().run(frame, intelligence, ["MonthlyCharges"])

    binding = result.bindings[0]
    assert binding.source_column is None
    assert binding.provenance.transformation.name == "default"
    assert binding.provenance.missing_reason
    assert result.default_feature_count == 1
    assert result.feature_coverage == 0.0
