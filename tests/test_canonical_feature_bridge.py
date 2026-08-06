import pandas as pd

from universal_churn.canonical_feature_context import CanonicalFeatureAccess, CanonicalValueProvenance
from universal_churn.feature_engineering import FeaturePreparationPipeline
from universal_churn.intelligence_pipeline import infer_intelligence
from universal_churn.udif import DiagnosticLevel, UDIFRun


def test_context_consumes_schema_canonical_value_before_compatibility():
    raw = pd.DataFrame({'Tenure': [12, 24], 'CashbackAmount': [10.0, 20.0]})
    intelligence = infer_intelligence(raw)
    context = FeaturePreparationPipeline().run(
        raw, 'ecommerce', canonical_mapping_result=intelligence.canonical_mapping,
        coverage_summary=intelligence.coverage.summary,
    )
    binding = context.resolved_canonical_bindings['CustomerTenure']
    assert binding.source_column == 'Tenure'
    assert context.feature_provenance['tenure_normalized'].status == 'Resolved'


def test_legacy_lookup_is_explicit_compatibility_only():
    access = CanonicalFeatureAccess(
        pd.DataFrame(index=[0]), pd.DataFrame({'CouponUsed': [2]}), {},
    )
    assert access.require('CouponDependency').iloc[0] == 2
    assert access.used['CouponDependency'].resolution_type == 'compatibility'


def test_udif_prediction_coverage_uses_feature_provenance():
    raw = pd.DataFrame({'Tenure': [12], 'CashbackAmount': [10.0]})
    context = FeaturePreparationPipeline().run(raw, 'ecommerce')
    run = UDIFRun(DiagnosticLevel.STANDARD)
    run.capture_feature_preparation(context.pipeline_manifest)
    assert run.prediction_coverage is not None
    assert 0 <= run.prediction_coverage.score <= 1
    assert any(item.feature == 'tenure_normalized' for item in run.feature_provenance)
