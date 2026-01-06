"""
Structured logging configuration using structlog.

Provides consistent JSON logging for production and
human-readable console logging for development.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from config import get_settings


def add_app_context(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add application context to all log entries."""
    settings = get_settings()
    event_dict["app"] = "aeo-orchestrator"
    event_dict["environment"] = settings.app_env
    return event_dict


def drop_color_message_key(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Remove color_message key that uvicorn adds."""
    event_dict.pop("color_message", None)
    return event_dict


def configure_logging() -> None:
    """
    Configure structured logging for the application.

    In production: JSON output for log aggregation systems
    In development: Colorized console output for readability
    """
    settings = get_settings()

    # Shared processors for all environments
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        add_app_context,
        drop_color_message_key,
    ]

    if settings.is_production:
        # Production: JSON logs for structured log aggregation
        shared_processors.append(structlog.processors.format_exc_info)
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        # Development: Pretty console output
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    # Root handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers = []
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Configure specific loggers
    loggers_to_configure = [
        "aeo",
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "sqlalchemy.engine",
        "arq",
        "httpx",
    ]

    for logger_name in loggers_to_configure:
        logger = logging.getLogger(logger_name)
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(log_level)
        logger.propagate = False

    # Reduce noise from certain loggers in production
    if settings.is_production:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a configured logger instance."""
    return structlog.get_logger(name)


def bind_contextvars(**kwargs: Any) -> None:
    """
    Bind context variables for the current async context.

    These values will be included in all log entries within this context.
    Useful for request_id, organization_id, etc.
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_contextvars() -> None:
    """Clear all context variables."""
    structlog.contextvars.clear_contextvars()
