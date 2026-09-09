"""Unit tests for Phase 5 degradation detection."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from tracenova_api.degradation import DegradationDetector
from tracenova_api.main import create_app
from tracenova_api.models import (
    BaselineComparison,
    PipelineBaseline,
    PipelineMetrics,
    SignalSeverity,
    SignalType,
)
from tracenova_config.settings import Settings


def test_normal_comparison_emits_no_signals() -> None:
    """Normal baseline comparison produces zero degradation signals."""
    pipeline_id = uuid4()
    metrics = PipelineMetrics(
        pipeline_id=pipeline_id,
        median_duration_ms=600_000.0,
        failure_rate=0.0,
        retry_rate=0.0,
        throughput_per_minute=1.0,
    )
    baseline = PipelineBaseline(
        pipeline_id=pipeline_id,
        sample_size=10,
        median_duration_ms=600_000.0,
        failure_rate=0.0,
        retry_rate=0.0,
        throughput_per_minute=1.0,
        calculated_at=datetime.now(UTC),
    )
    comparison = BaselineComparison(
        pipeline_id=pipeline_id,
        current_metrics=metrics,
        baseline=baseline,
        duration_ratio=1.0,
        failure_rate_diff=0.0,
        retry_rate_diff=0.0,
        throughput_ratio=1.0,
    )

    detector = DegradationDetector()
    report = detector.evaluate(comparison)

    assert report.is_degraded is False
    assert len(report.signals) == 0


def test_slow_duration_emits_duration_degradation_signal() -> None:
    """High duration ratio produces DURATION_DEGRADATION signal."""
    pipeline_id = uuid4()
    metrics = PipelineMetrics(pipeline_id=pipeline_id, median_duration_ms=1_800_000.0)
    baseline = PipelineBaseline(
        pipeline_id=pipeline_id,
        sample_size=10,
        median_duration_ms=600_000.0,
        calculated_at=datetime.now(UTC),
    )
    comparison = BaselineComparison(
        pipeline_id=pipeline_id,
        current_metrics=metrics,
        baseline=baseline,
        duration_ratio=3.0,
    )

    detector = DegradationDetector()
    report = detector.evaluate(comparison)

    assert report.is_degraded is True
    assert len(report.signals) == 1
    sig = report.signals[0]
    assert sig.signal_type == SignalType.DURATION_DEGRADATION
    assert sig.severity == SignalSeverity.HIGH
    assert sig.deviation == 3.0


def test_failure_and_retry_storm_emit_signals() -> None:
    """Increased failure and retry rates emit corresponding signals."""
    pipeline_id = uuid4()
    metrics = PipelineMetrics(
        pipeline_id=pipeline_id,
        failure_rate=0.25,
        retry_rate=0.50,
    )
    baseline = PipelineBaseline(
        pipeline_id=pipeline_id,
        sample_size=10,
        failure_rate=0.0,
        retry_rate=0.0,
        calculated_at=datetime.now(UTC),
    )
    comparison = BaselineComparison(
        pipeline_id=pipeline_id,
        current_metrics=metrics,
        baseline=baseline,
        failure_rate_diff=0.25,
        retry_rate_diff=0.50,
    )

    detector = DegradationDetector()
    report = detector.evaluate(comparison)

    assert report.is_degraded is True
    signal_types = {sig.signal_type for sig in report.signals}
    assert SignalType.FAILURE_RATE_INCREASE in signal_types
    assert SignalType.RETRY_RATE_INCREASE in signal_types


def test_degradation_api_endpoint() -> None:
    """GET /pipelines/{id}/degradation returns complete report."""
    client = TestClient(create_app(Settings()))

    # Create pipeline & run slow scenario
    create_res = client.post(
        "/pipelines",
        json={
            "name": "degrad_pipe",
            "owner": "ops",
            "schedule": "0 * * * *",
            "dependencies": [],
        },
    )
    pipeline_id = create_res.json()["id"]

    client.post(
        f"/pipelines/{pipeline_id}/run",
        json={"scenario": "slow", "started_at": "2026-01-10T10:00:00Z"},
    )

    deg_res = client.get(f"/pipelines/{pipeline_id}/degradation")
    assert deg_res.status_code == 200
    body = deg_res.json()
    assert body["pipeline_id"] == pipeline_id
    assert "is_degraded" in body
    assert "signals" in body


def test_degradation_unknown_pipeline_returns_404() -> None:
    """Missing pipeline returns 404."""
    client = TestClient(create_app(Settings()))
    missing_id = "00000000-0000-0000-0000-000000000077"

    res = client.get(f"/pipelines/{missing_id}/degradation")
    assert res.status_code == 404
