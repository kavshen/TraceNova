"""Unit tests for deterministic simulator behavior."""

from datetime import UTC, datetime

from tracenova_api.models import (
    Pipeline,
    PipelineStatus,
    RunPipelineRequest,
    Scenario,
)
from tracenova_api.simulator import PipelineSimulator
from tracenova_common.events import EventType

FIXED_START = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)


def pipeline() -> Pipeline:
    """Create a pipeline for simulator tests."""
    return Pipeline(
        name="orders_daily",
        owner="data-platform",
        schedule="0 2 * * *",
        dependencies=["orders_db"],
    )


def test_normal_scenario_is_successful() -> None:
    """Normal scenarios have the expected fixed duration."""
    result = PipelineSimulator().simulate(
        pipeline(),
        RunPipelineRequest(scenario=Scenario.NORMAL, started_at=FIXED_START),
    )

    assert len(result.runs) == 1
    assert result.runs[0].status is PipelineStatus.SUCCESS
    assert result.runs[0].duration_ms == 600_000
    assert [event.event_type for event in result.events] == [
        EventType.PIPELINE_STARTED,
        EventType.PIPELINE_COMPLETED,
    ]


def test_slow_scenario_is_longer_than_normal() -> None:
    """Slow scenarios use the fixed slow duration."""
    result = PipelineSimulator().simulate(
        pipeline(),
        RunPipelineRequest(scenario=Scenario.SLOW, started_at=FIXED_START),
    )

    assert result.runs[0].status is PipelineStatus.SUCCESS
    assert result.runs[0].duration_ms == 1_800_000


def test_failure_scenario_creates_failed_run() -> None:
    """Failure scenarios emit a failure event."""
    result = PipelineSimulator().simulate(
        pipeline(),
        RunPipelineRequest(scenario=Scenario.FAILURE, started_at=FIXED_START),
    )

    assert result.runs[0].status is PipelineStatus.FAILED
    assert result.events[-1].event_type is EventType.PIPELINE_FAILED


def test_retry_storm_creates_multiple_failed_attempts() -> None:
    """Retry storms emit retries and preserve one correlation ID."""
    result = PipelineSimulator().simulate(
        pipeline(),
        RunPipelineRequest(scenario=Scenario.RETRY_STORM, started_at=FIXED_START),
    )

    assert len(result.runs) == 3
    assert [run.attempt for run in result.runs] == [1, 2, 3]
    assert all(run.status is PipelineStatus.FAILED for run in result.runs)
    assert sum(event.event_type is EventType.PIPELINE_RETRIED for event in result.events) == 2
    assert len({event.correlation_id for event in result.events}) == 1
    assert all(event.schema_version == 1 for event in result.events)