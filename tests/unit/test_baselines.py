"""Unit tests for Phase 4 historical baselines."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from tracenova_api.baselines import BaselineEngine
from tracenova_api.main import create_app
from tracenova_api.metrics import MetricsAggregator
from tracenova_api.models import PipelineRun, PipelineStatus
from tracenova_config.settings import Settings


def test_calculate_baseline_empty_runs() -> None:
    """Empty runs produce a default baseline."""
    pipeline_id = uuid4()
    baseline = BaselineEngine.calculate_baseline(pipeline_id, [])

    assert baseline.pipeline_id == pipeline_id
    assert baseline.sample_size == 0
    assert baseline.median_duration_ms == 0.0


def test_baseline_comparison_ratios() -> None:
    """Validate baseline comparison ratios and differences.

    Baseline excludes failed/retried runs, so this uses only clean SUCCESS/attempt=1
    runs to assert the self-consistency identity (current == baseline -> ratio 1.0).
    """
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
            duration_ms=1_200_000,
            status=PipelineStatus.SUCCESS,
            attempt=1,
        ),
    ]

    current_metrics = MetricsAggregator.calculate_metrics(pipeline_id, runs)
    baseline = BaselineEngine.calculate_baseline(pipeline_id, runs)

    comparison = BaselineEngine.compare(current_metrics, baseline)

    assert comparison.pipeline_id == pipeline_id
    assert comparison.duration_ratio == 1.0
    assert comparison.failure_rate_diff == 0.0
    assert comparison.retry_rate_diff == 0.0
    assert comparison.throughput_ratio == 1.0


def test_baseline_excludes_failed_and_retried_runs() -> None:
    """Baseline is computed only from SUCCESS/attempt=1 runs when any exist."""
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
            duration_ms=1_200_000,
            status=PipelineStatus.FAILED,
            attempt=2,
        ),
    ]

    baseline = BaselineEngine.calculate_baseline(pipeline_id, runs)

    assert baseline.sample_size == 1
    assert baseline.median_duration_ms == 600_000.0
    assert baseline.failure_rate == 0.0
    assert baseline.retry_rate == 0.0


def test_baseline_api_endpoints() -> None:
    """API endpoints return calculated baseline and baseline comparison."""
    client = TestClient(create_app(Settings()))

    # Create pipeline
    create_res = client.post(
        "/pipelines",
        json={
            "name": "baseline_test_pipe",
            "owner": "analytics",
            "schedule": "0 0 * * *",
            "dependencies": [],
        },
    )
    pipeline_id = create_res.json()["id"]

    # Run normal scenario
    client.post(
        f"/pipelines/{pipeline_id}/run",
        json={"scenario": "normal", "started_at": "2026-01-10T10:00:00Z"},
    )

    # Test baseline endpoint
    b_res = client.get(f"/pipelines/{pipeline_id}/baseline")
    assert b_res.status_code == 200
    b_body = b_res.json()
    assert b_body["pipeline_id"] == pipeline_id
    assert b_body["sample_size"] == 1
    assert b_body["median_duration_ms"] == 600_000.0

    # Test comparison endpoint
    c_res = client.get(f"/pipelines/{pipeline_id}/baseline/compare")
    assert c_res.status_code == 200
    c_body = c_res.json()
    assert c_body["duration_ratio"] == 1.0
    assert c_body["failure_rate_diff"] == 0.0


def test_baseline_unknown_pipeline_returns_404() -> None:
    """Baseline endpoints return 404 for non-existent pipeline."""
    client = TestClient(create_app(Settings()))
    missing_id = "00000000-0000-0000-0000-000000000088"

    assert client.get(f"/pipelines/{missing_id}/baseline").status_code == 404
    assert client.get(f"/pipelines/{missing_id}/baseline/compare").status_code == 404