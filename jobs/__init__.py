"""
Background job system for AEO using ARQ.

Provides:
- Async background task execution
- Scheduled/periodic jobs for monitoring
- Job status tracking
- Retry handling
"""

from jobs.worker import WorkerSettings, create_pool
from jobs.tasks import (
    run_monitoring_job,
    run_strategy_job,
    run_content_job,
    run_onboarding_job,
)
from jobs.scheduler import (
    schedule_monitoring,
    schedule_all_client_monitoring,
    get_scheduled_jobs,
)

__all__ = [
    "WorkerSettings",
    "create_pool",
    "run_monitoring_job",
    "run_strategy_job",
    "run_content_job",
    "run_onboarding_job",
    "schedule_monitoring",
    "schedule_all_client_monitoring",
    "get_scheduled_jobs",
]
