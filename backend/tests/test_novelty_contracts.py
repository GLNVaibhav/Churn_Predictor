from __future__ import annotations

import pandas as pd

from universal_churn.intelligence_pipeline import infer_intelligence
from universal_churn.routing import DecisionFactor, RoutingCandidate, _FACTOR_WEIGHTS


def test_canonical_mapping_preserves_original_source_column_names():
    frame = pd.DataFrame({
        "Customer_ID": ["c1", "c2", "c3"],
        "Tenure_Months": [4, 12, 20],
        "Monthly_Charges": [35.0, 52.0, 71.0],
    })

    result = infer_intelligence(frame)

    assert [mapping.column_name for mapping in result.canonical_mapping.mappings] == list(frame.columns)
    assert [meaning.supporting_features["source_column"] for meaning in result.business_meanings] == list(frame.columns)


def test_routing_score_weights_match_documented_prior_and_factor_budget():
    assert sum(_FACTOR_WEIGHTS.values()) == 0.60
    factors = tuple(
        DecisionFactor(name=name, score=0.5, weight=weight, reasoning="test")
        for name, weight in _FACTOR_WEIGHTS.items()
    )
    candidate = RoutingCandidate(
        pipeline_name="TelecomPipeline",
        base_score=0.9,
        reasoning="test",
        factors=factors,
    )

    assert candidate.final_score == 0.66
