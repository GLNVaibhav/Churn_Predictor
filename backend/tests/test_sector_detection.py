import pandas as pd
import pytest

from universal_churn.preprocessing import detect_sector, sector_signature_scores


@pytest.mark.parametrize(
    ("columns", "expected"),
    [
        (["Tenure_Months", "ARPU", "Days_Since_Recharge", "Network_Quality"], "telecom"),
        (["Orders_Last_Year", "Days_Since_Last_Order", "Annual_Spend", "Wishlist_Count"], "ecommerce"),
        (["CreditScore", "Geography", "NumOfProducts", "Exited"], "banking"),
        (["PatientID", "Visits_Last_Year", "Missed_Appointments", "Churned"], "healthcare"),
    ],
)
def test_sector_detection_recognizes_domain_schema_aliases(columns, expected):
    frame = pd.DataFrame(columns=columns)
    assert detect_sector(frame) == expected


def test_sector_detection_reports_scores_and_refuses_ambiguous_schema():
    frame = pd.DataFrame(columns=[
        "Tenure_Months", "ARPU", "CreditScore", "NumOfProducts",
    ])
    scores = sector_signature_scores(frame)
    assert scores["telecom"] == 2
    assert scores["banking"] == 2
    with pytest.raises(ValueError, match="Ambiguous sector match"):
        detect_sector(frame)


def test_sector_detection_refuses_schema_without_domain_evidence():
    with pytest.raises(ValueError, match="Could not auto-detect sector"):
        detect_sector(pd.DataFrame(columns=["age", "gender", "customer_id"]))
