import pandas as pd

from universal_churn.universal_dataset_builder import (
    DatasetInput,
    DatasetReadiness,
    DatasetValidationConfig,
    build_universal_training_dataset,
)


def _airtel_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "Recharge_Value": [163.0, 391.0],
        "Days_Since_Last_Recharge": [35, 25],
        "Avg_Monthly_Data_GB": [18.2, 31.5],
        "Voice_Minutes": [111, 969],
        "SMS_Count": [23, 150],
        "Complaint_Count": [2, 1],
        "Broadband_User": ["No", "Yes"],
        "ARPU": [163.0, 391.0],
        "Churn": ["No", "Yes"],
    })


def test_builder_aligns_canonical_order_and_exports_no_raw_feature_columns(tmp_path):
    dataset = build_universal_training_dataset(
        [DatasetInput("Airtel", _airtel_frame(), "Churn")], sector="telecom",
    )
    assert dataset.accepted_origins == ("Airtel",)
    assert tuple(dataset.rows.columns[:len(dataset.canonical_features)]) == dataset.canonical_features
    assert "Recharge_Value" not in dataset.rows.columns
    assert "Voice_Minutes" not in dataset.rows.columns
    assert "Target" in dataset.rows.columns
    assert all(f"Confidence__{name}" in dataset.rows for name in dataset.canonical_features)
    assert dataset.rows["DatasetOrigin"].eq("Airtel").all()

    output = dataset.export_csv(tmp_path / "Universal_Telecom_Training.csv")
    report = dataset.export_quality_report(tmp_path / "telecom_quality.json")
    assert output.exists() and report.exists()
    assert "Recharge_Value" not in output.read_text(encoding="utf-8").splitlines()[0]


def test_insufficient_dataset_is_retained_in_quality_report_but_excluded_from_rows():
    raw = pd.DataFrame({"unknown_metric": [1, 2], "Churn": [0, 1]})
    dataset = build_universal_training_dataset(
        [DatasetInput("Unknown", raw, "Churn")], sector="telecom",
    )
    assert dataset.rows.empty
    assert dataset.rejected_origins == ("Unknown",)
    assert dataset.dataset_reports[0].training_readiness in {
        DatasetReadiness.INSUFFICIENT, DatasetReadiness.REJECTED,
    }


def test_critical_concepts_can_be_governed_without_fabricating_them():
    dataset = build_universal_training_dataset(
        [DatasetInput("Airtel", _airtel_frame(), "Churn")], sector="telecom",
        validation_config=DatasetValidationConfig(critical_features=("CustomerTenure",)),
    )
    result = dataset.validation_results[0]
    assert result.readiness is DatasetReadiness.INSUFFICIENT
    assert result.accepted is False
    assert "CustomerTenure" in result.missing_critical_concepts
