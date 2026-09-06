"""Shared API-safe error model."""

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """A stable, correlation-aware error response contract."""

    code: str
    message: str
    correlation_id: str | None = Field(default=None)

