"""Unit tests for Phase 6 health status classification."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from tracenova_api.classifier import HealthClassifier
from tracenova_api.main import create_app
from tracenova_api.models import (
    DegradationReport,
    DetectionSignal,
    HealthStatus,
    SignalSeverity,
    SignalType,
)
from tracenova_config.settings import Settings


def test_classify_healthy_when_no_signals() -> None:
    """Empty degradation report is classified as HEALTHY."""
    pipeline_id = uuid4()
    now = datetime.now(UTC)
    report = DegradationReport(
        pipeline_id=pipeline_id,
        is_degraded=False,
        signals=[],
        evaluated_at=now,
    )

    result = HealthClassifier.classify(report)

    assert result.pipeline_id == pipeline_id
    assert result.status == HealthStatus.HEALTHY
    assert result.reasons == []


def test_classify_degraded_when_medium_signal_present() -> None:
    """Medium severity signal produces DEGRADED status."""
    pipeline_id = uuid4()
    now = datetime.now(UTC)
    signal = DetectionSignal(
        pipeline_id=pipeline_id,
        signal_type=SignalType.DURATION_DEGRADATION,
        current_value=750_000.0,
        baseline_value=600_000.0,
        deviation=1.25,
        threshold=1.25,
        severity=SignalSeverity.MEDIUM,
        timestamp=now,
    )
    report = DegradationReport(
        pipeline_id=pipeline_id,
        is_degraded=True,
        signals=[signal],
        evaluated_at=now,
    )

    result = HealthClassifier.classify(report)

    assert result.status == HealthStatus.DEGRADED
    assert result.reasons == [SignalType.DURATION_DEGRADATION]


def test_classify_critical_when_high_signal_present() -> None:
    """High severity signal produces CRITICAL status."""
    pipeline_id = uuid4()
    now = datetime.now(UTC)
    signal = DetectionSignal(
        pipeline_id=pipeline_id,
        signal_type=SignalType.FAILURE_RATE_INCREASE,
        current_value=0.50,
        baseline_value=0.0,
        deviation=0.50,
        threshold=0.05,
        severity=SignalSeverity.HIGH,
        timestamp=now,
    )
    report = DegradationReport(
        pipeline_id=pipeline_id,
        is_degraded=True,
        signals=[signal],
        evaluated_at=now,
    )

    result = HealthClassifier.classify(report)

    assert result.status == HealthStatus.CRITICAL
    assert result.reasons == [SignalType.FAILURE_RATE_INCREASE]


def test_health_api_endpoint() -> None:
    """GET /pipelines/{id}/health returns valid classification."""
    client = TestClient(create_app(Settings()))

    # Create pipeline & run normal scenario
    create_res = client.post(
        "/pipelines",
        json={
            "name": "health_pipe",
            "owner": "infra",
            "schedule": "0 * * * *",
            "dependencies": [],
        },
    )
    pipeline_id = create_res.json()["id"]

    client.post(
        f"/pipelines/{pipeline_id}/run",
        json={"scenario": "normal", "started_at": "2026-01-10T10:00:00Z"},
    )

    res = client.get(f"/pipelines/{pipeline_id}/health")
    assert res.status_code == 200
    body = res.json()
    assert body["pipeline_id"] == pipeline_id
    assert body["status"] == "HEALTHY"
    assert body["reasons"] == []


def test_health_unknown_pipeline_returns_404() -> None:
    """Missing pipeline returns 404."""
    client = TestClient(create_app(Settings()))
    missing_id = "00000000-0000-0000-0000-000000000066"

    res = client.get(f"/pipelines/{missing_id}/health")
    assert res.status_code == 404
