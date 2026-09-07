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