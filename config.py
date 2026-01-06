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

    # Authentication
    jwt_secret_key: str = "CHANGE-ME-IN-PRODUCTION-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Rate Limiting
    rate_limit_enabled: bool = True
    default_rate_limit_rpm: int = 60  # requests per minute

    # Redis (for background jobs and rate limiting)
    redis_url: str = "redis://localhost:6379"
    redis_db: int = 0

    # Worker
    worker_concurrency: int = 4
    monitoring_interval_hours: int = 4
    job_timeout_seconds: int = 600  # 10 minutes
    job_max_retries: int = 3

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
