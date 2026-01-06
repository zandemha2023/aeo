"""Content creation and optimization API endpoints."""

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import Auth, CurrentOrg
from api.deps import get_session
from db.queries import get_client, get_latest_intelligence
from workflows.content import run_content_workflow, run_optimization_workflow

logger = structlog.get_logger()
router = APIRouter()


class ContentGenerateRequest(BaseModel):
    """Request to generate content."""

    blueprints: list[dict] | None = None  # If not provided, uses architect output


class ContentOptimizeRequest(BaseModel):
    """Request to optimize existing content."""

    content_items: list[dict]  # url, title, content, score, target_queries


class ContentGenerateResponse(BaseModel):
    """Response from content generation."""

    client_id: str
    generated_count: int
    passed_quality_count: int
    failed_count: int
    errors: list[str]


class ContentOptimizeResponse(BaseModel):
    """Response from content optimization."""

    client_id: str
    optimized_count: int
    average_improvement: float
    errors: list[str]


class QualityReportResponse(BaseModel):
    """Quality report for a content piece."""

    title: str
    overall_passed: bool
    passed_gates: int
    failed_gates: int
    warnings: int
    gate_results: list[dict]


@router.post("/{client_id}/generate", response_model=ContentGenerateResponse)
async def generate_content(
    client_id: UUID,
    request: ContentGenerateRequest,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """
    Generate content from blueprints.

    If blueprints are not provided, uses the latest execution plans from The Architect.
    Runs quality gates on all generated content.
    """
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    logger.info(
        "generating_content",
        client_id=str(client_id),
        organization_id=str(auth.organization_id),
    )

    result = await run_content_workflow(
        session,
        auth.organization_id,
        client_id,
        blueprints=request.blueprints,
    )

    passed_count = len([
        r for r in result["quality_reports"]
        if r["report"]["overall_passed"]
    ])

    return ContentGenerateResponse(
        client_id=str(client_id),
        generated_count=len(result["generated_content"]),
        passed_quality_count=passed_count,
        failed_count=len(result["failed_content"]),
        errors=result["errors"],
    )


@router.post("/{client_id}/optimize", response_model=ContentOptimizeResponse)
async def optimize_content(
    client_id: UUID,
    request: ContentOptimizeRequest,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """
    Optimize existing content for AI citation.

    Provide a list of content items with their current text and citability score.
    """
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if not request.content_items:
        raise HTTPException(status_code=400, detail="No content items provided")

    logger.info(
        "optimizing_content",
        client_id=str(client_id),
        organization_id=str(auth.organization_id),
        items=len(request.content_items),
    )

    result = await run_optimization_workflow(
        session,
        auth.organization_id,
        client_id,
        content_items=request.content_items,
    )

    # Calculate average improvement
    improvements = [
        o.get("improvement_percentage", 0)
        for o in result["optimizations"]
    ]
    avg_improvement = sum(improvements) / len(improvements) if improvements else 0

    return ContentOptimizeResponse(
        client_id=str(client_id),
        optimized_count=len(result["optimizations"]),
        average_improvement=round(avg_improvement, 1),
        errors=result["errors"],
    )


@router.get("/{client_id}/generated")
async def get_generated_content(
    client_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get all generated content for a client."""
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    content_intel = await get_latest_intelligence(
        session, auth.organization_id, client_id, "content_generated"
    )
    if not content_intel:
        raise HTTPException(
            status_code=404,
            detail="No generated content found - run content generation first",
        )

    return content_intel.data


@router.get("/{client_id}/generated/approved")
async def get_approved_content(
    client_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get approved content that passed quality gates."""
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    content_intel = await get_latest_intelligence(
        session, auth.organization_id, client_id, "content_generated"
    )
    if not content_intel:
        raise HTTPException(
            status_code=404,
            detail="No generated content found - run content generation first",
        )

    return content_intel.data.get("approved_content", [])


@router.get("/{client_id}/generated/{index}")
async def get_generated_content_by_index(
    client_id: UUID,
    index: int,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get a specific generated content piece by index."""
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    content_intel = await get_latest_intelligence(
        session, auth.organization_id, client_id, "content_generated"
    )
    if not content_intel:
        raise HTTPException(
            status_code=404,
            detail="No generated content found",
        )

    all_content = content_intel.data.get("all_content", [])
    if index < 0 or index >= len(all_content):
        raise HTTPException(status_code=404, detail="Content index out of range")

    return all_content[index]


@router.get("/{client_id}/generated/{index}/markdown")
async def get_content_as_markdown(
    client_id: UUID,
    index: int,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get a specific generated content piece as markdown."""
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    content_intel = await get_latest_intelligence(
        session, auth.organization_id, client_id, "content_generated"
    )
    if not content_intel:
        raise HTTPException(
            status_code=404,
            detail="No generated content found",
        )

    all_content = content_intel.data.get("all_content", [])
    if index < 0 or index >= len(all_content):
        raise HTTPException(status_code=404, detail="Content index out of range")

    content = all_content[index]

    # Convert to markdown
    lines = [f"# {content.get('title', '')}", ""]

    for section in content.get("sections", []):
        lines.append(f"## {section.get('heading', '')}")
        lines.append("")
        lines.append(section.get("content", ""))
        lines.append("")

    return {"markdown": "\n".join(lines)}


@router.get("/{client_id}/quality-reports", response_model=list[QualityReportResponse])
async def get_quality_reports(
    client_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get quality reports for generated content."""
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    content_intel = await get_latest_intelligence(
        session, auth.organization_id, client_id, "content_generated"
    )
    if not content_intel:
        raise HTTPException(
            status_code=404,
            detail="No generated content found",
        )

    reports = content_intel.data.get("quality_reports", [])

    return [
        QualityReportResponse(
            title=r.get("title", ""),
            overall_passed=r["report"]["overall_passed"],
            passed_gates=r["report"]["passed_gates"],
            failed_gates=r["report"]["failed_gates"],
            warnings=r["report"]["warnings"],
            gate_results=r["report"]["gate_results"],
        )
        for r in reports
    ]


@router.get("/{client_id}/optimizations")
async def get_optimizations(
    client_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get optimization results for a client."""
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    opt_intel = await get_latest_intelligence(
        session, auth.organization_id, client_id, "content_optimizations"
    )
    if not opt_intel:
        raise HTTPException(
            status_code=404,
            detail="No optimizations found - run content optimization first",
        )

    return opt_intel.data


@router.get("/{client_id}/optimizations/{index}")
async def get_optimization_by_index(
    client_id: UUID,
    index: int,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get a specific optimization result."""
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    opt_intel = await get_latest_intelligence(
        session, auth.organization_id, client_id, "content_optimizations"
    )
    if not opt_intel:
        raise HTTPException(
            status_code=404,
            detail="No optimizations found",
        )

    optimizations = opt_intel.data.get("optimizations", [])
    if index < 0 or index >= len(optimizations):
        raise HTTPException(status_code=404, detail="Optimization index out of range")

    return optimizations[index]
