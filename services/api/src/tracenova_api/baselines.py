"""Historical baseline calculation engine for TraceNova."""

from datetime import UTC, datetime
from uuid import UUID

from tracenova_api.metrics import MetricsAggregator
from tracenova_api.models import (
    BaselineComparison,
    PipelineBaseline,
    PipelineMetrics,
    PipelineRun,
)


class BaselineEngine:
    """Calculates historical performance baselines and baseline comparisons."""

    @staticmethod
    def calculate_baseline(
        pipeline_id: UUID,
        runs: list[PipelineRun],
        window_size: int = 100,
    ) -> PipelineBaseline:
        """Compute rolling baseline metrics from historical execution runs."""
        sorted_runs = sorted(runs, key=lambda r: r.started_at, reverse=True)[:window_size]
        if not sorted_runs:
            return PipelineBaseline(
                pipeline_id=pipeline_id,
                calculated_at=datetime.now(UTC),
            )

        metrics = MetricsAggregator.calculate_metrics(pipeline_id, sorted_runs)
        return PipelineBaseline(
            pipeline_id=pipeline_id,
            sample_size=metrics.total_runs,
            median_duration_ms=metrics.median_duration_ms,
            p95_duration_ms=metrics.p95_duration_ms,
            failure_rate=metrics.failure_rate,
            retry_rate=metrics.retry_rate,
            throughput_per_minute=metrics.throughput_per_minute,
            calculated_at=datetime.now(UTC),
        )

    @staticmethod
    def compare(
        current_metrics: PipelineMetrics,
        baseline: PipelineBaseline,
    ) -> BaselineComparison:
        """Compare live execution metrics against a historical baseline."""
        if baseline.median_duration_ms > 0:
            duration_ratio = current_metrics.median_duration_ms / baseline.median_duration_ms
        else:
            duration_ratio = 1.0

        failure_rate_diff = current_metrics.failure_rate - baseline.failure_rate
        retry_rate_diff = current_metrics.retry_rate - baseline.retry_rate

        if baseline.throughput_per_minute > 0:
            throughput_ratio = (
                current_metrics.throughput_per_minute / baseline.throughput_per_minute
            )
        else:
            throughput_ratio = 1.0

        return BaselineComparison(
            pipeline_id=current_metrics.pipeline_id,
            current_metrics=current_metrics,
            baseline=baseline,
            duration_ratio=round(duration_ratio, 4),
            failure_rate_diff=round(failure_rate_diff, 4),
            retry_rate_diff=round(retry_rate_diff, 4),
            throughput_ratio=round(throughput_ratio, 4),
        )
