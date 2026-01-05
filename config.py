"""Application configuration using pydantic-settings."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Anthropic
    anthropic_api_key: str

    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/aeo"
    database_sync_url: str = "postgresql://user:password@localhost:5432/aeo"

    # External AI APIs
    openai_api_key: str | None = None
    perplexity_api_key: str | None = None
    google_api_key: str | None = None

    # Application
    app_env: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Worker
    worker_concurrency: int = 4
    monitoring_interval_hours: int = 4

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
