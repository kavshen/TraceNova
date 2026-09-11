"""HTTP entry point for the TraceNova API service."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, status
from redis.asyncio import Redis
from tracenova_config.settings import Settings, get_settings
from tracenova_logging.logging import configure_logging

from tracenova_api.baselines import BaselineEngine
from tracenova_api.classifier import HealthClassifier
from tracenova_api.degradation import DegradationDetector
from tracenova_api.event_publisher import EventPublisher
from tracenova_api.incidents import IncidentManager
from tracenova_api.metrics import MetricsAggregator
from tracenova_api.models import (
    BaselineComparison,
    DegradationReport,
    Incident,
    IncidentStatus,
    Pipeline,
    PipelineBaseline,
    PipelineCreate,
    PipelineHealthClassification,
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
    degradation_detector = DegradationDetector()
    incident_manager = IncidentManager()

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

    @app.get(
        "/pipelines/{pipeline_id}/degradation",
        response_model=DegradationReport,
        tags=["degradation"],
    )
    def get_pipeline_degradation(pipeline_id: UUID) -> DegradationReport:
        """Evaluate baseline comparison against detector and return degradation report."""
        if pipeline_store.get_pipeline(pipeline_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found.",
            )
        runs = pipeline_store.list_runs(pipeline_id)
        current_metrics = MetricsAggregator.calculate_metrics(pipeline_id, runs)
        baseline = BaselineEngine.calculate_baseline(pipeline_id, runs)
        comparison = BaselineEngine.compare(current_metrics, baseline)
        return degradation_detector.evaluate(comparison)

    @app.get(
        "/pipelines/{pipeline_id}/health",
        response_model=PipelineHealthClassification,
        tags=["health"],
    )
    def get_pipeline_health(pipeline_id: UUID) -> PipelineHealthClassification:
        """Classify pipeline health into HEALTHY, DEGRADED, or CRITICAL status."""
        if pipeline_store.get_pipeline(pipeline_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found.",
            )
        runs = pipeline_store.list_runs(pipeline_id)
        current_metrics = MetricsAggregator.calculate_metrics(pipeline_id, runs)
        baseline = BaselineEngine.calculate_baseline(pipeline_id, runs)
        comparison = BaselineEngine.compare(current_metrics, baseline)
        report = degradation_detector.evaluate(comparison)
        return HealthClassifier.classify(report)

    @app.post(
        "/pipelines/{pipeline_id}/incidents/evaluate",
        response_model=Incident | None,
        tags=["incidents"],
    )
    def evaluate_pipeline_incident(pipeline_id: UUID) -> Incident | None:
        """Classify current health and idempotently open/update an incident if degraded."""
        if pipeline_store.get_pipeline(pipeline_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found.",
            )
        runs = pipeline_store.list_runs(pipeline_id)
        current_metrics = MetricsAggregator.calculate_metrics(pipeline_id, runs)
        baseline = BaselineEngine.calculate_baseline(pipeline_id, runs)
        comparison = BaselineEngine.compare(current_metrics, baseline)
        report = degradation_detector.evaluate(comparison)
        classification = HealthClassifier.classify(report)
        return incident_manager.evaluate_and_trigger(classification)

    @app.get("/incidents", response_model=list[Incident], tags=["incidents"])
    def list_incidents_route() -> list[Incident]:
        """Return all stored incidents."""
        return incident_manager.list_incidents()

    @app.get("/incidents/{incident_id}", response_model=Incident, tags=["incidents"])
    def get_incident_route(incident_id: UUID) -> Incident:
        """Return one incident by id."""
        incident = incident_manager.get_incident(incident_id)
        if incident is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found.",
            )
        return incident

    @app.post("/incidents/{incident_id}/resolve", response_model=Incident, tags=["incidents"])
    def resolve_incident_route(incident_id: UUID) -> Incident:
        """Transition an incident to RESOLVED."""
        incident = incident_manager.get_incident(incident_id)
        if incident is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found.",
            )
        if incident.status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot resolve incident in {incident.status} status.",
            )
        return incident_manager.update_status(incident_id, IncidentStatus.RESOLVED)

    return app


app = create_app()