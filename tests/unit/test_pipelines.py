"""Tests for Phase 1 pipeline endpoints."""

from fastapi.testclient import TestClient
from tracenova_api.main import create_app
from tracenova_config.settings import Settings


def create_pipeline(client: TestClient) -> str:
    """Create a pipeline and return its ID."""
    response = client.post(
        "/pipelines",
        json={
            "name": "orders_daily",
            "owner": "data-platform",
            "schedule": "0 2 * * *",
            "dependencies": ["orders_db"],
        },
    )

    assert response.status_code == 201
    return str(response.json()["id"])


def test_create_pipeline() -> None:
    """A client can create a pipeline."""
    client = TestClient(create_app(Settings()))

    pipeline_id = create_pipeline(client)

    assert pipeline_id


def test_list_pipelines() -> None:
    """A client can retrieve created pipelines."""
    client = TestClient(create_app(Settings()))

    create_pipeline(client)
    response = client.get("/pipelines")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "orders_daily"


def test_run_normal_pipeline() -> None:
    """A normal simulation creates a successful run and two events."""
    client = TestClient(create_app(Settings()))
    pipeline_id = create_pipeline(client)

    response = client.post(
        f"/pipelines/{pipeline_id}/run",
        json={
            "scenario": "normal",
            "started_at": "2026-01-10T10:00:00Z",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert len(body["runs"]) == 1
    assert body["runs"][0]["status"] == "SUCCESS"
    assert body["runs"][0]["duration_ms"] == 600_000
    assert [event["event_type"] for event in body["events"]] == [
        "PIPELINE_STARTED",
        "PIPELINE_COMPLETED",
    ]


def test_list_pipeline_runs() -> None:
    """A client can retrieve execution history for one pipeline."""
    client = TestClient(create_app(Settings()))
    pipeline_id = create_pipeline(client)

    client.post(
        f"/pipelines/{pipeline_id}/run",
        json={"scenario": "failure", "started_at": "2026-01-10T10:00:00Z"},
    )
    response = client.get(f"/pipelines/{pipeline_id}/runs")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "FAILED"


def test_unknown_pipeline_returns_404() -> None:
    """Runs cannot be generated for a missing pipeline."""
    client = TestClient(create_app(Settings()))

    response = client.post(
        "/pipelines/00000000-0000-0000-0000-000000000001/run",
        json={"scenario": "normal"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Pipeline not found."