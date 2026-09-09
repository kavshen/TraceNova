"""Metrics aggregation engine for TraceNova."""

import math
import statistics
from uuid import UUID

from tracenova_api.models import (
    PipelineMetrics,
    PipelineRun,
    PipelineStatus,
    TimeseriesMetricPoint,
)


def calculate_p95(values: list[float]) -> float:
    """Calculate the 95th percentile of a sorted list of numeric values."""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    k = (len(sorted_values) - 1) * 0.95
    floor_idx = math.floor(k)
    ceil_idx = math.ceil(k)
    if floor_idx == ceil_idx:
        return float(sorted_values[int(k)])
    d0 = sorted_values[floor_idx] * (ceil_idx - k)
    d1 = sorted_values[ceil_idx] * (k - floor_idx)
    return float(d0 + d1)


class MetricsAggregator:
    """Calculates summary and timeseries operational metrics for pipeline executions."""

    @staticmethod
    def calculate_metrics(
        pipeline_id: UUID,
        runs: list[PipelineRun],
    ) -> PipelineMetrics:
        """Compute aggregated metrics mathematically from a list of pipeline runs."""
        total_runs = len(runs)
        if total_runs == 0:
            return PipelineMetrics(pipeline_id=pipeline_id)

        successful_runs = sum(1 for r in runs if r.status == PipelineStatus.SUCCESS)
        failed_runs = sum(1 for r in runs if r.status == PipelineStatus.FAILED)
        retried_runs = sum(1 for r in runs if r.attempt > 1)

        success_rate = successful_runs / total_runs
        failure_rate = failed_runs / total_runs
        retry_rate = retried_runs / total_runs

        durations = [float(r.duration_ms) for r in runs if r.duration_ms is not None]

        if durations:
            avg_duration = float(statistics.mean(durations))
            median_duration = float(statistics.median(durations))
            p95_duration = calculate_p95(durations)
        else:
            avg_duration = 0.0
            median_duration = 0.0
            p95_duration = 0.0

        # Calculate throughput (runs / minute)
        timestamps = [r.started_at for r in runs]
        if len(timestamps) > 1:
            earliest = min(timestamps)
            latest_run = max(runs, key=lambda r: r.completed_at or r.started_at)
            latest = latest_run.completed_at or latest_run.started_at
            span_seconds = (latest - earliest).total_seconds()
            throughput = (
                (total_runs / (span_seconds / 60.0))
                if span_seconds > 0
                else float(total_runs)
            )
        else:
            throughput = float(total_runs)

        return PipelineMetrics(
            pipeline_id=pipeline_id,
            total_runs=total_runs,
            successful_runs=successful_runs,
            failed_runs=failed_runs,
            retried_runs=retried_runs,
            success_rate=round(success_rate, 4),
            failure_rate=round(failure_rate, 4),
            retry_rate=round(retry_rate, 4),
            avg_duration_ms=round(avg_duration, 2),
            median_duration_ms=round(median_duration, 2),
            p95_duration_ms=round(p95_duration, 2),
            throughput_per_minute=round(throughput, 2),
        )

    @staticmethod
    def calculate_timeseries(runs: list[PipelineRun]) -> list[TimeseriesMetricPoint]:
        """Convert pipeline runs into chronological timeseries metric points."""
        sorted_runs = sorted(runs, key=lambda r: r.started_at)
        return [
            TimeseriesMetricPoint(
                timestamp=run.started_at,
                duration_ms=float(run.duration_ms or 0),
                status=run.status,
            )
            for run in sorted_runs
        ]
