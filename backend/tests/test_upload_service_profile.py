from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from backend.services import upload_service
from backend.services.upload_service import UploadService


def test_upload_profile_uses_dataset_values_and_framework_coverage(tmp_path: Path, monkeypatch):
    source = tmp_path / "customers.csv"
    source.write_text("Churn,Contract,MonthlyCharges\n0,Month-to-month,70.5\n1,One year,\n", encoding="utf-8")
    coverage = SimpleNamespace(
        summary=SimpleNamespace(overall_coverage=0.75, confidence_coverage=0.6, readiness="PARTIAL"),
        assessment=SimpleNamespace(
            issues=[SimpleNamespace(severity="HIGH", affected_items=("Contract",))],
            metrics=[SimpleNamespace(name="concept_coverage", score=0.5)],
        ),
    )
    monkeypatch.setattr(upload_service, "detect_sector", lambda _frame: "telecom")
    monkeypatch.setattr(upload_service, "infer_intelligence", lambda _frame: SimpleNamespace(coverage=coverage))

    result = UploadService().process_upload(source, "customers.csv")

    assert result["rows"] == 2
    assert result["columns"] == 3
    assert result["null_counts"]["MonthlyCharges"] == 1
    assert result["target_column"] == "Churn"
    assert result["missing_critical"] == ["Contract"]
    assert result["column_profiles"] == [
        {"name": "Churn", "inferredType": "numeric", "nullPercentage": 0.0, "sampleValues": ["0", "1"]},
        {"name": "Contract", "inferredType": "categorical", "nullPercentage": 0.0, "sampleValues": ["Month-to-month", "One year"]},
        {"name": "MonthlyCharges", "inferredType": "numeric", "nullPercentage": 50.0, "sampleValues": ["70.5"]},
    ]


def test_upload_profile_counts_whitespace_as_missing_and_infers_numeric_text(tmp_path: Path):
    source = tmp_path / "whitespace.csv"
    source.write_text("TotalCharges,Contract\n42.5,Month-to-month\n   ,One year\n", encoding="utf-8")
    frame = upload_service.pd.read_csv(source)

    profile = UploadService()._profile(frame)

    assert profile["null_counts"]["TotalCharges"] == 1
    total_charges = next(item for item in profile["column_profiles"] if item["name"] == "TotalCharges")
    assert total_charges["inferredType"] == "numeric"
    assert total_charges["nullPercentage"] == 50.0
    assert total_charges["sampleValues"] == ["42.5"]
    # Profiling is descriptive: the source frame passed to analysis is intact.
    assert frame["TotalCharges"].iloc[1] == "   "
