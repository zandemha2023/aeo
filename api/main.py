"""
FastAPI main application for AEO Orchestrator.

Provides REST API endpoints for:
- Client management
- Monitoring
- Performance reports
- Alerts
"""

import asyncio
from contextlib import asynccontextmanager
from uuid import UUID

import structlog
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest, REGISTRY
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base import flush_usage_to_db, get_circuit_breaker_status, set_agent_context
from api.deps import get_session
from api.clients import router as clients_router
from api.monitoring import router as monitoring_router
from api.strategy import router as strategy_router
from api.content import router as content_router
from api.analytics import router as analytics_router
from api.jobs import router as jobs_router
from api.middleware import RateLimitMiddleware, RequestLoggingMiddleware
from config import get_settings
from observability.logging import configure_logging, bind_contextvars, clear_contextvars
from observability.metrics import MetricsMiddleware

# Configure structured logging on module load
configure_logging()
logger = structlog.get_logger()


# Background task for flushing usage
async def periodic_usage_flush():
    """Periodically flush LLM usage records to database."""
    while True:
        await asyncio.sleep(60)  # Every minute
        try:
            await flush_usage_to_db()
        except Exception as e:
            logger.error("periodic_flush_error", error=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("aeo_orchestrator_starting")

    # Start background tasks
    flush_task = asyncio.create_task(periodic_usage_flush())

    yield

    # Cleanup
    flush_task.cancel()
    try:
        await flush_task
    except asyncio.CancelledError:
        pass

    # Final flush on shutdown
    await flush_usage_to_db()
    logger.info("aeo_orchestrator_shutting_down")


app = FastAPI(
    title="AEO Orchestrator",
    description="Autonomous Answer Engine Optimization Agency",
    version="0.1.0",
    lifespan=lifespan,
)

# Add middleware (order matters - last added = first executed)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(MetricsMiddleware)

# Include routers
app.include_router(clients_router, prefix="/api/clients", tags=["clients"])
app.include_router(monitoring_router, prefix="/api/monitoring", tags=["monitoring"])
app.include_router(strategy_router, prefix="/api/strategy", tags=["strategy"])
app.include_router(content_router, prefix="/api/content", tags=["content"])
app.include_router(analytics_router, prefix="/api/analytics", tags=["analytics"])
app.include_router(jobs_router, prefix="/api/jobs", tags=["jobs"])


@app.middleware("http")
async def set_agent_context_middleware(request: Request, call_next):
    """
    Set agent context from authenticated request for cost tracking.

    This middleware runs after auth and sets the organization context
    that agents use for recording LLM usage costs.
    """
    org_id = getattr(request.state, "organization_id", None)
    request_id = getattr(request.state, "request_id", None)

    if org_id:
        set_agent_context(org_id, request_id)

    response = await call_next(request)

    # Clear context after request
    set_agent_context(None, None)

    return response


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "AEO Orchestrator",
        "version": "0.1.0",
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "components": {
            "api": "ok",
            "database": "ok",  # TODO: Add actual DB check
        },
    }


@app.get("/ready")
async def ready():
    """Readiness check for container orchestration."""
    # TODO: Add actual readiness checks (DB connection, external services)
    return {"status": "ready"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/api/system/circuit-breakers")
async def circuit_breaker_status():
    """Get status of circuit breakers for monitoring."""
    return {
        "circuit_breakers": get_circuit_breaker_status(),
    }


@app.get("/api/system/usage")
async def system_usage_summary(
    days: int = 30,
    session: AsyncSession = Depends(get_session),
):
    """
    Get system-wide usage summary.

    Note: In production, this should be admin-only.
    """
    from db.queries import get_usage_summary

    # TODO: Add admin auth check
    # For now, just return empty to avoid exposing all orgs
    return {
        "message": "Admin endpoint - requires authentication",
        "usage": {},
    }
