"""Unit tests for Phase 3 metrics aggregation."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from tracenova_api.main import create_app
from tracenova_api.metrics import MetricsAggregator, calculate_p95
from tracenova_api.models import PipelineRun, PipelineStatus
from tracenova_config.settings import Settings


def test_calculate_p95() -> None:
    """Validate 95th percentile mathematical accuracy."""
    values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    p95 = calculate_p95(values)
    assert p95 == 95.5


def test_metrics_aggregator_mathematical_precision() -> None:
    """Validate summary metrics calculations for known runs."""
    pipeline_id = uuid4()
    start = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)

    runs = [
        PipelineRun(
            pipeline_id=pipeline_id,
            started_at=start,
            completed_at=start,
            duration_ms=600_000,
            status=PipelineStatus.SUCCESS,
            attempt=1,
        ),
        PipelineRun(
            pipeline_id=pipeline_id,
            started_at=start,
            completed_at=start,
            duration_ms=1_800_000,
            status=PipelineStatus.SUCCESS,
            attempt=1,
        ),
        PipelineRun(
            pipeline_id=pipeline_id,
            started_at=start,
            completed_at=start,
            duration_ms=300_000,
            status=PipelineStatus.FAILED,
            attempt=2,
        ),
    ]

    metrics = MetricsAggregator.calculate_metrics(pipeline_id, runs)

    assert metrics.total_runs == 3
    assert metrics.successful_runs == 2
    assert metrics.failed_runs == 1
    assert metrics.retried_runs == 1
    assert metrics.success_rate == 0.6667
    assert metrics.failure_rate == 0.3333
    assert metrics.retry_rate == 0.3333
    assert metrics.avg_duration_ms == 900_000.0
    assert metrics.median_duration_ms == 600_000.0


def test_metrics_api_endpoints() -> None:
    """API endpoints return valid pipeline metrics and timeseries."""
    client = TestClient(create_app(Settings()))

    # Create pipeline
    create_res = client.post(
        "/pipelines",
        json={
            "name": "metrics_test_pipe",
            "owner": "data-team",
            "schedule": "0 * * * *",
            "dependencies": [],
        },
    )
    pipeline_id = create_res.json()["id"]

    # Run normal scenario
    client.post(
        f"/pipelines/{pipeline_id}/run",
        json={"scenario": "normal", "started_at": "2026-01-10T10:00:00Z"},
    )

    # Test summary metrics endpoint
    metrics_res = client.get(f"/metrics/pipelines/{pipeline_id}")
    assert metrics_res.status_code == 200
    m_body = metrics_res.json()
    assert m_body["pipeline_id"] == pipeline_id
    assert m_body["total_runs"] == 1
    assert m_body["successful_runs"] == 1
    assert m_body["success_rate"] == 1.0

    # Test timeseries endpoint
    ts_res = client.get(f"/metrics/pipelines/{pipeline_id}/timeseries")
    assert ts_res.status_code == 200
    ts_body = ts_res.json()
    assert len(ts_body) == 1
    assert ts_body[0]["duration_ms"] == 600_000.0
    assert ts_body[0]["status"] == "SUCCESS"


def test_metrics_unknown_pipeline_returns_404() -> None:
    """Metrics request for missing pipeline returns 404."""
    client = TestClient(create_app(Settings()))
    missing_id = "00000000-0000-0000-0000-000000000099"

    res = client.get(f"/metrics/pipelines/{missing_id}")
    assert res.status_code == 404

    res_ts = client.get(f"/metrics/pipelines/{missing_id}/timeseries")
    assert res_ts.status_code == 404
