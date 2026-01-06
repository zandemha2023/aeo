"""
Background task definitions for AEO workflows.

These tasks are executed by the ARQ worker and run the
various workflows asynchronously.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from arq import ArqRedis

from agents.base import set_agent_context

logger = structlog.get_logger()


async def run_monitoring_job(
    ctx: dict[str, Any],
    organization_id: str,
    client_id: str,
) -> dict:
    """
    Run monitoring workflow for a client as a background job.

    Args:
        ctx: ARQ context with session_maker
        organization_id: Organization UUID string
        client_id: Client UUID string

    Returns:
        Job result with status and metrics
    """
    job_id = ctx.get("job_id", "unknown")
    logger.info(
        "monitoring_job_starting",
        job_id=job_id,
        organization_id=organization_id,
        client_id=client_id,
    )

    org_uuid = UUID(organization_id)
    client_uuid = UUID(client_id)

    # Set agent context for cost tracking
    set_agent_context(org_uuid, job_id)

    try:
        from workflows.monitoring import run_monitoring_workflow

        session_maker = ctx["session_maker"]
        async with session_maker() as session:
            result = await run_monitoring_workflow(
                session, org_uuid, client_uuid
            )

            return {
                "status": "completed",
                "job_id": job_id,
                "organization_id": organization_id,
                "client_id": client_id,
                "mentions_found": len([m for m in result["mentions"] if m.mentioned]),
                "alerts_created": len(result["alerts_created"]),
                "health_score": result["report"].overall_health_score if result["report"] else None,
                "errors": result["errors"],
                "completed_at": datetime.utcnow().isoformat(),
            }

    except Exception as e:
        logger.error(
            "monitoring_job_failed",
            job_id=job_id,
            error=str(e),
        )
        return {
            "status": "failed",
            "job_id": job_id,
            "organization_id": organization_id,
            "client_id": client_id,
            "error": str(e),
            "completed_at": datetime.utcnow().isoformat(),
        }

    finally:
        set_agent_context(None, None)


async def run_strategy_job(
    ctx: dict[str, Any],
    organization_id: str,
    client_id: str,
) -> dict:
    """
    Run strategy workflow for a client as a background job.

    Args:
        ctx: ARQ context with session_maker
        organization_id: Organization UUID string
        client_id: Client UUID string

    Returns:
        Job result with status and metrics
    """
    job_id = ctx.get("job_id", "unknown")
    logger.info(
        "strategy_job_starting",
        job_id=job_id,
        organization_id=organization_id,
        client_id=client_id,
    )

    org_uuid = UUID(organization_id)
    client_uuid = UUID(client_id)

    set_agent_context(org_uuid, job_id)

    try:
        from workflows.strategy import run_strategy_workflow

        session_maker = ctx["session_maker"]
        async with session_maker() as session:
            result = await run_strategy_workflow(
                session, org_uuid, client_uuid
            )

            return {
                "status": "completed",
                "job_id": job_id,
                "organization_id": organization_id,
                "client_id": client_id,
                "has_strategy": result["strategy"] is not None,
                "priorities_count": len(result["strategy"].priorities) if result["strategy"] else 0,
                "execution_plans_count": len(result["execution_plans"]),
                "errors": result["errors"],
                "completed_at": datetime.utcnow().isoformat(),
            }

    except Exception as e:
        logger.error(
            "strategy_job_failed",
            job_id=job_id,
            error=str(e),
        )
        return {
            "status": "failed",
            "job_id": job_id,
            "organization_id": organization_id,
            "client_id": client_id,
            "error": str(e),
            "completed_at": datetime.utcnow().isoformat(),
        }

    finally:
        set_agent_context(None, None)


async def run_content_job(
    ctx: dict[str, Any],
    organization_id: str,
    client_id: str,
    blueprints: list[dict] | None = None,
) -> dict:
    """
    Run content creation workflow for a client as a background job.

    Args:
        ctx: ARQ context with session_maker
        organization_id: Organization UUID string
        client_id: Client UUID string
        blueprints: Optional list of content blueprints

    Returns:
        Job result with status and metrics
    """
    job_id = ctx.get("job_id", "unknown")
    logger.info(
        "content_job_starting",
        job_id=job_id,
        organization_id=organization_id,
        client_id=client_id,
    )

    org_uuid = UUID(organization_id)
    client_uuid = UUID(client_id)

    set_agent_context(org_uuid, job_id)

    try:
        from workflows.content import run_content_workflow

        session_maker = ctx["session_maker"]
        async with session_maker() as session:
            result = await run_content_workflow(
                session, org_uuid, client_uuid, blueprints
            )

            passed_count = len([
                r for r in result["quality_reports"]
                if r["report"]["overall_passed"]
            ])

            return {
                "status": "completed",
                "job_id": job_id,
                "organization_id": organization_id,
                "client_id": client_id,
                "generated_count": len(result["generated_content"]),
                "passed_quality_count": passed_count,
                "failed_count": len(result["failed_content"]),
                "errors": result["errors"],
                "completed_at": datetime.utcnow().isoformat(),
            }

    except Exception as e:
        logger.error(
            "content_job_failed",
            job_id=job_id,
            error=str(e),
        )
        return {
            "status": "failed",
            "job_id": job_id,
            "organization_id": organization_id,
            "client_id": client_id,
            "error": str(e),
            "completed_at": datetime.utcnow().isoformat(),
        }

    finally:
        set_agent_context(None, None)


async def run_onboarding_job(
    ctx: dict[str, Any],
    organization_id: str,
    domain: str,
    company_name: str,
    additional_context: str = "",
) -> dict:
    """
    Run client onboarding workflow as a background job.

    Args:
        ctx: ARQ context with session_maker
        organization_id: Organization UUID string
        domain: Client website domain
        company_name: Client company name
        additional_context: Optional additional context

    Returns:
        Job result with status and new client ID
    """
    job_id = ctx.get("job_id", "unknown")
    logger.info(
        "onboarding_job_starting",
        job_id=job_id,
        organization_id=organization_id,
        domain=domain,
    )

    org_uuid = UUID(organization_id)

    set_agent_context(org_uuid, job_id)

    try:
        from workflows.onboarding import run_onboarding_workflow

        session_maker = ctx["session_maker"]
        async with session_maker() as session:
            result = await run_onboarding_workflow(
                session,
                org_uuid,
                domain,
                company_name,
                additional_context,
            )

            return {
                "status": "completed",
                "job_id": job_id,
                "organization_id": organization_id,
                "client_id": result["client_id"],
                "domain": domain,
                "queries_created": result["queries_created"],
                "has_profile": result["profile"] is not None,
                "errors": result["errors"],
                "completed_at": datetime.utcnow().isoformat(),
            }

    except Exception as e:
        logger.error(
            "onboarding_job_failed",
            job_id=job_id,
            error=str(e),
        )
        return {
            "status": "failed",
            "job_id": job_id,
            "organization_id": organization_id,
            "domain": domain,
            "error": str(e),
            "completed_at": datetime.utcnow().isoformat(),
        }

    finally:
        set_agent_context(None, None)
