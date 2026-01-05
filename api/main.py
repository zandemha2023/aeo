"""
FastAPI main application for AEO Orchestrator.

Provides REST API endpoints for:
- Client management
- Monitoring
- Performance reports
- Alerts
"""

from contextlib import asynccontextmanager
from uuid import UUID

import structlog
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from api.clients import router as clients_router
from api.monitoring import router as monitoring_router
from api.strategy import router as strategy_router
from config import get_settings

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("aeo_orchestrator_starting")
    yield
    logger.info("aeo_orchestrator_shutting_down")


app = FastAPI(
    title="AEO Orchestrator",
    description="Autonomous Answer Engine Optimization Agency",
    version="0.1.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(clients_router, prefix="/api/clients", tags=["clients"])
app.include_router(monitoring_router, prefix="/api/monitoring", tags=["monitoring"])
app.include_router(strategy_router, prefix="/api/strategy", tags=["strategy"])


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
