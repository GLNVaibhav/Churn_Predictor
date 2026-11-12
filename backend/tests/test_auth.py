from fastapi.testclient import TestClient
import pytest

from backend.api.app import create_app
from backend.api.dependencies import get_execution_repository
from backend.config import settings

TEST_PROXY_SECRET = "unit-test-proxy-secret-with-sufficient-length"


class OwnedRepository:
    def list_executions(self):
        return [
            {"execution_id": "one", "owner_id": "user-one", "status": "SUCCEEDED"},
            {"execution_id": "two", "owner_id": "user-two", "status": "SUCCEEDED"},
        ]

    def load(self, execution_id):
        return {
            "execution_id": execution_id,
            "owner_id": "user-two",
            "status": "SUCCEEDED",
        }


def test_protected_execution_routes_reject_missing_or_invalid_proxy_identity(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_MODE", "production")
    monkeypatch.setattr(settings, "UCIF_PROXY_SECRET", TEST_PROXY_SECRET)
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://configured-for-test")
    monkeypatch.setattr(settings, "OBJECT_STORAGE_BACKEND", "s3")
    monkeypatch.setattr(settings, "S3_BUCKET", "configured-for-test")
    app = create_app()
    app.dependency_overrides[get_execution_repository] = OwnedRepository
    client = TestClient(app)

    assert client.get("/api/v1/executions").status_code == 401
    assert client.get("/api/v1/executions", headers={
        "x-ucif-proxy-secret": "wrong", "x-ucif-user-id": "user-one",
    }).status_code == 401


def test_execution_history_and_details_are_scoped_to_authenticated_user(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_MODE", "production")
    monkeypatch.setattr(settings, "UCIF_PROXY_SECRET", TEST_PROXY_SECRET)
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://configured-for-test")
    monkeypatch.setattr(settings, "OBJECT_STORAGE_BACKEND", "s3")
    monkeypatch.setattr(settings, "S3_BUCKET", "configured-for-test")
    app = create_app()
    app.dependency_overrides[get_execution_repository] = OwnedRepository
    client = TestClient(app)
    headers = {"x-ucif-proxy-secret": TEST_PROXY_SECRET, "x-ucif-user-id": "user-one"}

    response = client.get("/api/v1/executions", headers=headers)
    assert response.status_code == 200
    assert [item["execution_id"] for item in response.json()] == ["one"]
    assert client.get("/api/v1/analysis/two", headers=headers).status_code == 404


def test_local_development_mode_remains_available_without_proxy_secret(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_MODE", "development")
    monkeypatch.setattr(settings, "UCIF_PROXY_SECRET", "")
    app = create_app()
    app.dependency_overrides[get_execution_repository] = OwnedRepository
    assert TestClient(app).get("/api/v1/executions").status_code == 200


def test_production_configuration_fails_closed_without_durable_storage(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_MODE", "production")
    monkeypatch.setattr(settings, "UCIF_PROXY_SECRET", "")
    monkeypatch.setattr(settings, "DATABASE_URL", "")
    monkeypatch.setattr(settings, "OBJECT_STORAGE_BACKEND", "filesystem")
    monkeypatch.setattr(settings, "S3_BUCKET", "")
    with pytest.raises(RuntimeError, match="Production API configuration is incomplete"):
        create_app()
