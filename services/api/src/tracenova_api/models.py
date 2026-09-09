"""Data models for the synthetic pipeline simulator."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from tracenova_common.events import PipelineEvent


class PipelineStatus(StrEnum):
    """Possible states of a pipeline run."""

    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class Scenario(StrEnum):
    """Deterministic simulator scenarios."""

    NORMAL = "normal"
    SLOW = "slow"
    FAILURE = "failure"
    RETRY_STORM = "retry_storm"


class Pipeline(BaseModel):
    """A configured pipeline."""

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=100)
    owner: str = Field(min_length=1, max_length=100)
    schedule: str = Field(min_length=1, max_length=100)
    dependencies: list[str] = Field(default_factory=list)


class PipelineCreate(BaseModel):
    """Input required to create a pipeline."""

    name: str = Field(min_length=1, max_length=100)
    owner: str = Field(min_length=1, max_length=100)
    schedule: str = Field(min_length=1, max_length=100)
    dependencies: list[str] = Field(default_factory=list)


class PipelineRun(BaseModel):
    """One execution attempt of a pipeline."""

    id: UUID = Field(default_factory=uuid4)
    pipeline_id: UUID
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    status: PipelineStatus = PipelineStatus.RUNNING
    attempt: int = Field(default=1, ge=1)


class RunPipelineRequest(BaseModel):
    """Input used to simulate a pipeline execution."""

    scenario: Scenario = Scenario.NORMAL
    started_at: datetime | None = None


class SimulationResult(BaseModel):
    """Runs and events produced by one simulator invocation."""

    runs: list[PipelineRun]
    events: list[PipelineEvent]


class PipelineMetrics(BaseModel):
    """Aggregated operational metrics for a pipeline."""

    pipeline_id: UUID
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    retried_runs: int = 0
    success_rate: float = 0.0
    failure_rate: float = 0.0
    retry_rate: float = 0.0
    avg_duration_ms: float = 0.0
    median_duration_ms: float = 0.0
    p95_duration_ms: float = 0.0
    throughput_per_minute: float = 0.0


class TimeseriesMetricPoint(BaseModel):
    """A metric point over a single time window."""

    timestamp: datetime
    duration_ms: float
    status: PipelineStatus


class PipelineBaseline(BaseModel):
    """Calculated historical baseline representing normal pipeline behavior."""

    pipeline_id: UUID
    sample_size: int = 0
    median_duration_ms: float = 0.0
    p95_duration_ms: float = 0.0
    failure_rate: float = 0.0
    retry_rate: float = 0.0
    throughput_per_minute: float = 0.0
    calculated_at: datetime


class BaselineComparison(BaseModel):
    """Comparison of current metrics against historical baseline."""

    pipeline_id: UUID
    current_metrics: PipelineMetrics
    baseline: PipelineBaseline
    duration_ratio: float = 1.0
    failure_rate_diff: float = 0.0
    retry_rate_diff: float = 0.0
    throughput_ratio: float = 1.0