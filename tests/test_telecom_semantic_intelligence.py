import pandas as pd

from universal_churn.intelligence_pipeline import infer_intelligence


def test_standard_telecom_measures_resolve_to_distinct_canonical_concepts():
    """Generic telecom measures must not collapse into GenericConcept/Complaint."""
    df = pd.DataFrame({
        "Recharge_Value": [120.0, 250.0, 180.0],
        "ARPU": [160.0, 230.0, 200.0],
        "SMS_Count": [10, 5, 8],
        "Complaint_Count": [0, 1, 0],
        "Days_Since_Last_Recharge": [4, 20, 7],
        "Broadband_User": [1, 0, 1],
        "Voice_Minutes": [100, 40, 70],
    })

    result = infer_intelligence(df)
    meanings = {column: meaning for column, meaning in zip(df.columns, result.business_meanings)}
    canonical = {
        column: mapping.chosen_concept.name
        for column, mapping in zip(df.columns, result.canonical_mapping.mappings)
    }

    assert all(meaning.domain == "Telecom" for meaning in meanings.values())
    assert all(meaning.confidence >= 0.9 for meaning in meanings.values())
    assert canonical == {
        "Recharge_Value": "RecurringRevenue",
        "ARPU": "AverageRevenuePerUser",
        "SMS_Count": "MessagingUsage",
        "Complaint_Count": "SupportContacts",
        "Days_Since_Last_Recharge": "ActivityRecency",
        "Broadband_User": "ProductPortfolio",
        "Voice_Minutes": "VoiceUsage",
    }
    assert result.coverage.summary.semantic_coverage >= 0.8
    assert result.coverage.summary.confidence_coverage >= 0.7
    assert result.routing.decision.selected_pipeline == "TelecomPipeline"
    assert result.routing.decision.fallback_used is False
