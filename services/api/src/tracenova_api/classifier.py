"""Health status classifier engine for TraceNova."""

from datetime import UTC, datetime

from tracenova_api.models import (
    DegradationReport,
    HealthStatus,
    PipelineHealthClassification,
    SignalSeverity,
    SignalType,
)


class HealthClassifier:
    """Classifies pipeline health into HEALTHY, DEGRADED, or CRITICAL based on signals."""

    @staticmethod
    def classify(report: DegradationReport) -> PipelineHealthClassification:
        """Deterministically map a degradation report into an explainable health status."""
        now = datetime.now(UTC)

        if not report.signals:
            return PipelineHealthClassification(
                pipeline_id=report.pipeline_id,
                status=HealthStatus.HEALTHY,
                reasons=[],
                report=report,
                classified_at=now,
            )

        # Extract unique reason signal types
        reasons: list[SignalType] = []
        for signal in report.signals:
            if signal.signal_type not in reasons:
                reasons.append(signal.signal_type)

        has_high_severity = any(s.severity == SignalSeverity.HIGH for s in report.signals)
        status = HealthStatus.CRITICAL if has_high_severity else HealthStatus.DEGRADED

        return PipelineHealthClassification(
            pipeline_id=report.pipeline_id,
            status=status,
            reasons=reasons,
            report=report,
            classified_at=now,
        )
