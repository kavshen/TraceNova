"""Degradation detection engine for TraceNova."""

from dataclasses import dataclass
from datetime import UTC, datetime

from tracenova_api.models import (
    BaselineComparison,
    DegradationReport,
    DetectionSignal,
    SignalSeverity,
    SignalType,
)


@dataclass
class DetectionConfig:
    """Configurable thresholds for detecting pipeline degradation."""

    duration_medium_ratio: float = 1.25
    duration_high_ratio: float = 1.75
    failure_rate_diff_threshold: float = 0.05
    retry_rate_diff_threshold: float = 0.10
    throughput_decrease_ratio_threshold: float = 0.75


class DegradationDetector:
    """Evaluates pipeline baseline comparisons against rules to detect degradation."""

    def __init__(self, config: DetectionConfig | None = None) -> None:
        self.config = config or DetectionConfig()

    def evaluate(self, comparison: BaselineComparison) -> DegradationReport:
        """Analyze a baseline comparison and emit structured detection signals."""
        signals: list[DetectionSignal] = []
        now = datetime.now(UTC)

        # 1. Duration degradation check
        if comparison.duration_ratio >= self.config.duration_high_ratio:
            signals.append(
                DetectionSignal(
                    pipeline_id=comparison.pipeline_id,
                    signal_type=SignalType.DURATION_DEGRADATION,
                    current_value=comparison.current_metrics.median_duration_ms,
                    baseline_value=comparison.baseline.median_duration_ms,
                    deviation=comparison.duration_ratio,
                    threshold=self.config.duration_high_ratio,
                    severity=SignalSeverity.HIGH,
                    timestamp=now,
                )
            )
        elif comparison.duration_ratio >= self.config.duration_medium_ratio:
            signals.append(
                DetectionSignal(
                    pipeline_id=comparison.pipeline_id,
                    signal_type=SignalType.DURATION_DEGRADATION,
                    current_value=comparison.current_metrics.median_duration_ms,
                    baseline_value=comparison.baseline.median_duration_ms,
                    deviation=comparison.duration_ratio,
                    threshold=self.config.duration_medium_ratio,
                    severity=SignalSeverity.MEDIUM,
                    timestamp=now,
                )
            )

        # 2. Failure rate increase check
        if comparison.failure_rate_diff >= self.config.failure_rate_diff_threshold:
            severity = (
                SignalSeverity.HIGH
                if comparison.failure_rate_diff >= 0.20
                else SignalSeverity.MEDIUM
            )
            signals.append(
                DetectionSignal(
                    pipeline_id=comparison.pipeline_id,
                    signal_type=SignalType.FAILURE_RATE_INCREASE,
                    current_value=comparison.current_metrics.failure_rate,
                    baseline_value=comparison.baseline.failure_rate,
                    deviation=comparison.failure_rate_diff,
                    threshold=self.config.failure_rate_diff_threshold,
                    severity=severity,
                    timestamp=now,
                )
            )

        # 3. Retry rate increase check
        if comparison.retry_rate_diff >= self.config.retry_rate_diff_threshold:
            severity = (
                SignalSeverity.HIGH
                if comparison.retry_rate_diff >= 0.30
                else SignalSeverity.MEDIUM
            )
            signals.append(
                DetectionSignal(
                    pipeline_id=comparison.pipeline_id,
                    signal_type=SignalType.RETRY_RATE_INCREASE,
                    current_value=comparison.current_metrics.retry_rate,
                    baseline_value=comparison.baseline.retry_rate,
                    deviation=comparison.retry_rate_diff,
                    threshold=self.config.retry_rate_diff_threshold,
                    severity=severity,
                    timestamp=now,
                )
            )

        # 4. Throughput decrease check
        if (
            comparison.baseline.throughput_per_minute > 0
            and comparison.throughput_ratio <= self.config.throughput_decrease_ratio_threshold
        ):
            severity = (
                SignalSeverity.HIGH
                if comparison.throughput_ratio <= 0.50
                else SignalSeverity.MEDIUM
            )
            signals.append(
                DetectionSignal(
                    pipeline_id=comparison.pipeline_id,
                    signal_type=SignalType.THROUGHPUT_DECREASE,
                    current_value=comparison.current_metrics.throughput_per_minute,
                    baseline_value=comparison.baseline.throughput_per_minute,
                    deviation=comparison.throughput_ratio,
                    threshold=self.config.throughput_decrease_ratio_threshold,
                    severity=severity,
                    timestamp=now,
                )
            )

        return DegradationReport(
            pipeline_id=comparison.pipeline_id,
            is_degraded=len(signals) > 0,
            signals=signals,
            evaluated_at=now,
        )
