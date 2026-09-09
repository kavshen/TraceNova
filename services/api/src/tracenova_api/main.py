"""HTTP entry point for the TraceNova API service."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, status
from redis.asyncio import Redis
from tracenova_config.settings import Settings, get_settings
from tracenova_logging.logging import configure_logging

from tracenova_api.baselines import BaselineEngine
from tracenova_api.event_publisher import EventPublisher
from tracenova_api.metrics import MetricsAggregator
from tracenova_api.models import (
    BaselineComparison,
    Pipeline,
    PipelineBaseline,
    PipelineCreate,
    PipelineMetrics,
    PipelineRun,
    RunPipelineRequest,
    SimulationResult,
    TimeseriesMetricPoint,
)
from tracenova_api.simulator import PipelineSimulator
from tracenova_api.store import PipelineStore


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the API application."""
    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)

    redis_client = Redis.from_url(
        active_settings.redis_url,
        decode_responses=True,
    )
    event_publisher = EventPublisher(
        redis_client,
        active_settings.redis_stream_name,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await redis_client.aclose()

    app = FastAPI(
        title=active_settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    pipeline_store = PipelineStore()
    simulator = PipelineSimulator()

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "api",
            "environment": active_settings.environment,
        }

    @app.post(
        "/pipelines",
        response_model=Pipeline,
        status_code=status.HTTP_201_CREATED,
        tags=["pipelines"],
    )
    def create_pipeline(payload: PipelineCreate) -> Pipeline:
        """Create and store a pipeline."""
        pipeline = Pipeline(**payload.model_dump())
        return pipeline_store.create_pipeline(pipeline)

    @app.get("/pipelines", response_model=list[Pipeline], tags=["pipelines"])
    def list_pipelines() -> list[Pipeline]:
        """Return all stored pipelines."""
        return pipeline_store.list_pipelines()

    @app.post(
        "/pipelines/{pipeline_id}/run",
        response_model=SimulationResult,
        status_code=status.HTTP_201_CREATED,
        tags=["pipelines"],
    )
    async def run_pipeline(
        pipeline_id: UUID,
        payload: RunPipelineRequest,
    ) -> SimulationResult:
        """Run a simulation and publish its events to Redis."""
        pipeline = pipeline_store.get_pipeline(pipeline_id)
        if pipeline is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found.",
            )

        result = simulator.simulate(pipeline, payload)
        pipeline_store.add_runs(result.runs)

        for event in result.events:
            await event_publisher.publish(event)

        return result

    @app.get(
        "/pipelines/{pipeline_id}/runs",
        response_model=list[PipelineRun],
        tags=["pipelines"],
    )
    def list_pipeline_runs(pipeline_id: UUID) -> list[PipelineRun]:
        """Return execution history for one pipeline."""
        if pipeline_store.get_pipeline(pipeline_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found.",
            )

        return pipeline_store.list_runs(pipeline_id)

    @app.get(
        "/metrics/pipelines/{pipeline_id}",
        response_model=PipelineMetrics,
        tags=["metrics"],
    )
    def get_pipeline_metrics(pipeline_id: UUID) -> PipelineMetrics:
        """Return aggregated summary metrics for a pipeline."""
        if pipeline_store.get_pipeline(pipeline_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found.",
            )
        runs = pipeline_store.list_runs(pipeline_id)
        return MetricsAggregator.calculate_metrics(pipeline_id, runs)

    @app.get(
        "/metrics/pipelines/{pipeline_id}/timeseries",
        response_model=list[TimeseriesMetricPoint],
        tags=["metrics"],
    )
    def get_pipeline_timeseries(pipeline_id: UUID) -> list[TimeseriesMetricPoint]:
        """Return timeseries metrics for a pipeline."""
        if pipeline_store.get_pipeline(pipeline_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found.",
            )
        runs = pipeline_store.list_runs(pipeline_id)
        return MetricsAggregator.calculate_timeseries(runs)

    @app.get(
        "/pipelines/{pipeline_id}/baseline",
        response_model=PipelineBaseline,
        tags=["baselines"],
    )
    def get_pipeline_baseline(pipeline_id: UUID) -> PipelineBaseline:
        """Return the calculated historical baseline for a pipeline."""
        if pipeline_store.get_pipeline(pipeline_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found.",
            )
        runs = pipeline_store.list_runs(pipeline_id)
        return BaselineEngine.calculate_baseline(pipeline_id, runs)

    @app.get(
        "/pipelines/{pipeline_id}/baseline/compare",
        response_model=BaselineComparison,
        tags=["baselines"],
    )
    def compare_pipeline_baseline(pipeline_id: UUID) -> BaselineComparison:
        """Compare current pipeline metrics against historical baseline."""
        if pipeline_store.get_pipeline(pipeline_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found.",
            )
        runs = pipeline_store.list_runs(pipeline_id)
        current_metrics = MetricsAggregator.calculate_metrics(pipeline_id, runs)
        baseline = BaselineEngine.calculate_baseline(pipeline_id, runs)
        return BaselineEngine.compare(current_metrics, baseline)

    return app


app = create_app()