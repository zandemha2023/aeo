"""Strategy API endpoints."""

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import Auth, CurrentOrg
from api.deps import get_session
from db.queries import get_client, get_latest_intelligence
from knowledge.client_kb import ClientKnowledgeBase
from workflows.strategy import run_strategy_workflow

logger = structlog.get_logger()
router = APIRouter()


class StrategyRunResponse(BaseModel):
    """Response from running strategy workflow."""

    client_id: str
    has_strategy: bool
    priorities_count: int
    execution_plans_count: int
    errors: list[str]


class StrategySummaryResponse(BaseModel):
    """Summary of client's strategy."""

    executive_summary: str
    strategic_thesis: str
    health_summary: str
    priorities: list[dict]
    day_30_goals: list[str]
    day_60_goals: list[str]
    day_90_goals: list[str]


class ExecutionPlanResponse(BaseModel):
    """Execution plan response."""

    strategic_priority: str
    initiatives: list[dict]


@router.post("/{client_id}/generate", response_model=StrategyRunResponse)
async def generate_strategy(
    client_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """
    Generate full AEO strategy for a client.

    This runs the complete strategy workflow:
    1. Gathers intelligence (Cartographer, Scout, Librarian, Auditor)
    2. Synthesizes strategy (Strategist)
    3. Creates execution plans (Architect)
    """
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    logger.info(
        "generating_strategy",
        client_id=str(client_id),
        organization_id=str(auth.organization_id),
    )

    result = await run_strategy_workflow(session, auth.organization_id, client_id)

    return StrategyRunResponse(
        client_id=str(client_id),
        has_strategy=result["strategy"] is not None,
        priorities_count=len(result["strategy"].priorities) if result["strategy"] else 0,
        execution_plans_count=len(result["execution_plans"]),
        errors=result["errors"],
    )


@router.get("/{client_id}", response_model=StrategySummaryResponse)
async def get_strategy(
    client_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get the current strategy for a client."""
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    strategy_intel = await get_latest_intelligence(
        session, auth.organization_id, client_id, "strategist"
    )
    if not strategy_intel:
        raise HTTPException(
            status_code=404,
            detail="No strategy found - run strategy generation first",
        )

    data = strategy_intel.data

    return StrategySummaryResponse(
        executive_summary=data.get("executive_summary", ""),
        strategic_thesis=data.get("strategic_thesis", ""),
        health_summary=data.get("current_state_assessment", {}).get("health_summary", ""),
        priorities=data.get("priorities", []),
        day_30_goals=data.get("day_30_goals", []),
        day_60_goals=data.get("day_60_goals", []),
        day_90_goals=data.get("day_90_goals", []),
    )


@router.get("/{client_id}/full")
async def get_full_strategy(
    client_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get the complete strategy details."""
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    strategy_intel = await get_latest_intelligence(
        session, auth.organization_id, client_id, "strategist"
    )
    if not strategy_intel:
        raise HTTPException(
            status_code=404,
            detail="No strategy found - run strategy generation first",
        )

    return strategy_intel.data


@router.get("/{client_id}/execution-plans", response_model=list[ExecutionPlanResponse])
async def get_execution_plans(
    client_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get execution plans for a client."""
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    architect_intel = await get_latest_intelligence(
        session, auth.organization_id, client_id, "architect"
    )
    if not architect_intel:
        raise HTTPException(
            status_code=404,
            detail="No execution plans found - run strategy generation first",
        )

    plans = architect_intel.data.get("plans", [])

    return [
        ExecutionPlanResponse(
            strategic_priority=plan.get("strategic_priority_addressed", ""),
            initiatives=plan.get("initiatives", []),
        )
        for plan in plans
    ]


@router.get("/{client_id}/content-calendar")
async def get_content_calendar(
    client_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get content calendar derived from execution plans."""
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    architect_intel = await get_latest_intelligence(
        session, auth.organization_id, client_id, "architect"
    )
    if not architect_intel:
        raise HTTPException(
            status_code=404,
            detail="No execution plans found - run strategy generation first",
        )

    plans = architect_intel.data.get("plans", [])
    calendar = []

    for plan in plans:
        for initiative in plan.get("initiatives", []):
            for i, content in enumerate(initiative.get("content_pieces", [])):
                calendar.append({
                    "initiative": initiative.get("name", ""),
                    "content_title": content.get("title", ""),
                    "content_type": content.get("content_type", ""),
                    "target_queries": content.get("target_queries", []),
                    "target_length": content.get("target_length", ""),
                    "priority": i + 1,
                    "acceptance_criteria": content.get("acceptance_criteria", []),
                })

    return calendar


@router.get("/{client_id}/intelligence")
async def get_all_intelligence(
    client_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get all intelligence gathered for a client."""
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    kb = ClientKnowledgeBase(session, auth.organization_id, client_id)
    context = await kb.get_full_context()

    return context


@router.get("/{client_id}/competitive")
async def get_competitive_intelligence(
    client_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get competitive intelligence for a client."""
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    kb = ClientKnowledgeBase(session, auth.organization_id, client_id)
    competitive = await kb.get_competitive_intelligence()

    if not competitive:
        raise HTTPException(
            status_code=404,
            detail="No competitive intelligence found - run strategy generation first",
        )

    return competitive.model_dump()


@router.get("/{client_id}/content-analysis")
async def get_content_analysis(
    client_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get content analysis for a client."""
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    kb = ClientKnowledgeBase(session, auth.organization_id, client_id)
    content = await kb.get_content_analysis()

    if not content:
        raise HTTPException(
            status_code=404,
            detail="No content analysis found - run strategy generation first",
        )

    return content.model_dump()
