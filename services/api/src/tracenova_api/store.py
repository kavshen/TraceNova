"""Temporary in-memory storage for Phase 1."""

from uuid import UUID

from tracenova_api.models import Pipeline, PipelineRun


class PipelineStore:
    """Stores pipelines and their runs until database storage is introduced."""

    def __init__(self) -> None:
        self.pipelines: dict[UUID, Pipeline] = {}
        self.runs: dict[UUID, list[PipelineRun]] = {}

    def create_pipeline(self, pipeline: Pipeline) -> Pipeline:
        """Store a pipeline."""
        self.pipelines[pipeline.id] = pipeline
        self.runs[pipeline.id] = []
        return pipeline

    def list_pipelines(self) -> list[Pipeline]:
        """Return all pipelines."""
        return list(self.pipelines.values())

    def get_pipeline(self, pipeline_id: UUID) -> Pipeline | None:
        """Return one pipeline when it exists."""
        return self.pipelines.get(pipeline_id)

    def add_runs(self, runs: list[PipelineRun]) -> list[PipelineRun]:
        """Store generated execution attempts."""
        for run in runs:
            self.runs.setdefault(run.pipeline_id, []).append(run)
        return runs

    def list_runs(self, pipeline_id: UUID) -> list[PipelineRun]:
        """Return all runs for one pipeline."""
        return list(self.runs.get(pipeline_id, []))