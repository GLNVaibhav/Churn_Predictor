"""Unit tests for Business Meaning Intelligence taxonomy inference."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from universal_churn.business_meaning import infer_business_meaning
from universal_churn.intelligence_pipeline import infer_intelligence
from universal_churn.semantic_schema import profile_column


# Representative columns that previously collapsed to GenericConcept.
# Names are generic business signals, not company- or dataset-specific.
_REPRESENTATIVE_COLUMNS = [
    ("LoyaltyScore", "CustomerLoyalty"),
    ("WishlistItems", "ProductPreference"),
    ("Returns", "ReturnBehaviour"),
    ("BrowsingTime", "DigitalEngagement"),
    ("CouponRewards", "RewardProgram"),
]


@pytest.mark.parametrize("column_name,expected_concept", _REPRESENTATIVE_COLUMNS)
def test_representative_columns_resolve_to_business_concepts(column_name, expected_concept):
    meaning = infer_business_meaning(profile_column(column_name))
    assert meaning.primary_business_concept != "GenericConcept"
    assert meaning.primary_business_concept == expected_concept
    assert meaning.confidence > 0.0


def test_generic_concept_receives_zero_confidence():
    meaning = infer_business_meaning(profile_column("XyzUnknownField"))
    assert meaning.primary_business_concept == "GenericConcept"
    assert meaning.confidence == 0.0


def test_singular_plural_keyword_matching():
    meaning = infer_business_meaning(profile_column("ProductReturns"))
    assert meaning.primary_business_concept == "ReturnBehaviour"


def test_telecom_knowledge_pack_priority_preserved():
    """Knowledge-pack resolution must still take precedence over taxonomy."""
    df = pd.read_csv(Path(__file__).resolve().parents[1] / "tests" / "telecom12.csv", nrows=5)
    result = infer_intelligence(df)
    generic = sum(
        1 for meaning in result.business_meanings
        if meaning.primary_business_concept == "GenericConcept"
    )
    assert generic == 0
    assert all(meaning.confidence >= 0.9 for meaning in result.business_meanings)


def test_ecommerce_representative_batch_avoids_generic_concept():
    columns = [name for name, _ in _REPRESENTATIVE_COLUMNS]
    generic = sum(
        1 for name in columns
        if infer_business_meaning(profile_column(name)).primary_business_concept == "GenericConcept"
    )
    assert generic == 0
