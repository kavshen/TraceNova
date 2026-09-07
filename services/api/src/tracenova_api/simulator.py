"""Deterministic synthetic pipeline execution simulator."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from tracenova_common.events import EventType, PipelineEvent

from tracenova_api.models import (
    Pipeline,
    PipelineRun,
    PipelineStatus,
    RunPipelineRequest,
    Scenario,
    SimulationResult,
)


class PipelineSimulator:
    """Generates deterministic runs and events for supported scenarios."""

    NORMAL_DURATION_MS = 600_000
    SLOW_DURATION_MS = 1_800_000
    FAILURE_DURATION_MS = 600_000
    RETRY_DURATION_MS = 60_000
    RETRY_BACKOFF_MS = 15_000
    RETRY_ATTEMPTS = 3

    def simulate(self, pipeline: Pipeline, request: RunPipelineRequest) -> SimulationResult:
        """Generate runs and events for the requested scenario."""
        started_at = self._resolve_start_time(request.started_at)
        correlation_id = uuid4()

        if request.scenario is Scenario.NORMAL:
            return self._single_attempt(
                pipeline=pipeline,
                correlation_id=correlation_id,
                started_at=started_at,
                duration_ms=self.NORMAL_DURATION_MS,
                status=PipelineStatus.SUCCESS,
            )

        if request.scenario is Scenario.SLOW:
            return self._single_attempt(
                pipeline=pipeline,
                correlation_id=correlation_id,
                started_at=started_at,
                duration_ms=self.SLOW_DURATION_MS,
                status=PipelineStatus.SUCCESS,
            )

        if request.scenario is Scenario.FAILURE:
            return self._single_attempt(
                pipeline=pipeline,
                correlation_id=correlation_id,
                started_at=started_at,
                duration_ms=self.FAILURE_DURATION_MS,
                status=PipelineStatus.FAILED,
            )

        return self._retry_storm(
            pipeline=pipeline,
            correlation_id=correlation_id,
            started_at=started_at,
        )

    def _single_attempt(
        self,
        pipeline: Pipeline,
        correlation_id: UUID,
        started_at: datetime,
        duration_ms: int,
        status: PipelineStatus,
    ) -> SimulationResult:
        completed_at = started_at + timedelta(milliseconds=duration_ms)
        run = PipelineRun(
            pipeline_id=pipeline.id,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            status=status,
            attempt=1,
        )

        terminal_event = (
            EventType.PIPELINE_COMPLETED
            if status is PipelineStatus.SUCCESS
            else EventType.PIPELINE_FAILED
        )

        events = [
            self._event(
                event_type=EventType.PIPELINE_STARTED,
                pipeline_id=pipeline.id,
                correlation_id=correlation_id,
                timestamp=started_at,
                payload={"attempt": 1},
            ),
            self._event(
                event_type=terminal_event,
                pipeline_id=pipeline.id,
                correlation_id=correlation_id,
                timestamp=completed_at,
                payload={
                    "attempt": 1,
                    "duration_ms": duration_ms,
                    "status": status.value,
                },
            ),
        ]

        return SimulationResult(runs=[run], events=events)

    def _retry_storm(
        self,
        pipeline: Pipeline,
        correlation_id: UUID,
        started_at: datetime,
    ) -> SimulationResult:
        runs: list[PipelineRun] = []
        events: list[PipelineEvent] = []
        attempt_started_at = started_at

        for attempt in range(1, self.RETRY_ATTEMPTS + 1):
            completed_at = attempt_started_at + timedelta(milliseconds=self.RETRY_DURATION_MS)
            run = PipelineRun(
                pipeline_id=pipeline.id,
                started_at=attempt_started_at,
                completed_at=completed_at,
                duration_ms=self.RETRY_DURATION_MS,
                status=PipelineStatus.FAILED,
                attempt=attempt,
            )
            runs.append(run)

            events.append(
                self._event(
                    event_type=EventType.PIPELINE_STARTED,
                    pipeline_id=pipeline.id,
                    correlation_id=correlation_id,
                    timestamp=attempt_started_at,
                    payload={"attempt": attempt},
                )
            )
            events.append(
                self._event(
                    event_type=EventType.PIPELINE_FAILED,
                    pipeline_id=pipeline.id,
                    correlation_id=correlation_id,
                    timestamp=completed_at,
                    payload={
                        "attempt": attempt,
                        "duration_ms": self.RETRY_DURATION_MS,
                        "status": PipelineStatus.FAILED.value,
                    },
                )
            )

            if attempt < self.RETRY_ATTEMPTS:
                events.append(
                    self._event(
                        event_type=EventType.PIPELINE_RETRIED,
                        pipeline_id=pipeline.id,
                        correlation_id=correlation_id,
                        timestamp=completed_at,
                        payload={
                            "attempt": attempt,
                            "next_attempt": attempt + 1,
                        },
                    )
                )

            attempt_started_at = completed_at + timedelta(milliseconds=self.RETRY_BACKOFF_MS)

        return SimulationResult(runs=runs, events=events)

    @staticmethod
    def _resolve_start_time(started_at: datetime | None) -> datetime:
        """Return a UTC timestamp, using the current time when none was supplied."""
        if started_at is None:
            return datetime.now(UTC)
        if started_at.tzinfo is None:
            return started_at.replace(tzinfo=UTC)
        return started_at.astimezone(UTC)

    @staticmethod
    def _event(
        event_type: EventType,
        pipeline_id: UUID,
        correlation_id: UUID,
        timestamp: datetime,
        payload: dict[str, object],
    ) -> PipelineEvent:
        """Create a versioned event."""
        return PipelineEvent(
            event_type=event_type,
            pipeline_id=pipeline_id,
            correlation_id=correlation_id,
            timestamp=timestamp,
            payload=payload,
        )