from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from backend.api.routers.upload import upload_file
from backend.api.routers.analysis import AnalyzeRequest, start_analysis
from backend.api.auth import CurrentUser
from backend.runtime.manager import ExecutionManager
from backend.services.upload_storage import FilesystemUploadStorage
from backend.api.routers.upload import delete_upload
from backend.config import settings


class MemoryRepository:
    def __init__(self) -> None:
        self.records: dict[str, dict] = {}

    def save(self, key: str, value: dict) -> None:
        self.records[key] = value

    def load(self, key: str):
        return self.records.get(key)

    def delete(self, key: str) -> bool:
        return self.records.pop(key, None) is not None


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
            "column_profiles": [{"name": "Churn", "inferredType": "numeric", "nullPercentage": 0.0, "sampleValues": ["0"]}],
            "target_column": "Churn",
            "missing_critical": ["Contract"],
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
            user=CurrentUser("test-user"),
            storage=FilesystemUploadStorage(upload_root),
        )
    )

    assert response.filename == "customer.csv"
    assert response.rows == 1
    assert response.columns == 2
    assert response.column_profiles == [{"name": "Churn", "inferredType": "numeric", "nullPercentage": 0.0, "sampleValues": ["0"]}]
    assert response.target_column == "Churn"
    assert response.missing_critical == ["Contract"]
    assert response.upload_id in repository.records
    assert repository.records[response.upload_id]["owner_id"] == "test-user"
    assert (upload_root / response.upload_id / "customer.csv").is_file()
    assert not (upload_root.parent / "customer.csv").exists()


def test_upload_delete_is_owner_scoped(upload_context):
    repository, upload_root = upload_context
    storage = FilesystemUploadStorage(upload_root)
    key = storage.save("owned-upload", "customers.csv", b"id,churn\n1,0\n")
    repository.save("owned-upload", {
        "upload_id": "owned-upload",
        "owner_id": "owner-one",
        "filename": "customers.csv",
        "storage_key": key,
    })

    with pytest.raises(HTTPException) as exc_info:
        delete_upload("owned-upload", repo=repository, storage=storage, user=CurrentUser("owner-two"))
    assert exc_info.value.status_code == 404
    assert (upload_root / "owned-upload" / "customers.csv").exists()

    response = delete_upload("owned-upload", repo=repository, storage=storage, user=CurrentUser("owner-one"))
    assert response.status_code == 204
    assert repository.load("owned-upload") is None
    assert not (upload_root / "owned-upload" / "customers.csv").exists()


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
                user=CurrentUser("test-user"),
                storage=FilesystemUploadStorage(upload_root),
            )
        )

    assert exc_info.value.status_code == expected_status
    assert repository.records == {}
    assert list(upload_root.iterdir()) == []


def test_analysis_response_reports_the_persisted_initial_pending_state(tmp_path: Path):
    repository = MemoryRepository()
    storage = FilesystemUploadStorage(tmp_path)
    storage_key = storage.save("upload-1", "customers.csv", b"Churn\n0\n")
    repository.save("upload-1", {
        "upload_id": "upload-1",
        "owner_id": "test-user",
        "filename": "customers.csv",
        "storage_key": storage_key,
    })

    manager = ExecutionManager(repository)
    response = asyncio.run(start_analysis(
        AnalyzeRequest(upload_id="upload-1"),
        repo=repository,
        manager=manager,
        user=CurrentUser("test-user"),
        storage=storage,
    ))

    assert response.execution_id in repository.records
    assert response.status in {"PENDING", "RUNNING"}
