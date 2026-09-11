"""Incident management service for TraceNova."""

from datetime import UTC, datetime
from uuid import UUID

from tracenova_api.models import (
    HealthStatus,
    Incident,
    IncidentStatus,
    PipelineHealthClassification,
    SignalSeverity,
)


class IncidentManager:
    """Manages operational incidents with idempotent creation and deduplication."""

    def __init__(self) -> None:
        self.incidents: dict[UUID, Incident] = {}

    def evaluate_and_trigger(
        self,
        classification: PipelineHealthClassification,
    ) -> Incident | None:
        """Idempotently trigger or update an active incident when a pipeline degrades."""
        if classification.status == HealthStatus.HEALTHY:
            return None

        now = datetime.now(UTC)
        severity = (
            SignalSeverity.HIGH
            if classification.status == HealthStatus.CRITICAL
            else SignalSeverity.MEDIUM
        )

        # Check for an active (OPEN or INVESTIGATING) incident for this pipeline
        active_incident: Incident | None = None
        for inc in self.incidents.values():
            if inc.pipeline_id == classification.pipeline_id and inc.status in (
                IncidentStatus.OPEN,
                IncidentStatus.INVESTIGATING,
            ):
                active_incident = inc
                break

        if active_incident is not None:
            # Deduplicate & update existing open incident
            active_incident.updated_at = now
            if severity == SignalSeverity.HIGH:
                active_incident.severity = SignalSeverity.HIGH

            for reason in classification.reasons:
                if reason not in active_incident.reason_codes:
                    active_incident.reason_codes.append(reason)

            return active_incident

        # Create a new incident
        incident = Incident(
            pipeline_id=classification.pipeline_id,
            severity=severity,
            status=IncidentStatus.OPEN,
            created_at=now,
            updated_at=now,
            reason_codes=list(classification.reasons),
        )
        self.incidents[incident.id] = incident
        return incident

    def list_incidents(
        self,
        pipeline_id: UUID | None = None,
        status: IncidentStatus | None = None,
    ) -> list[Incident]:
        """Return incidents matching optional pipeline or status filters."""
        results = list(self.incidents.values())
        if pipeline_id is not None:
            results = [inc for inc in results if inc.pipeline_id == pipeline_id]
        if status is not None:
            results = [inc for inc in results if inc.status == status]
        return sorted(results, key=lambda inc: inc.created_at, reverse=True)

    def get_incident(self, incident_id: UUID) -> Incident | None:
        """Retrieve a specific incident by ID."""
        return self.incidents.get(incident_id)

    def update_status(
        self,
        incident_id: UUID,
        new_status: IncidentStatus,
        hypothesis: str | None = None,
        root_cause: str | None = None,
    ) -> Incident:
        """Update incident status and optional diagnostic fields."""
        incident = self.incidents.get(incident_id)
        if incident is None:
            raise KeyError(f"Incident {incident_id} not found.")

        incident.status = new_status
        incident.updated_at = datetime.now(UTC)
        if hypothesis is not None:
            incident.hypothesis = hypothesis
        if root_cause is not None:
            incident.root_cause = root_cause

        return incident
