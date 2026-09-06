"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings common to all initial TraceNova services."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="TRACENOVA_")

    app_name: str = "TraceNova API"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://tracenova:tracenova@localhost:5432/tracenova"
    redis_url: str = "redis://localhost:6379/0"


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance for the running process."""
    return Settings()

