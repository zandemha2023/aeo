"""
ARQ worker configuration for background job processing.

Run worker with:
    arq jobs.worker.WorkerSettings
"""

from datetime import timedelta
from typing import Any

import structlog
from arq import cron
from arq.connections import RedisSettings, ArqRedis, create_pool as arq_create_pool

from config import get_settings

logger = structlog.get_logger()


def get_redis_settings() -> RedisSettings:
    """Get Redis settings from config."""
    settings = get_settings()
    # Parse redis URL
    # Format: redis://[user:password@]host[:port][/db]
    url = settings.redis_url

    if url.startswith("redis://"):
        url = url[8:]

    # Handle auth
    host = url
    password = None
    port = 6379

    if "@" in url:
        auth, host = url.rsplit("@", 1)
        if ":" in auth:
            _, password = auth.split(":", 1)

    # Handle port
    if ":" in host:
        host, port_str = host.rsplit(":", 1)
        if "/" in port_str:
            port_str = port_str.split("/")[0]
        port = int(port_str)

    # Handle db
    db = settings.redis_db

    return RedisSettings(
        host=host,
        port=port,
        password=password,
        database=db,
    )


async def create_pool() -> ArqRedis:
    """Create ARQ Redis connection pool."""
    return await arq_create_pool(get_redis_settings())


async def startup(ctx: dict[str, Any]) -> None:
    """Worker startup hook."""
    logger.info("worker_starting")

    # Initialize database session maker
    from db.queries import get_session_maker
    ctx["session_maker"] = get_session_maker()

    logger.info("worker_started")


async def shutdown(ctx: dict[str, Any]) -> None:
    """Worker shutdown hook."""
    logger.info("worker_shutting_down")

    # Flush any pending LLM usage records
    from agents.base import flush_usage_to_db
    await flush_usage_to_db()

    logger.info("worker_stopped")


async def on_job_start(ctx: dict[str, Any]) -> None:
    """Called when a job starts."""
    logger.info(
        "job_started",
        job_id=ctx.get("job_id"),
        job_name=ctx.get("job_name"),
    )


async def on_job_end(ctx: dict[str, Any]) -> None:
    """Called when a job ends."""
    logger.info(
        "job_completed",
        job_id=ctx.get("job_id"),
        job_name=ctx.get("job_name"),
        success=ctx.get("result") is not None,
    )


# Import tasks for registration
from jobs.tasks import (
    run_monitoring_job,
    run_strategy_job,
    run_content_job,
    run_onboarding_job,
)
from jobs.scheduler import run_scheduled_monitoring


class WorkerSettings:
    """ARQ worker settings."""

    # Redis connection
    redis_settings = get_redis_settings()

    # Job functions to register
    functions = [
        run_monitoring_job,
        run_strategy_job,
        run_content_job,
        run_onboarding_job,
        run_scheduled_monitoring,
    ]

    # Cron jobs (scheduled tasks)
    cron_jobs = [
        # Run scheduled monitoring every 4 hours
        cron(
            run_scheduled_monitoring,
            hour={0, 4, 8, 12, 16, 20},
            minute=0,
            run_at_startup=False,
        ),
    ]

    # Worker settings
    max_jobs = get_settings().worker_concurrency
    job_timeout = timedelta(seconds=get_settings().job_timeout_seconds)
    max_tries = get_settings().job_max_retries
    retry_jobs = True

    # Hooks
    on_startup = startup
    on_shutdown = shutdown
    on_job_start = on_job_start
    on_job_end = on_job_end

    # Queue names
    queue_name = "aeo:queue"

    # Health check
    health_check_interval = 60
    health_check_key = "aeo:health"
