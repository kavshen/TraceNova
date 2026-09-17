"""Unit tests for Phase 8 heuristic root-cause analysis."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from tracenova_api.main import create_app
from tracenova_api.models import (
    DegradationReport,
    DetectionSignal,
    RCACause,
    SignalSeverity,
    SignalType,
)
from tracenova_api.rca import RCAEngine
from tracenova_config.settings import Settings


def _signal(
    pipeline_id: object,
    signal_type: SignalType,
    severity: SignalSeverity,
) -> DetectionSignal:
    return DetectionSignal(
        pipeline_id=pipeline_id,
        signal_type=signal_type,
        current_value=1.0,
        baseline_value=0.5,
        deviation=1.0,
        threshold=0.25,
        severity=severity,
        timestamp=datetime.now(UTC),
    )


def _report(pipeline_id: object, signals: list[DetectionSignal]) -> DegradationReport:
    return DegradationReport(
        pipeline_id=pipeline_id,
        is_degraded=len(signals) > 0,
        signals=signals,
        evaluated_at=datetime.now(UTC),
    )


def _cause(result, cause: RCACause):  # type: ignore[no-untyped-def]
    return next(c for c in result.causes if c.cause == cause)


def test_no_signals_gives_zero_score_to_every_cause() -> None:
    """A clean (non-degraded) report scores every cause at 0."""
    pipeline_id = uuid4()
    result = RCAEngine.analyze(_report(pipeline_id, []))

    assert result.pipeline_id == pipeline_id
    assert len(result.causes) == 8
    assert all(c.score == 0.0 for c in result.causes)


def test_all_eight_causes_always_present() -> None:
    """Every candidate cause from the plan is always returned, even at score 0."""
    pipeline_id = uuid4()
    result = RCAEngine.analyze(_report(pipeline_id, []))
    causes_present = {c.cause for c in result.causes}

    assert causes_present == set(RCACause)


def test_results_are_ranked_descending_by_score() -> None:
    """Causes are sorted highest score first."""
    pipeline_id = uuid4()
    signals = [_signal(pipeline_id, SignalType.RETRY_RATE_INCREASE, SignalSeverity.HIGH)]
    result = RCAEngine.analyze(_report(pipeline_id, signals))

    scores = [c.score for c in result.causes]
    assert scores == sorted(scores, reverse=True)


def test_high_retry_rate_scores_retry_storm_highest() -> None:
    """A lone HIGH retry-rate signal should make RETRY_STORM the top cause."""
    pipeline_id = uuid4()
    signals = [_signal(pipeline_id, SignalType.RETRY_RATE_INCREASE, SignalSeverity.HIGH)]
    result = RCAEngine.analyze(_report(pipeline_id, signals))

    top_cause = result.causes[0]
    assert top_cause.cause == RCACause.RETRY_STORM
    assert top_cause.score == 0.7
    assert top_cause.contributing_signals == [SignalType.RETRY_RATE_INCREASE]
    assert "RETRY_STORM_BASE" in top_cause.rule_ids
    assert "RETRY_STORM_HIGH_SEVERITY" in top_cause.rule_ids


def test_duration_and_retry_compound_for_database_bottleneck() -> None:
    """Duration + retry together should raise DATABASE_BOTTLENECK's score."""
    pipeline_id = uuid4()
    signals = [
        _signal(pipeline_id, SignalType.DURATION_DEGRADATION, SignalSeverity.HIGH),
        _signal(pipeline_id, SignalType.RETRY_RATE_INCREASE, SignalSeverity.MEDIUM),
    ]
    result = RCAEngine.analyze(_report(pipeline_id, signals))

    db_cause = _cause(result, RCACause.DATABASE_BOTTLENECK)
    assert db_cause.score == 0.65  # 0.35 base + 0.15 high severity + 0.15 retry compound
    assert SignalType.DURATION_DEGRADATION in db_cause.contributing_signals
    assert SignalType.RETRY_RATE_INCREASE in db_cause.contributing_signals


def test_failure_rate_scores_upstream_api_and_dependency_failure() -> None:
    """A HIGH failure-rate signal contributes to both API and dependency causes."""
    pipeline_id = uuid4()
    signals = [_signal(pipeline_id, SignalType.FAILURE_RATE_INCREASE, SignalSeverity.HIGH)]
    result = RCAEngine.analyze(_report(pipeline_id, signals))

    api_cause = _cause(result, RCACause.UPSTREAM_API_FAILURE)
    dep_cause = _cause(result, RCACause.DEPENDENCY_FAILURE)
    assert api_cause.score == 0.6
    assert dep_cause.score == 0.45


def test_recent_deployment_always_scores_zero_with_missing_evidence() -> None:
    """RECENT_DEPLOYMENT can never be scored without deployment data, by design."""
    pipeline_id = uuid4()
    signals = [_signal(pipeline_id, SignalType.DURATION_DEGRADATION, SignalSeverity.HIGH)]
    result = RCAEngine.analyze(_report(pipeline_id, signals))

    deployment_cause = _cause(result, RCACause.RECENT_DEPLOYMENT)
    assert deployment_cause.score == 0.0
    assert deployment_cause.contributing_signals == []
    assert deployment_cause.missing_evidence
    assert deployment_cause.rule_ids == []


def test_every_cause_reports_missing_evidence() -> None:
    """Every cause always documents what evidence would confirm/strengthen it."""
    pipeline_id = uuid4()
    signals = [_signal(pipeline_id, SignalType.THROUGHPUT_DECREASE, SignalSeverity.HIGH)]
    result = RCAEngine.analyze(_report(pipeline_id, signals))

    assert all(c.missing_evidence for c in result.causes)


def _create_pipeline_and_degrade(client: TestClient) -> str:
    create_res = client.post(
        "/pipelines",
        json={
            "name": "rca_pipe",
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


def test_rca_api_returns_ranked_causes() -> None:
    """The RCA endpoint returns all 8 causes ranked descending by score."""
    client = TestClient(create_app(Settings()))
    pipeline_id = _create_pipeline_and_degrade(client)

    res = client.get(f"/pipelines/{pipeline_id}/rca")
    assert res.status_code == 200
    body = res.json()

    assert body["pipeline_id"] == pipeline_id
    assert len(body["causes"]) == 8
    scores = [c["score"] for c in body["causes"]]
    assert scores == sorted(scores, reverse=True)


def test_rca_unknown_pipeline_returns_404() -> None:
    """RCA endpoint returns 404 for a non-existent pipeline."""
    client = TestClient(create_app(Settings()))
    missing_id = "00000000-0000-0000-0000-000000000099"

    res = client.get(f"/pipelines/{missing_id}/rca")
    assert res.status_code == 404