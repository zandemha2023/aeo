"""Analytics and reporting API endpoints."""

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import Auth, CurrentOrg
from api.deps import get_session
from db.queries import get_client, get_latest_intelligence
from workflows.analytics import (
    run_analytics_workflow,
    run_technical_audit_workflow,
)

logger = structlog.get_logger()
router = APIRouter()


class GenerateReportRequest(BaseModel):
    """Request to generate a client report."""

    report_type: str = "monthly"  # weekly, monthly, quarterly
    include_technical: bool = False


class TechnicalAuditRequest(BaseModel):
    """Request for technical audit."""

    domain: str
    robots_txt: str | None = None
    sitemap: str | None = None
    sample_urls: list[str] | None = None


class GenerateReportResponse(BaseModel):
    """Response from report generation."""

    client_id: str
    report_type: str
    has_report: bool
    errors: list[str]


class TechnicalAuditResponse(BaseModel):
    """Response from technical audit."""

    client_id: str
    domain: str
    recommendations_count: int
    ai_crawler_status: dict
    errors: list[str]


class ReportSummary(BaseModel):
    """Summary of a client report."""

    report_type: str
    period: str
    executive_summary: str
    health_score: float | None
    wins_count: int
    challenges_count: int
    created_at: str


@router.post("/{client_id}/reports/generate", response_model=GenerateReportResponse)
async def generate_report(
    client_id: UUID,
    request: GenerateReportRequest,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """
    Generate a client report.

    Runs the analytics workflow to analyze performance data and generate
    a comprehensive report.
    """
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    logger.info(
        "generating_report",
        client_id=str(client_id),
        organization_id=str(auth.organization_id),
        report_type=request.report_type,
    )

    result = await run_analytics_workflow(
        session,
        auth.organization_id,
        client_id,
        client_name=client.name,
        domain=client.domain,
        report_type=request.report_type,
        include_technical=request.include_technical,
    )

    return GenerateReportResponse(
        client_id=str(client_id),
        report_type=request.report_type,
        has_report=result.get("client_report") is not None,
        errors=result.get("errors", []),
    )


@router.post("/{client_id}/technical-audit", response_model=TechnicalAuditResponse)
async def run_technical_audit(
    client_id: UUID,
    request: TechnicalAuditRequest,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """
    Run a technical SEO audit.

    Analyzes robots.txt, sitemap, and technical SEO factors for AI visibility.
    """
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    logger.info(
        "running_technical_audit",
        client_id=str(client_id),
        organization_id=str(auth.organization_id),
        domain=request.domain,
    )

    result = await run_technical_audit_workflow(
        session,
        auth.organization_id,
        client_id,
        domain=request.domain,
        robots_txt=request.robots_txt,
        sitemap=request.sitemap,
        sample_urls=request.sample_urls,
    )

    # Extract AI crawler status from technical audit
    ai_crawler_status = {}
    if result.get("technical_audit"):
        ai_crawler_status = result["technical_audit"].get("crawlability", {}).get("ai_crawler_access", {})

    return TechnicalAuditResponse(
        client_id=str(client_id),
        domain=request.domain,
        recommendations_count=len(result.get("combined_recommendations", [])),
        ai_crawler_status=ai_crawler_status,
        errors=result.get("errors", []),
    )


@router.get("/{client_id}/reports")
async def get_reports(
    client_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get all reports for a client."""
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    reports = []

    # Check for each report type
    for report_type in ["weekly", "monthly", "quarterly"]:
        intel = await get_latest_intelligence(
            session,
            auth.organization_id,
            client_id,
            f"client_report_{report_type}",
        )
        if intel:
            reports.append({
                "report_type": report_type,
                "created_at": intel.created_at.isoformat(),
                "data": intel.data,
            })

    return {"reports": reports}


@router.get("/{client_id}/reports/{report_type}")
async def get_report(
    client_id: UUID,
    report_type: str,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get a specific report type."""
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if report_type not in ["weekly", "monthly", "quarterly", "technical"]:
        raise HTTPException(status_code=400, detail="Invalid report type")

    intel = await get_latest_intelligence(
        session,
        auth.organization_id,
        client_id,
        f"client_report_{report_type}",
    )

    if not intel:
        raise HTTPException(
            status_code=404,
            detail=f"No {report_type} report found - generate one first",
        )

    return intel.data


@router.get("/{client_id}/reports/{report_type}/markdown")
async def get_report_as_markdown(
    client_id: UUID,
    report_type: str,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get a report formatted as markdown."""
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    intel = await get_latest_intelligence(
        session,
        auth.organization_id,
        client_id,
        f"client_report_{report_type}",
    )

    if not intel:
        raise HTTPException(
            status_code=404,
            detail=f"No {report_type} report found",
        )

    # Convert to markdown format
    report = intel.data
    lines = [
        f"# {report.get('client_name', '')} - AEO Performance Report",
        f"**Report Type:** {report.get('report_type', '').title()}",
        f"**Period:** {report.get('period', '')}",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        report.get("executive_summary", ""),
        "",
    ]

    # Key metrics
    if report.get("key_metrics"):
        lines.extend(["## Key Metrics", ""])
        for metric, value in report["key_metrics"].items():
            formatted = metric.replace("_", " ").title()
            if isinstance(value, float) and value <= 1:
                lines.append(f"- **{formatted}:** {value:.1%}")
            else:
                lines.append(f"- **{formatted}:** {value}")
        lines.append("")

    # Wins
    if report.get("wins"):
        lines.extend(["## Wins", ""])
        for win in report["wins"]:
            lines.append(f"- {win}")
        lines.append("")

    # Challenges
    if report.get("challenges"):
        lines.extend(["## Challenges", ""])
        for challenge in report["challenges"]:
            lines.append(f"- {challenge}")
        lines.append("")

    # Sections
    for section in report.get("sections", []):
        lines.extend([f"## {section.get('title', '')}", ""])
        lines.append(section.get("content", ""))
        lines.append("")

    # Next steps
    if report.get("next_steps"):
        lines.extend(["## Next Steps", ""])
        for i, step in enumerate(report["next_steps"], 1):
            lines.append(f"{i}. [{step.get('priority', '')}] {step.get('action', '')}")
        lines.append("")

    return {"markdown": "\n".join(lines)}


@router.get("/{client_id}/analysis")
async def get_performance_analysis(
    client_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get the latest performance analysis."""
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    intel = await get_latest_intelligence(
        session,
        auth.organization_id,
        client_id,
        "performance_analysis",
    )

    if not intel:
        raise HTTPException(
            status_code=404,
            detail="No analysis found - generate a report first",
        )

    return intel.data


@router.get("/{client_id}/technical-audit")
async def get_technical_audit(
    client_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get the latest technical audit results."""
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    intel = await get_latest_intelligence(
        session,
        auth.organization_id,
        client_id,
        "full_technical_audit",
    )

    if not intel:
        raise HTTPException(
            status_code=404,
            detail="No technical audit found - run one first",
        )

    return intel.data


@router.get("/{client_id}/technical-audit/recommendations")
async def get_technical_recommendations(
    client_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get prioritized technical recommendations."""
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    intel = await get_latest_intelligence(
        session,
        auth.organization_id,
        client_id,
        "full_technical_audit",
    )

    if not intel:
        raise HTTPException(
            status_code=404,
            detail="No technical audit found",
        )

    return {
        "recommendations": intel.data.get("combined_recommendations", []),
    }


@router.get("/{client_id}/schema-audit")
async def get_schema_audit(
    client_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get the latest schema audit results."""
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    intel = await get_latest_intelligence(
        session,
        auth.organization_id,
        client_id,
        "schema_audit",
    )

    if not intel:
        raise HTTPException(
            status_code=404,
            detail="No schema audit found",
        )

    return intel.data


@router.get("/{client_id}/dashboard")
async def get_dashboard_data(
    client_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """
    Get dashboard summary data for a client.

    Combines key metrics from various sources for dashboard display.
    """
    client = await get_client(session, auth.organization_id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    dashboard = {
        "client_id": str(client_id),
        "client_name": client.name,
        "domain": client.domain,
        "metrics": {},
        "recent_activity": [],
        "alerts": [],
    }

    # Get performance report
    perf_intel = await get_latest_intelligence(
        session,
        auth.organization_id,
        client_id,
        "performance_report",
    )
    if perf_intel:
        dashboard["metrics"]["health_score"] = perf_intel.data.get("health_score")
        dashboard["metrics"]["citation_rate"] = perf_intel.data.get("citation_rate")
        dashboard["metrics"]["sentiment_score"] = perf_intel.data.get("overall_sentiment")

    # Get analysis
    analysis_intel = await get_latest_intelligence(
        session,
        auth.organization_id,
        client_id,
        "performance_analysis",
    )
    if analysis_intel:
        dashboard["key_insights"] = analysis_intel.data.get("key_insights", [])[:5]
        dashboard["trends"] = analysis_intel.data.get("trends", [])[:3]

    # Get latest report summary
    for report_type in ["weekly", "monthly"]:
        report_intel = await get_latest_intelligence(
            session,
            auth.organization_id,
            client_id,
            f"client_report_{report_type}",
        )
        if report_intel:
            dashboard["latest_report"] = {
                "type": report_type,
                "executive_summary": report_intel.data.get("executive_summary", ""),
                "wins": report_intel.data.get("wins", [])[:3],
                "created_at": report_intel.created_at.isoformat(),
            }
            break

    return dashboard
