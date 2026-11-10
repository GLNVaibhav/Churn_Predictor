from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from backend.api.routers.upload import upload_file
from backend.config import settings


class MemoryRepository:
    def __init__(self) -> None:
        self.records: dict[str, dict] = {}

    def save(self, key: str, value: dict) -> None:
        self.records[key] = value


class InspectingUploadService:
    def process_upload(self, path: Path, filename: str) -> dict:
        assert path.is_file()
        assert path.name == filename
        return {
            "filename": filename,
            "rows": 1,
            "columns": 2,
            "null_counts": {"Churn": 0},
            "dtypes": {"Churn": "int64"},
            "sector": "telecom",
            "coverage_score": 0.8,
            "concept_confidence": 0.7,
            "preview_rows": [{"Churn": 0}],
            "warnings": [],
            "created_at": "2026-11-10T00:00:00Z",
        }


@pytest.fixture
def upload_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repository = MemoryRepository()
    monkeypatch.setattr(settings, "UPLOAD_ROOT", tmp_path)
    return repository, tmp_path


def test_upload_accepts_csv_and_stores_only_the_basename(upload_context):
    repository, upload_root = upload_context
    response = asyncio.run(
        upload_file(
            file=UploadFile(file=BytesIO(b"CustomerID,Churn\n1,0\n"), filename="../nested/customer.csv"),
            repo=repository,
            service=InspectingUploadService(),
        )
    )

    assert response.filename == "customer.csv"
    assert response.rows == 1
    assert response.columns == 2
    assert response.upload_id in repository.records
    assert (upload_root / response.upload_id / "customer.csv").is_file()
    assert not (upload_root.parent / "customer.csv").exists()


@pytest.mark.parametrize(
    ("filename", "content", "limit", "expected_status"),
    [
        ("customers.txt", b"a,b\n1,2\n", 64, 400),
        ("empty.csv", b"", 64, 400),
        ("large.csv", b"a" * 17, 16, 413),
    ],
)
def test_upload_rejects_invalid_or_oversized_files(upload_context, monkeypatch, filename, content, limit, expected_status):
    repository, upload_root = upload_context
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", limit)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            upload_file(
                file=UploadFile(file=BytesIO(content), filename=filename),
                repo=repository,
                service=InspectingUploadService(),
            )
        )

    assert exc_info.value.status_code == expected_status
    assert repository.records == {}
    assert list(upload_root.iterdir()) == []
