from backend.runtime.repository import ExecutionRepository
from backend.api.routers.executions import _load_execution
from fastapi import HTTPException
import pytest


def test_execution_history_excludes_upload_profiles(tmp_path):
    repository = ExecutionRepository(str(tmp_path))
    repository.save("upload-1", {
        "upload_id": "upload-1",
        "filename": "customers.csv",
        "rows": 20,
        "columns": 4,
    })
    repository.save("run-1", {
        "execution_id": "run-1",
        "status": "SUCCEEDED",
        "created_at": "2026-11-10T00:00:00Z",
        "dataset": {"filename": "customers.csv", "sector": "telecom"},
    })

    assert repository.list_executions() == [{
        "execution_id": "run-1",
        "status": "SUCCEEDED",
        "created_at": "2026-11-10T00:00:00Z",
        "started_at": None,
        "completed_at": None,
        "execution_time_ms": None,
        "filename": "customers.csv",
        "sector": "telecom",
        "progress": None,
    }]


def test_upload_profile_is_not_an_execution_detail():
    class UploadOnlyRepository:
        def load(self, execution_id: str) -> dict:
            return {"upload_id": execution_id, "filename": "customers.csv", "rows": 20}

    with pytest.raises(HTTPException) as exc_info:
        _load_execution("upload-1", UploadOnlyRepository())

    assert exc_info.value.status_code == 404
