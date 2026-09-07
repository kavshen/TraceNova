"""Versioned event contracts shared across TraceNova services."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventType(StrEnum):
    """Events produced by the pipeline simulator."""

    PIPELINE_STARTED = "PIPELINE_STARTED"
    PIPELINE_COMPLETED = "PIPELINE_COMPLETED"
    PIPELINE_FAILED = "PIPELINE_FAILED"
    PIPELINE_RETRIED = "PIPELINE_RETRIED"


class PipelineEvent(BaseModel):
    """A versioned pipeline event."""

    event_id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    schema_version: int = Field(default=1, ge=1)
    pipeline_id: UUID
    correlation_id: UUID
    timestamp: datetime
    payload: dict[str, Any] = Field(default_factory=dict)