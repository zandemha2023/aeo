"""
Admin dashboard API endpoints.

Provides REST API for:
- Organization statistics and overview
- Usage summaries and cost breakdowns
- System health monitoring
- User management (admin only)
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import Auth, CurrentOrg, require_role
from api.deps import get_session
from db.models import (
    Alert,
    Client,
    LLMUsage,
    MonitoringQuery,
    MonitoringResult,
    Organization,
    User,
)

logger = structlog.get_logger()
router = APIRouter()


# =============================================================================
# RESPONSE MODELS
# =============================================================================


class OrganizationStats(BaseModel):
    """Organization overview statistics."""

    organization_id: str
    organization_name: str
    plan: str
    total_clients: int
    active_clients: int
    total_queries: int
    total_monitoring_results: int
    unresolved_alerts: int
    created_at: str


class UsageSummary(BaseModel):
    """LLM usage summary."""

    period_start: str
    period_end: str
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    budget_used_percent: float
    by_agent: dict[str, dict]
    by_model: dict[str, dict]


class DailyUsage(BaseModel):
    """Daily usage breakdown."""

    date: str
    requests: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


class SystemHealth(BaseModel):
    """System health overview."""

    status: str
    database: str
    redis: str
    workers: str
    circuit_breakers: dict[str, str]
    rate_limit_status: dict


class UserResponse(BaseModel):
    """User information for admin views."""

    id: str
    email: str
    name: Optional[str]
    role: str
    is_active: bool
    last_login_at: Optional[str]
    created_at: str


class AlertSummary(BaseModel):
    """Alert summary for dashboard."""

    total: int
    by_severity: dict[str, int]
    by_status: dict[str, int]
    recent: list[dict]


# =============================================================================
# DASHBOARD ENDPOINTS
# =============================================================================


@router.get("/stats", response_model=OrganizationStats)
async def get_organization_stats(
    auth: Auth,
    org: CurrentOrg,
    session: AsyncSession = Depends(get_session),
):
    """
    Get organization overview statistics.

    Returns counts of clients, queries, results, and alerts.
    """
    # Count clients
    total_clients = await session.scalar(
        select(func.count(Client.id)).where(
            Client.organization_id == auth.organization_id
        )
    )

    active_clients = await session.scalar(
        select(func.count(Client.id)).where(
            Client.organization_id == auth.organization_id,
            Client.status == "active",
        )
    )

    # Count queries
    total_queries = await session.scalar(
        select(func.count(MonitoringQuery.id)).where(
            MonitoringQuery.organization_id == auth.organization_id
        )
    )

    # Count results
    total_results = await session.scalar(
        select(func.count(MonitoringResult.id)).where(
            MonitoringResult.organization_id == auth.organization_id
        )
    )

    # Count unresolved alerts
    unresolved_alerts = await session.scalar(
        select(func.count(Alert.id)).where(
            Alert.organization_id == auth.organization_id,
            Alert.status.in_(["new", "acknowledged"]),
        )
    )

    return OrganizationStats(
        organization_id=str(org.id),
        organization_name=org.name,
        plan=org.plan,
        total_clients=total_clients or 0,
        active_clients=active_clients or 0,
        total_queries=total_queries or 0,
        total_monitoring_results=total_results or 0,
        unresolved_alerts=unresolved_alerts or 0,
        created_at=org.created_at.isoformat(),
    )


@router.get("/usage", response_model=UsageSummary)
async def get_usage_summary(
    auth: Auth,
    org: CurrentOrg,
    days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
):
    """
    Get LLM usage summary for the organization.

    Returns token usage, costs, and breakdowns by agent and model.
    """
    period_start = datetime.utcnow() - timedelta(days=days)
    period_end = datetime.utcnow()

    # Get usage records
    result = await session.execute(
        select(LLMUsage).where(
            LLMUsage.organization_id == auth.organization_id,
            LLMUsage.created_at >= period_start,
        )
    )
    usage_records = result.scalars().all()

    # Aggregate data
    total_requests = len(usage_records)
    total_input_tokens = sum(r.input_tokens for r in usage_records)
    total_output_tokens = sum(r.output_tokens for r in usage_records)
    total_cost = sum(float(r.cost_usd) for r in usage_records)

    # Calculate budget usage
    budget = float(org.monthly_llm_budget_usd or Decimal("100.00"))
    # Pro-rate budget for period
    days_in_month = 30
    period_budget = budget * (days / days_in_month)
    budget_used_percent = (total_cost / period_budget * 100) if period_budget > 0 else 0

    # Group by agent
    by_agent: dict[str, dict] = {}
    for r in usage_records:
        if r.agent not in by_agent:
            by_agent[r.agent] = {
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
            }
        by_agent[r.agent]["requests"] += 1
        by_agent[r.agent]["input_tokens"] += r.input_tokens
        by_agent[r.agent]["output_tokens"] += r.output_tokens
        by_agent[r.agent]["cost_usd"] += float(r.cost_usd)

    # Group by model
    by_model: dict[str, dict] = {}
    for r in usage_records:
        if r.model not in by_model:
            by_model[r.model] = {
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
            }
        by_model[r.model]["requests"] += 1
        by_model[r.model]["input_tokens"] += r.input_tokens
        by_model[r.model]["output_tokens"] += r.output_tokens
        by_model[r.model]["cost_usd"] += float(r.cost_usd)

    return UsageSummary(
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        total_requests=total_requests,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_cost_usd=round(total_cost, 4),
        budget_used_percent=round(budget_used_percent, 2),
        by_agent=by_agent,
        by_model=by_model,
    )


@router.get("/usage/daily", response_model=list[DailyUsage])
async def get_daily_usage(
    auth: Auth,
    days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
):
    """
    Get daily usage breakdown for charting.

    Returns per-day token usage and costs.
    """
    period_start = datetime.utcnow() - timedelta(days=days)

    result = await session.execute(
        select(LLMUsage).where(
            LLMUsage.organization_id == auth.organization_id,
            LLMUsage.created_at >= period_start,
        ).order_by(LLMUsage.created_at)
    )
    usage_records = result.scalars().all()

    # Group by date
    daily_data: dict[str, dict] = {}
    for r in usage_records:
        date_key = r.created_at.strftime("%Y-%m-%d")
        if date_key not in daily_data:
            daily_data[date_key] = {
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
            }
        daily_data[date_key]["requests"] += 1
        daily_data[date_key]["input_tokens"] += r.input_tokens
        daily_data[date_key]["output_tokens"] += r.output_tokens
        daily_data[date_key]["cost_usd"] += float(r.cost_usd)

    return [
        DailyUsage(
            date=date,
            requests=data["requests"],
            input_tokens=data["input_tokens"],
            output_tokens=data["output_tokens"],
            cost_usd=round(data["cost_usd"], 4),
        )
        for date, data in sorted(daily_data.items())
    ]


@router.get("/alerts", response_model=AlertSummary)
async def get_alert_summary(
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """
    Get alert summary for the dashboard.

    Returns alert counts by severity and status, plus recent alerts.
    """
    # Get all alerts for org
    result = await session.execute(
        select(Alert).where(
            Alert.organization_id == auth.organization_id
        ).order_by(Alert.created_at.desc())
    )
    alerts = result.scalars().all()

    # Count by severity
    by_severity: dict[str, int] = {}
    for a in alerts:
        by_severity[a.severity] = by_severity.get(a.severity, 0) + 1

    # Count by status
    by_status: dict[str, int] = {}
    for a in alerts:
        by_status[a.status] = by_status.get(a.status, 0) + 1

    # Get recent alerts (last 10)
    recent = [
        {
            "id": str(a.id),
            "client_id": str(a.client_id),
            "severity": a.severity,
            "alert_type": a.alert_type,
            "title": a.title,
            "status": a.status,
            "created_at": a.created_at.isoformat(),
        }
        for a in alerts[:10]
    ]

    return AlertSummary(
        total=len(alerts),
        by_severity=by_severity,
        by_status=by_status,
        recent=recent,
    )


# =============================================================================
# USER MANAGEMENT (Admin Only)
# =============================================================================


@router.get(
    "/users",
    response_model=list[UserResponse],
    dependencies=[Depends(require_role(["admin", "owner"]))],
)
async def list_users(
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """
    List all users in the organization.

    Requires admin or owner role.
    """
    result = await session.execute(
        select(User).where(User.organization_id == auth.organization_id)
    )
    users = result.scalars().all()

    return [
        UserResponse(
            id=str(u.id),
            email=u.email,
            name=u.name,
            role=u.role,
            is_active=u.is_active,
            last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
            created_at=u.created_at.isoformat(),
        )
        for u in users
    ]


class UserUpdate(BaseModel):
    """Request to update a user."""

    role: Optional[str] = None
    is_active: Optional[bool] = None


@router.patch(
    "/users/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_role(["admin", "owner"]))],
)
async def update_user(
    user_id: UUID,
    update: UserUpdate,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """
    Update a user's role or status.

    Requires admin or owner role.
    """
    result = await session.execute(
        select(User).where(
            User.id == user_id,
            User.organization_id == auth.organization_id,
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent self-demotion
    if auth.user_id == user_id and update.role and update.role != user.role:
        raise HTTPException(
            status_code=400,
            detail="Cannot change your own role",
        )

    if update.role is not None:
        if update.role not in ["owner", "admin", "member", "viewer"]:
            raise HTTPException(status_code=400, detail="Invalid role")
        user.role = update.role

    if update.is_active is not None:
        # Prevent self-deactivation
        if auth.user_id == user_id and not update.is_active:
            raise HTTPException(
                status_code=400,
                detail="Cannot deactivate your own account",
            )
        user.is_active = update.is_active

    await session.commit()
    await session.refresh(user)

    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
        created_at=user.created_at.isoformat(),
    )


# =============================================================================
# SYSTEM HEALTH (Admin Only)
# =============================================================================


@router.get(
    "/health",
    response_model=SystemHealth,
    dependencies=[Depends(require_role(["admin", "owner"]))],
)
async def get_system_health(
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """
    Get system health overview.

    Requires admin or owner role.
    """
    from agents.base import get_circuit_breaker_status

    # Check database
    try:
        await session.execute(select(1))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    # Check Redis (best effort)
    redis_status = "unknown"
    try:
        from redis.asyncio import Redis
        from config import get_settings

        settings = get_settings()
        redis = Redis.from_url(settings.redis_url)
        await redis.ping()
        redis_status = "healthy"
        await redis.close()
    except Exception:
        redis_status = "unhealthy"

    # Get circuit breaker status
    cb_status = get_circuit_breaker_status()
    cb_summary = {
        name: status["state"]
        for name, status in cb_status.items()
    }

    # Determine overall status
    overall = "healthy"
    if db_status != "healthy" or redis_status == "unhealthy":
        overall = "degraded"

    return SystemHealth(
        status=overall,
        database=db_status,
        redis=redis_status,
        workers="unknown",  # Would need to check ARQ worker status
        circuit_breakers=cb_summary,
        rate_limit_status={
            "enabled": True,
            "organization_rpm": 60,  # Could get from org settings
        },
    )
