"""
AEO Orchestrator - Main Entry Point

An autonomous AEO agency that doesn't just report on AI visibility—it thinks
strategically, understands your business deeply, knows what "good" looks like,
and takes action to improve your presence in AI answer engines.
"""

import asyncio
import sys

import structlog
import uvicorn

from config import get_settings


def configure_logging() -> None:
    """Configure structured logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer() if not get_settings().is_production else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def run_api() -> None:
    """Run the FastAPI server."""
    configure_logging()
    settings = get_settings()

    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=not settings.is_production,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run_api()
