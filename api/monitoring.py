"""Monitoring API endpoints."""

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from db.queries import (
    get_client,
    get_monitoring_queries,
    create_monitoring_query,
    get_active_alerts,
    acknowledge_alert,
    resolve_alert,
)
from knowledge.client_kb import ClientKnowledgeBase
from knowledge.schemas import AEOPerformanceReport, Severity
from workflows.monitoring import run_monitoring_workflow

logger = structlog.get_logger()
router = APIRouter()


class QueryCreate(BaseModel):
    """Request to create a monitoring query."""

    query: str
    query_type: str = "general"
    priority: int = 50


class QueryResponse(BaseModel):
    """Monitoring query response."""

    id: str
    query: str
    query_type: str
    priority: int
    active: bool


class MonitoringRunResponse(BaseModel):
    """Response from running monitoring."""

    client_id: str
    mentions_found: int
    alerts_created: int
    health_score: float | None
    health_grade: str | None
    errors: list[str]


class AlertResponse(BaseModel):
    """Alert response model."""

    id: str
    severity: str
    alert_type: str
    title: str
    details: dict
    status: str
    created_at: str


@router.post("/{client_id}/run", response_model=MonitoringRunResponse)
async def run_monitoring(
    client_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """
    Run monitoring workflow for a client.

    Queries all AI engines and analyzes brand mentions.
    """
    client = await get_client(session, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    logger.info("running_monitoring", client_id=str(client_id))

    result = await run_monitoring_workflow(session, client_id)

    return MonitoringRunResponse(
        client_id=str(client_id),
        mentions_found=sum(1 for m in result["mentions"] if m.mentioned),
        alerts_created=len(result["alerts_created"]),
        health_score=result["report"].overall_health_score if result["report"] else None,
        health_grade=result["report"].health_grade.value if result["report"] else None,
        errors=result["errors"],
    )


@router.get("/{client_id}/queries", response_model=list[QueryResponse])
async def list_queries(
    client_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """List monitoring queries for a client."""
    client = await get_client(session, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    queries = await get_monitoring_queries(session, client_id, active_only=False)

    return [
        QueryResponse(
            id=str(q.id),
            query=q.query,
            query_type=q.query_type or "general",
            priority=q.priority,
            active=q.active,
        )
        for q in queries
    ]


@router.post("/{client_id}/queries", response_model=QueryResponse)
async def add_query(
    client_id: UUID,
    request: QueryCreate,
    session: AsyncSession = Depends(get_session),
):
    """Add a new monitoring query."""
    client = await get_client(session, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    query = await create_monitoring_query(
        session,
        client_id,
        request.query,
        request.query_type,
        request.priority,
    )

    return QueryResponse(
        id=str(query.id),
        query=query.query,
        query_type=query.query_type or "general",
        priority=query.priority,
        active=query.active,
    )


@router.get("/{client_id}/report")
async def get_performance_report(
    client_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get the latest performance report for a client."""
    client = await get_client(session, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    kb = ClientKnowledgeBase(session, client_id)
    report = await kb.get_performance_report()

    if not report:
        raise HTTPException(
            status_code=404,
            detail="No performance report found - run monitoring first",
        )

    return report.model_dump()


@router.get("/{client_id}/alerts", response_model=list[AlertResponse])
async def list_alerts(
    client_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """List active alerts for a client."""
    client = await get_client(session, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    alerts = await get_active_alerts(session, client_id)

    return [
        AlertResponse(
            id=str(a.id),
            severity=a.severity,
            alert_type=a.alert_type,
            title=a.title,
            details=a.details,
            status=a.status,
            created_at=a.created_at.isoformat(),
        )
        for a in alerts
    ]


@router.post("/{client_id}/alerts/{alert_id}/acknowledge")
async def acknowledge_alert_endpoint(
    client_id: UUID,
    alert_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Acknowledge an alert."""
    alert = await acknowledge_alert(session, alert_id)

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return {"status": "acknowledged", "alert_id": str(alert_id)}


@router.post("/{client_id}/alerts/{alert_id}/resolve")
async def resolve_alert_endpoint(
    client_id: UUID,
    alert_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Resolve an alert."""
    alert = await resolve_alert(session, alert_id)

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return {"status": "resolved", "alert_id": str(alert_id)}
