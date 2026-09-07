"""HTTP entry point for the TraceNova API service."""

from uuid import UUID

from fastapi import FastAPI, HTTPException, status
from tracenova_config.settings import Settings, get_settings
from tracenova_logging.logging import configure_logging

from tracenova_api.models import (
    Pipeline,
    PipelineCreate,
    PipelineRun,
    RunPipelineRequest,
    SimulationResult,
)
from tracenova_api.simulator import PipelineSimulator
from tracenova_api.store import PipelineStore


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the API application without connecting to optional dependencies."""
    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)

    app = FastAPI(title=active_settings.app_name, version="0.1.0")
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
    def run_pipeline(pipeline_id: UUID, payload: RunPipelineRequest) -> SimulationResult:
        """Run a deterministic pipeline simulation."""
        pipeline = pipeline_store.get_pipeline(pipeline_id)
        if pipeline is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found.",
            )

        result = simulator.simulate(pipeline, payload)
        pipeline_store.add_runs(result.runs)
        return result

    @app.get(
        "/pipelines/{pipeline_id}/runs",
        response_model=list[PipelineRun],
        tags=["pipelines"],
    )
    def list_pipeline_runs(pipeline_id: UUID) -> list[PipelineRun]:
        """Return the execution history for one pipeline."""
        if pipeline_store.get_pipeline(pipeline_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found.",
            )

        return pipeline_store.list_runs(pipeline_id)

    return app


app = create_app()