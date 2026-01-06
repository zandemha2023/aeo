"""
Job scheduling for periodic monitoring and batch operations.

Handles:
- Scheduled monitoring runs for all active clients
- Job queue management
- Schedule status tracking
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from arq import ArqRedis

logger = structlog.get_logger()


async def run_scheduled_monitoring(ctx: dict[str, Any]) -> dict:
    """
    Run monitoring for all active clients.

    This is triggered by the cron schedule in worker settings.
    It enqueues individual monitoring jobs for each client.
    """
    logger.info("scheduled_monitoring_starting")

    from db.queries import get_session_maker
    from sqlalchemy import select, and_
    from db.models import Client, Organization

    session_maker = ctx.get("session_maker") or get_session_maker()
    redis: ArqRedis = ctx.get("redis")

    jobs_enqueued = 0
    errors = []

    try:
        async with session_maker() as session:
            # Get all active organizations
            from db.models import Organization
            org_result = await session.execute(
                select(Organization).where(Organization.status == "active")
            )
            organizations = list(org_result.scalars().all())

            for org in organizations:
                # Get active clients for this org
                client_result = await session.execute(
                    select(Client).where(
                        and_(
                            Client.organization_id == org.id,
                            Client.status == "active",
                        )
                    )
                )
                clients = list(client_result.scalars().all())

                for client in clients:
                    try:
                        # Enqueue monitoring job
                        if redis:
                            await redis.enqueue_job(
                                "run_monitoring_job",
                                str(org.id),
                                str(client.id),
                                _queue_name="aeo:queue",
                            )
                            jobs_enqueued += 1
                            logger.info(
                                "monitoring_job_enqueued",
                                organization_id=str(org.id),
                                client_id=str(client.id),
                            )
                    except Exception as e:
                        error_msg = f"Failed to enqueue job for client {client.id}: {e}"
                        errors.append(error_msg)
                        logger.error(
                            "job_enqueue_failed",
                            client_id=str(client.id),
                            error=str(e),
                        )

    except Exception as e:
        logger.error("scheduled_monitoring_failed", error=str(e))
        errors.append(f"Scheduler error: {e}")

    result = {
        "status": "completed",
        "jobs_enqueued": jobs_enqueued,
        "errors": errors,
        "completed_at": datetime.utcnow().isoformat(),
    }

    logger.info(
        "scheduled_monitoring_complete",
        jobs_enqueued=jobs_enqueued,
        errors=len(errors),
    )

    return result


async def schedule_monitoring(
    redis: ArqRedis,
    organization_id: UUID,
    client_id: UUID,
    delay_seconds: int = 0,
) -> str | None:
    """
    Schedule a monitoring job for a specific client.

    Args:
        redis: ARQ Redis connection
        organization_id: Organization UUID
        client_id: Client UUID
        delay_seconds: Delay before running (0 = immediate)

    Returns:
        Job ID if successfully enqueued, None otherwise
    """
    try:
        job = await redis.enqueue_job(
            "run_monitoring_job",
            str(organization_id),
            str(client_id),
            _queue_name="aeo:queue",
            _defer_by=timedelta(seconds=delay_seconds) if delay_seconds > 0 else None,
        )

        if job:
            logger.info(
                "monitoring_scheduled",
                job_id=job.job_id,
                organization_id=str(organization_id),
                client_id=str(client_id),
                delay_seconds=delay_seconds,
            )
            return job.job_id

    except Exception as e:
        logger.error(
            "schedule_monitoring_failed",
            organization_id=str(organization_id),
            client_id=str(client_id),
            error=str(e),
        )

    return None


async def schedule_all_client_monitoring(
    redis: ArqRedis,
    organization_id: UUID,
    stagger_seconds: int = 30,
) -> list[str]:
    """
    Schedule monitoring for all clients in an organization.

    Jobs are staggered to avoid overwhelming the worker.

    Args:
        redis: ARQ Redis connection
        organization_id: Organization UUID
        stagger_seconds: Delay between each job

    Returns:
        List of job IDs
    """
    from db.deps import get_session_context
    from db.queries import list_active_clients

    job_ids = []

    async with get_session_context() as session:
        clients = await list_active_clients(session, organization_id)

        for i, client in enumerate(clients):
            delay = i * stagger_seconds
            job_id = await schedule_monitoring(
                redis, organization_id, client.id, delay
            )
            if job_id:
                job_ids.append(job_id)

    logger.info(
        "all_monitoring_scheduled",
        organization_id=str(organization_id),
        job_count=len(job_ids),
    )

    return job_ids


async def get_scheduled_jobs(redis: ArqRedis) -> list[dict]:
    """
    Get list of scheduled/pending jobs.

    Returns basic info about jobs in the queue.
    """
    try:
        # Get queued jobs
        queued = await redis.queued_jobs()

        jobs = []
        for job in queued:
            jobs.append({
                "job_id": job.job_id,
                "function": job.function,
                "enqueue_time": job.enqueue_time.isoformat() if job.enqueue_time else None,
                "score": job.score,
            })

        return jobs

    except Exception as e:
        logger.error("get_scheduled_jobs_failed", error=str(e))
        return []


async def get_job_result(redis: ArqRedis, job_id: str) -> dict | None:
    """
    Get the result of a completed job.

    Args:
        redis: ARQ Redis connection
        job_id: Job ID to look up

    Returns:
        Job result dict or None if not found/not complete
    """
    try:
        from arq.jobs import Job
        job = Job(job_id, redis)
        info = await job.info()

        if info is None:
            return None

        return {
            "job_id": job_id,
            "function": info.function,
            "status": info.status.value if info.status else "unknown",
            "enqueue_time": info.enqueue_time.isoformat() if info.enqueue_time else None,
            "start_time": info.start_time.isoformat() if info.start_time else None,
            "finish_time": info.finish_time.isoformat() if info.finish_time else None,
            "result": info.result,
            "success": info.success,
        }

    except Exception as e:
        logger.error("get_job_result_failed", job_id=job_id, error=str(e))
        return None


async def cancel_job(redis: ArqRedis, job_id: str) -> bool:
    """
    Cancel a pending job.

    Args:
        redis: ARQ Redis connection
        job_id: Job ID to cancel

    Returns:
        True if cancelled, False otherwise
    """
    try:
        from arq.jobs import Job
        job = Job(job_id, redis)
        await job.abort()

        logger.info("job_cancelled", job_id=job_id)
        return True

    except Exception as e:
        logger.error("cancel_job_failed", job_id=job_id, error=str(e))
        return False
