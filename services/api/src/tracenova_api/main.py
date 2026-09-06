"""HTTP entry point for the TraceNova API service."""

from fastapi import FastAPI
from tracenova_config.settings import Settings, get_settings
from tracenova_logging.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the API application without connecting to optional dependencies."""
    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)

    app = FastAPI(title=active_settings.app_name, version="0.1.0")

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "api",
            "environment": active_settings.environment,
        }

    return app


app = create_app()

