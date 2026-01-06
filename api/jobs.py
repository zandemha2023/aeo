"""
API endpoints for job management and monitoring.

Provides REST API for:
- Viewing job status and results
- Listing scheduled/pending jobs
- Scheduling on-demand jobs
- Cancelling pending jobs
"""

from typing import Optional
from uuid import UUID

import structlog
from arq import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from redis.asyncio import Redis

from api.auth import Auth
from config import get_settings
from jobs.scheduler import (
    cancel_job,
    get_job_result,
    get_scheduled_jobs,
    schedule_all_client_monitoring,
    schedule_monitoring,
)

logger = structlog.get_logger()
router = APIRouter()

settings = get_settings()


class ScheduleMonitoringRequest(BaseModel):
    """Request to schedule monitoring for a client."""
    client_id: UUID
    delay_seconds: int = 0


class ScheduleAllMonitoringRequest(BaseModel):
    """Request to schedule monitoring for all clients."""
    stagger_seconds: int = 30


class JobResponse(BaseModel):
    """Response containing job information."""
    job_id: str
    status: str
    function: Optional[str] = None
    enqueue_time: Optional[str] = None
    start_time: Optional[str] = None
    finish_time: Optional[str] = None
    result: Optional[dict] = None
    success: Optional[bool] = None


async def get_redis() -> ArqRedis:
    """Get ARQ Redis connection."""
    from arq import create_pool
    from arq.connections import RedisSettings

    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    pool = await create_pool(redis_settings)
    return pool


@router.get("/")
async def list_jobs(
    auth: Auth,
):
    """
    List all scheduled/pending jobs.

    Returns jobs in the queue awaiting execution.
    """
    try:
        redis = await get_redis()
        jobs = await get_scheduled_jobs(redis)
        await redis.close()

        return {
            "organization_id": str(auth.organization_id),
            "jobs": jobs,
            "count": len(jobs),
        }
    except Exception as e:
        logger.error("list_jobs_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list jobs: {str(e)}",
        )


@router.get("/{job_id}")
async def get_job_status(
    job_id: str,
    auth: Auth,
):
    """
    Get status and result of a specific job.

    Returns detailed information including result if completed.
    """
    try:
        redis = await get_redis()
        result = await get_job_result(redis, job_id)
        await redis.close()

        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"Job {job_id} not found",
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_job_status_failed", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get job status: {str(e)}",
        )


@router.post("/schedule/monitoring")
async def schedule_monitoring_job(
    request: ScheduleMonitoringRequest,
    auth: Auth,
):
    """
    Schedule a monitoring job for a specific client.

    Optionally delay execution by delay_seconds.
    """
    try:
        redis = await get_redis()
        job_id = await schedule_monitoring(
            redis,
            auth.organization_id,
            request.client_id,
            request.delay_seconds,
        )
        await redis.close()

        if job_id is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to schedule monitoring job",
            )

        return {
            "job_id": job_id,
            "status": "scheduled",
            "organization_id": str(auth.organization_id),
            "client_id": str(request.client_id),
            "delay_seconds": request.delay_seconds,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "schedule_monitoring_failed",
            client_id=str(request.client_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to schedule job: {str(e)}",
        )


@router.post("/schedule/monitoring/all")
async def schedule_all_monitoring_jobs(
    request: ScheduleAllMonitoringRequest,
    auth: Auth,
):
    """
    Schedule monitoring for all active clients in the organization.

    Jobs are staggered by stagger_seconds to avoid overwhelming workers.
    """
    try:
        redis = await get_redis()
        job_ids = await schedule_all_client_monitoring(
            redis,
            auth.organization_id,
            request.stagger_seconds,
        )
        await redis.close()

        return {
            "status": "scheduled",
            "organization_id": str(auth.organization_id),
            "job_count": len(job_ids),
            "job_ids": job_ids,
            "stagger_seconds": request.stagger_seconds,
        }

    except Exception as e:
        logger.error(
            "schedule_all_monitoring_failed",
            organization_id=str(auth.organization_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to schedule jobs: {str(e)}",
        )


@router.delete("/{job_id}")
async def cancel_pending_job(
    job_id: str,
    auth: Auth,
):
    """
    Cancel a pending job.

    Only works for jobs that haven't started execution yet.
    """
    try:
        redis = await get_redis()
        success = await cancel_job(redis, job_id)
        await redis.close()

        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to cancel job {job_id}. It may have already started or completed.",
            )

        return {
            "job_id": job_id,
            "status": "cancelled",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("cancel_job_failed", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel job: {str(e)}",
        )


@router.get("/health/workers")
async def worker_health(
    auth: Auth,
):
    """
    Get health status of background workers.

    Returns information about connected workers and queue depth.
    """
    try:
        redis = await get_redis()

        # Get queue info
        jobs = await get_scheduled_jobs(redis)

        # Try to get worker info from Redis
        # ARQ stores worker heartbeats in Redis
        worker_keys = await redis.keys("arq:worker:*")

        await redis.close()

        return {
            "status": "healthy" if worker_keys else "no_workers",
            "worker_count": len(worker_keys),
            "queued_jobs": len(jobs),
        }

    except Exception as e:
        logger.error("worker_health_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "worker_count": 0,
            "queued_jobs": 0,
        }
