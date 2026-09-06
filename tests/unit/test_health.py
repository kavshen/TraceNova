"""Tests for Phase 0 API health behavior."""

from fastapi.testclient import TestClient
from tracenova_api.main import create_app
from tracenova_config.settings import Settings


def test_health_endpoint_reports_service_status() -> None:
    client = TestClient(create_app(Settings(environment="test")))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "api",
        "environment": "test",
    }

