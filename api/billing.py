"""
Billing and usage invoicing API endpoints.

Provides REST API for:
- Usage invoices and cost breakdowns
- Budget management
- Plan management
- Usage export
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
from db.models import LLMUsage, Organization

logger = structlog.get_logger()
router = APIRouter()


# =============================================================================
# RESPONSE MODELS
# =============================================================================


class UsageLineItem(BaseModel):
    """Individual usage line item."""

    date: str
    agent: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    requests: int


class Invoice(BaseModel):
    """Usage invoice for a billing period."""

    invoice_id: str
    organization_id: str
    organization_name: str
    period_start: str
    period_end: str
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    line_items: list[UsageLineItem]
    generated_at: str


class BudgetStatus(BaseModel):
    """Current budget status."""

    monthly_budget_usd: float
    current_month_spend_usd: float
    percent_used: float
    remaining_usd: float
    projected_month_end_usd: float
    status: str  # ok, warning, critical, exceeded
    days_remaining: int


class PlanInfo(BaseModel):
    """Organization plan information."""

    plan: str
    monthly_budget_usd: float
    rate_limit_rpm: int
    features: list[str]


class PlanUpdateRequest(BaseModel):
    """Request to update organization plan."""

    plan: str
    monthly_budget_usd: Optional[float] = None


# =============================================================================
# INVOICE ENDPOINTS
# =============================================================================


@router.get("/invoices/current", response_model=Invoice)
async def get_current_invoice(
    auth: Auth,
    org: CurrentOrg,
    session: AsyncSession = Depends(get_session),
):
    """
    Get the current month's usage invoice.

    Returns detailed breakdown of LLM usage and costs.
    """
    # Current month boundaries
    now = datetime.utcnow()
    period_start = datetime(now.year, now.month, 1)
    if now.month == 12:
        period_end = datetime(now.year + 1, 1, 1)
    else:
        period_end = datetime(now.year, now.month + 1, 1)

    return await _generate_invoice(
        session,
        auth.organization_id,
        org.name,
        period_start,
        period_end,
    )


@router.get("/invoices/{year}/{month}", response_model=Invoice)
async def get_monthly_invoice(
    year: int,
    month: int,
    auth: Auth,
    org: CurrentOrg,
    session: AsyncSession = Depends(get_session),
):
    """
    Get invoice for a specific month.

    Useful for historical billing records.
    """
    if not (1 <= month <= 12) or year < 2020 or year > 2100:
        raise HTTPException(status_code=400, detail="Invalid year or month")

    period_start = datetime(year, month, 1)
    if month == 12:
        period_end = datetime(year + 1, 1, 1)
    else:
        period_end = datetime(year, month + 1, 1)

    return await _generate_invoice(
        session,
        auth.organization_id,
        org.name,
        period_start,
        period_end,
    )


async def _generate_invoice(
    session: AsyncSession,
    organization_id: UUID,
    organization_name: str,
    period_start: datetime,
    period_end: datetime,
) -> Invoice:
    """Generate an invoice for the specified period."""
    result = await session.execute(
        select(LLMUsage).where(
            LLMUsage.organization_id == organization_id,
            LLMUsage.created_at >= period_start,
            LLMUsage.created_at < period_end,
        ).order_by(LLMUsage.created_at)
    )
    usage_records = result.scalars().all()

    # Aggregate by date + agent + model
    line_items_dict: dict[tuple, dict] = {}
    for r in usage_records:
        date_key = r.created_at.strftime("%Y-%m-%d")
        key = (date_key, r.agent, r.model)

        if key not in line_items_dict:
            line_items_dict[key] = {
                "date": date_key,
                "agent": r.agent,
                "model": r.model,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
                "requests": 0,
            }

        line_items_dict[key]["input_tokens"] += r.input_tokens
        line_items_dict[key]["output_tokens"] += r.output_tokens
        line_items_dict[key]["cost_usd"] += float(r.cost_usd)
        line_items_dict[key]["requests"] += 1

    line_items = [
        UsageLineItem(**item) for item in sorted(line_items_dict.values(), key=lambda x: x["date"])
    ]

    # Calculate totals
    total_requests = len(usage_records)
    total_input_tokens = sum(r.input_tokens for r in usage_records)
    total_output_tokens = sum(r.output_tokens for r in usage_records)
    total_cost = sum(float(r.cost_usd) for r in usage_records)

    # Generate invoice ID
    invoice_id = f"INV-{organization_id.hex[:8]}-{period_start.strftime('%Y%m')}"

    return Invoice(
        invoice_id=invoice_id,
        organization_id=str(organization_id),
        organization_name=organization_name,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        total_requests=total_requests,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_cost_usd=round(total_cost, 4),
        line_items=line_items,
        generated_at=datetime.utcnow().isoformat(),
    )


# =============================================================================
# BUDGET ENDPOINTS
# =============================================================================


@router.get("/budget", response_model=BudgetStatus)
async def get_budget_status(
    auth: Auth,
    org: CurrentOrg,
    session: AsyncSession = Depends(get_session),
):
    """
    Get current budget status.

    Returns spending, projections, and alerts.
    """
    now = datetime.utcnow()
    period_start = datetime(now.year, now.month, 1)

    # Get current month spend
    result = await session.scalar(
        select(func.sum(LLMUsage.cost_usd)).where(
            LLMUsage.organization_id == auth.organization_id,
            LLMUsage.created_at >= period_start,
        )
    )
    current_spend = float(result or Decimal("0"))

    monthly_budget = float(org.monthly_llm_budget_usd or Decimal("100"))

    # Calculate projections
    days_elapsed = (now - period_start).days + 1
    days_in_month = 30  # Simplified
    days_remaining = max(0, days_in_month - days_elapsed)

    daily_rate = current_spend / days_elapsed if days_elapsed > 0 else 0
    projected_month_end = current_spend + (daily_rate * days_remaining)

    percent_used = (current_spend / monthly_budget * 100) if monthly_budget > 0 else 0
    remaining = max(0, monthly_budget - current_spend)

    # Determine status
    if percent_used >= 100:
        status = "exceeded"
    elif percent_used >= 90:
        status = "critical"
    elif percent_used >= 75:
        status = "warning"
    else:
        status = "ok"

    return BudgetStatus(
        monthly_budget_usd=monthly_budget,
        current_month_spend_usd=round(current_spend, 4),
        percent_used=round(percent_used, 2),
        remaining_usd=round(remaining, 4),
        projected_month_end_usd=round(projected_month_end, 4),
        status=status,
        days_remaining=days_remaining,
    )


@router.patch(
    "/budget",
    dependencies=[Depends(require_role(["admin", "owner"]))],
)
async def update_budget(
    auth: Auth,
    org: CurrentOrg,
    budget_usd: float = Query(..., gt=0, le=100000),
    session: AsyncSession = Depends(get_session),
):
    """
    Update the monthly LLM budget.

    Requires admin or owner role.
    """
    org.monthly_llm_budget_usd = Decimal(str(budget_usd))
    await session.commit()

    return {
        "status": "updated",
        "monthly_budget_usd": float(org.monthly_llm_budget_usd),
    }


# =============================================================================
# PLAN ENDPOINTS
# =============================================================================


PLAN_FEATURES = {
    "free": {
        "rate_limit_rpm": 30,
        "default_budget": 50,
        "features": ["Basic monitoring", "Up to 5 clients", "Email support"],
    },
    "starter": {
        "rate_limit_rpm": 60,
        "default_budget": 200,
        "features": [
            "Standard monitoring",
            "Up to 25 clients",
            "Webhooks",
            "Priority support",
        ],
    },
    "pro": {
        "rate_limit_rpm": 120,
        "default_budget": 500,
        "features": [
            "Advanced monitoring",
            "Unlimited clients",
            "Webhooks",
            "Custom integrations",
            "Dedicated support",
        ],
    },
    "enterprise": {
        "rate_limit_rpm": 300,
        "default_budget": 2000,
        "features": [
            "Enterprise monitoring",
            "Unlimited clients",
            "Webhooks",
            "Custom integrations",
            "SSO",
            "SLA",
            "Dedicated account manager",
        ],
    },
}


@router.get("/plan", response_model=PlanInfo)
async def get_plan_info(
    org: CurrentOrg,
):
    """Get current plan information."""
    plan_data = PLAN_FEATURES.get(org.plan, PLAN_FEATURES["free"])

    return PlanInfo(
        plan=org.plan,
        monthly_budget_usd=float(org.monthly_llm_budget_usd),
        rate_limit_rpm=org.rate_limit_rpm,
        features=plan_data["features"],
    )


@router.get("/plans")
async def list_available_plans():
    """List all available plans and their features."""
    return {
        "plans": [
            {
                "name": plan,
                "rate_limit_rpm": data["rate_limit_rpm"],
                "default_budget_usd": data["default_budget"],
                "features": data["features"],
            }
            for plan, data in PLAN_FEATURES.items()
        ]
    }


# =============================================================================
# EXPORT ENDPOINTS
# =============================================================================


@router.get("/export/csv")
async def export_usage_csv(
    auth: Auth,
    days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
):
    """
    Export usage data as CSV.

    Returns CSV-formatted usage data for the specified period.
    """
    from fastapi.responses import StreamingResponse
    import io
    import csv

    period_start = datetime.utcnow() - timedelta(days=days)

    result = await session.execute(
        select(LLMUsage).where(
            LLMUsage.organization_id == auth.organization_id,
            LLMUsage.created_at >= period_start,
        ).order_by(LLMUsage.created_at)
    )
    usage_records = result.scalars().all()

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "timestamp",
        "agent",
        "workflow",
        "model",
        "input_tokens",
        "output_tokens",
        "cost_usd",
        "success",
    ])

    # Data rows
    for r in usage_records:
        writer.writerow([
            r.created_at.isoformat(),
            r.agent,
            r.workflow or "",
            r.model,
            r.input_tokens,
            r.output_tokens,
            float(r.cost_usd),
            r.success,
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=aeo-usage-{datetime.utcnow().strftime('%Y%m%d')}.csv"
        },
    )
