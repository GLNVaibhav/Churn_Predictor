import pandas as pd

from universal_churn.canonical_feature_builder import (
    build_canonical_feature_set,
    load_canonical_feature_specifications,
)
from universal_churn.compatibility_intelligence import (
    CompatibilityLevel,
    evaluate_compatibility,
)
from universal_churn.intelligence_pipeline import infer_intelligence
from universal_churn.training_readiness import build_training_readiness_report


def test_every_supported_sector_has_a_v2_canonical_feature_contract():
    for sector in ("telecom", "banking", "healthcare", "ecommerce"):
        specifications = load_canonical_feature_specifications(sector)
        assert specifications
        assert all(item.description and item.supported_raw_concepts for item in specifications)


def test_airtel_semantics_build_canonical_features_without_legacy_substitution():
    raw = pd.DataFrame({
        "Recharge_Value": [163.0, 391.0],
        "Days_Since_Last_Recharge": [35, 25],
        "Voice_Minutes": [111, 969],
        "SMS_Count": [23, 150],
        "Complaint_Count": [2, 1],
        "Broadband_User": ["No", "Yes"],
        "ARPU": [163.0, 391.0],
    })
    intelligence = infer_intelligence(raw)
    feature_set = build_canonical_feature_set(
        raw, intelligence.business_meanings, intelligence.canonical_mapping,
        intelligence.semantic_graph, intelligence.coverage, sector="telecom",
    )

    assert feature_set.feature("RecurringRevenue").status == "Derived"
    assert feature_set.feature("VoiceUsage").status == "Available"
    assert feature_set.feature("MessagingUsage").status == "Available"
    assert feature_set.feature("CustomerTenure").status == "Unsupported"
    assert feature_set.feature("CustomerTenure").value.isna().all()

    compatibility = evaluate_compatibility(feature_set)
    report = build_training_readiness_report(feature_set, compatibility)
    assert compatibility.legacy_sector_model is None
    assert "CustomerTenure" in report.missing_business_concepts
    assert "VoiceUsage" in report.feature_provenance


def test_legacy_evaluation_never_uses_canonical_features_as_legacy_columns():
    raw = pd.DataFrame({"Voice_Minutes": [1, 2], "SMS_Count": [3, 4]})
    intelligence = infer_intelligence(raw)
    feature_set = build_canonical_feature_set(
        raw, intelligence.business_meanings, intelligence.canonical_mapping,
        intelligence.semantic_graph, intelligence.coverage, sector="telecom",
    )
    assessment = evaluate_compatibility(
        feature_set, legacy_required_features=("tenure", "MonthlyCharges", "TotalCharges"),
    )
    assert assessment.legacy_sector_model is CompatibilityLevel.INCOMPATIBLE
