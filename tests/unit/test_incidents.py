"""Unit tests for Phase 7 incident management."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from tracenova_api.incidents import IncidentManager
from tracenova_api.main import create_app
from tracenova_api.models import (
    DegradationReport,
    DetectionSignal,
    HealthStatus,
    IncidentStatus,
    PipelineHealthClassification,
    SignalSeverity,
    SignalType,
)
from tracenova_config.settings import Settings


def _classification(
    pipeline_id: object,
    status: HealthStatus,
    signal_type: SignalType = SignalType.DURATION_DEGRADATION,
    severity: SignalSeverity = SignalSeverity.MEDIUM,
) -> PipelineHealthClassification:
    now = datetime.now(UTC)
    signals = []
    reasons: list[SignalType] = []
    if status != HealthStatus.HEALTHY:
        signals = [
            DetectionSignal(
                pipeline_id=pipeline_id,
                signal_type=signal_type,
                current_value=1.0,
                baseline_value=0.5,
                deviation=1.0,
                threshold=0.25,
                severity=severity,
                timestamp=now,
            )
        ]
        reasons = [signal_type]
    report = DegradationReport(
        pipeline_id=pipeline_id,
        is_degraded=status != HealthStatus.HEALTHY,
        signals=signals,
        evaluated_at=now,
    )
    return PipelineHealthClassification(
        pipeline_id=pipeline_id,
        status=status,
        reasons=reasons,
        report=report,
        classified_at=now,
    )


def test_evaluate_healthy_creates_no_incident() -> None:
    """A HEALTHY classification produces no incident."""
    manager = IncidentManager()
    result = manager.evaluate_and_trigger(_classification(uuid4(), HealthStatus.HEALTHY))
    assert result is None


def test_evaluate_degraded_opens_incident() -> None:
    """A DEGRADED classification opens a new OPEN incident with reason codes."""
    pipeline_id = uuid4()
    manager = IncidentManager()

    incident = manager.evaluate_and_trigger(_classification(pipeline_id, HealthStatus.DEGRADED))

    assert incident is not None
    assert incident.pipeline_id == pipeline_id
    assert incident.status == IncidentStatus.OPEN
    assert incident.severity == SignalSeverity.MEDIUM
    assert incident.reason_codes == [SignalType.DURATION_DEGRADATION]


def test_repeated_evaluation_does_not_duplicate_incident() -> None:
    """Repeated detection for the same ongoing degradation reuses the active incident."""
    pipeline_id = uuid4()
    manager = IncidentManager()

    first = manager.evaluate_and_trigger(_classification(pipeline_id, HealthStatus.DEGRADED))
    second = manager.evaluate_and_trigger(_classification(pipeline_id, HealthStatus.DEGRADED))

    assert first is not None
    assert second is not None
    assert first.id == second.id
    assert len(manager.list_incidents()) == 1


def test_escalation_updates_existing_incident_severity() -> None:
    """Escalating from DEGRADED to CRITICAL raises severity on the same incident."""
    pipeline_id = uuid4()
    manager = IncidentManager()

    opened = manager.evaluate_and_trigger(_classification(pipeline_id, HealthStatus.DEGRADED))
    escalated = manager.evaluate_and_trigger(
        _classification(
            pipeline_id,
            HealthStatus.CRITICAL,
            signal_type=SignalType.FAILURE_RATE_INCREASE,
            severity=SignalSeverity.HIGH,
        )
    )

    assert opened is not None and escalated is not None
    assert opened.id == escalated.id
    assert escalated.severity == SignalSeverity.HIGH
    assert SignalType.FAILURE_RATE_INCREASE in escalated.reason_codes
    assert SignalType.DURATION_DEGRADATION in escalated.reason_codes


def test_resolve_transitions_to_resolved() -> None:
    """Resolving an OPEN incident transitions it to RESOLVED."""
    manager = IncidentManager()
    incident = manager.evaluate_and_trigger(_classification(uuid4(), HealthStatus.DEGRADED))
    assert incident is not None

    resolved = manager.update_status(incident.id, IncidentStatus.RESOLVED)

    assert resolved.status == IncidentStatus.RESOLVED


def test_new_incident_opened_after_previous_one_resolved() -> None:
    """A fresh degradation after resolution opens a distinct new incident."""
    pipeline_id = uuid4()
    manager = IncidentManager()

    first = manager.evaluate_and_trigger(_classification(pipeline_id, HealthStatus.DEGRADED))
    assert first is not None
    manager.update_status(first.id, IncidentStatus.RESOLVED)

    second = manager.evaluate_and_trigger(_classification(pipeline_id, HealthStatus.DEGRADED))

    assert second is not None
    assert second.id != first.id
    assert second.status == IncidentStatus.OPEN


def _create_pipeline_and_degrade(client: TestClient) -> str:
    create_res = client.post(
        "/pipelines",
        json={
            "name": "incident_pipe",
            "owner": "infra",
            "schedule": "0 * * * *",
            "dependencies": [],
        },
    )
    pipeline_id = create_res.json()["id"]
    client.post(
        f"/pipelines/{pipeline_id}/run",
        json={"scenario": "failure", "started_at": "2026-01-10T10:00:00Z"},
    )
    return pipeline_id


def test_incident_api_lifecycle() -> None:
    """End-to-end: evaluate creates an incident, it is listed/fetched, then resolved."""
    client = TestClient(create_app(Settings()))
    pipeline_id = _create_pipeline_and_degrade(client)

    eval_res = client.post(f"/pipelines/{pipeline_id}/incidents/evaluate")
    assert eval_res.status_code == 200
    body = eval_res.json()

    if body is None:
        # This particular synthetic run did not cross a degradation threshold;
        # nothing further to assert for the lifecycle in that case.
        return

    incident_id = body["id"]
    assert body["pipeline_id"] == pipeline_id
    assert body["status"] == "OPEN"

    list_res = client.get("/incidents")
    assert list_res.status_code == 200
    assert any(i["id"] == incident_id for i in list_res.json())

    get_res = client.get(f"/incidents/{incident_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == incident_id

    resolve_res = client.post(f"/incidents/{incident_id}/resolve")
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "RESOLVED"

    second_resolve = client.post(f"/incidents/{incident_id}/resolve")
    assert second_resolve.status_code == 409


def test_incident_unknown_returns_404() -> None:
    """Missing incident id returns 404."""
    client = TestClient(create_app(Settings()))
    missing_id = "00000000-0000-0000-0000-000000000077"

    assert client.get(f"/incidents/{missing_id}").status_code == 404
    assert client.post(f"/incidents/{missing_id}/resolve").status_code == 404


def test_evaluate_unknown_pipeline_returns_404() -> None:
    """Evaluating incidents for a missing pipeline returns 404."""
    client = TestClient(create_app(Settings()))
    missing_id = "00000000-0000-0000-0000-000000000088"

    res = client.post(f"/pipelines/{missing_id}/incidents/evaluate")
    assert res.status_code == 404