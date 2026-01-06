"""Client management API endpoints."""

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import Auth, CurrentOrg
from api.deps import get_session
from db.models import Organization
from db.queries import (
    create_client,
    get_client,
    get_client_by_domain,
    list_active_clients,
    get_latest_intelligence,
)
from knowledge.client_kb import ClientKnowledgeBase
from workflows.onboarding import run_onboarding_workflow

logger = structlog.get_logger()
router = APIRouter()


class ClientCreate(BaseModel):
    """Request to create/onboard a new client."""

    name: str
    domain: str
    additional_context: str = ""


class ClientResponse(BaseModel):
    """Client response model."""

    id: str
    name: str
    domain: str
    status: str
    has_profile: bool


class OnboardingResponse(BaseModel):
    """Response from onboarding workflow."""

    client_id: str
    status: str
    queries_created: int
    errors: list[str]


@router.post("/onboard", response_model=OnboardingResponse)
async def onboard_client(
    request: ClientCreate,
    auth: Auth,
    org: CurrentOrg,
    session: AsyncSession = Depends(get_session),
):
    """
    Onboard a new client.

    This triggers the full onboarding workflow:
    1. Creates client record
    2. Runs Cartographer for intelligence gathering
    3. Generates monitoring queries
    """
    logger.info(
        "onboarding_client",
        domain=request.domain,
        organization_id=str(auth.organization_id),
    )

    # Check if already exists within this organization
    existing = await get_client_by_domain(session, auth.organization_id, request.domain)
    if existing:
        # Return existing client info
        return OnboardingResponse(
            client_id=str(existing.id),
            status="already_exists",
            queries_created=0,
            errors=[],
        )

    # Run onboarding workflow
    result = await run_onboarding_workflow(
        session,
        auth.organization_id,
        request.domain,
        request.name,
        request.additional_context,
    )

    return OnboardingResponse(
        client_id=result["client_id"] or "",
        status="complete" if not result["errors"] else "partial",
        queries_created=result["queries_created"],
        errors=result["errors"],
    )


@router.get("/", response_model=list[ClientResponse])
async def list_clients(
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """List all active clients for the organization."""
    clients = await list_active_clients(session, auth.organization_id)

    responses = []
    for client in clients:
        # Check if profile exists
        intel = await get_latest_intelligence(
            session, auth.organization_id, client.id, "cartographer"
        )
        has_profile = intel is not None

        responses.append(
            ClientResponse(
                id=str(client.id),
                name=client.name,
                domain=client.domain,
                status=client.status,
                has_profile=has_profile,
            )
        )

    return responses


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client_by_id(
    client_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get a specific client."""
    client = await get_client(session, auth.organization_id, client_id)

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    intel = await get_latest_intelligence(
        session, auth.organization_id, client.id, "cartographer"
    )

    return ClientResponse(
        id=str(client.id),
        name=client.name,
        domain=client.domain,
        status=client.status,
        has_profile=intel is not None,
    )


@router.get("/{client_id}/profile")
async def get_client_profile(
    client_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get the full client intelligence profile."""
    client = await get_client(session, auth.organization_id, client_id)

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    kb = ClientKnowledgeBase(session, auth.organization_id, client_id)
    profile = await kb.get_client_profile()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found - run onboarding first")

    return profile.model_dump()


@router.get("/{client_id}/context")
async def get_client_context(
    client_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get complete client context (all intelligence)."""
    client = await get_client(session, auth.organization_id, client_id)

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    kb = ClientKnowledgeBase(session, auth.organization_id, client_id)
    context = await kb.get_full_context()

    return context
