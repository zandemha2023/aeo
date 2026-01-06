"""
Prometheus metrics for monitoring and alerting.

Exposes application metrics for:
- HTTP request latency and counts
- LLM API call tracking
- Workflow execution metrics
- Background job metrics
"""

import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CollectorRegistry,
    REGISTRY,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match

# HTTP Metrics
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint", "status_code"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently being processed",
    ["method", "endpoint"],
)

# LLM Metrics
LLM_CALLS_TOTAL = Counter(
    "llm_calls_total",
    "Total LLM API calls",
    ["model", "agent", "organization_id"],
)

LLM_TOKENS_TOTAL = Counter(
    "llm_tokens_total",
    "Total LLM tokens used",
    ["model", "token_type", "organization_id"],  # token_type: input/output
)

LLM_CALL_DURATION = Histogram(
    "llm_call_duration_seconds",
    "LLM API call latency in seconds",
    ["model", "agent"],
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
)

LLM_COST_TOTAL = Counter(
    "llm_cost_dollars_total",
    "Total LLM API cost in dollars",
    ["model", "organization_id"],
)

# Workflow Metrics
WORKFLOW_EXECUTIONS_TOTAL = Counter(
    "workflow_executions_total",
    "Total workflow executions",
    ["workflow", "status", "organization_id"],  # status: success/failure
)

WORKFLOW_DURATION = Histogram(
    "workflow_duration_seconds",
    "Workflow execution time in seconds",
    ["workflow"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0],
)

# Background Job Metrics
JOB_EXECUTIONS_TOTAL = Counter(
    "job_executions_total",
    "Total background job executions",
    ["job_type", "status"],  # status: success/failure/timeout
)

JOB_DURATION = Histogram(
    "job_duration_seconds",
    "Background job execution time in seconds",
    ["job_type"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0],
)

JOBS_IN_QUEUE = Gauge(
    "jobs_in_queue",
    "Number of jobs currently in the queue",
    ["queue"],
)

# Circuit Breaker Metrics
CIRCUIT_BREAKER_STATE = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["name"],
)

CIRCUIT_BREAKER_FAILURES = Counter(
    "circuit_breaker_failures_total",
    "Total circuit breaker failures",
    ["name"],
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP metrics."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        method = request.method
        endpoint = self._get_endpoint(request)

        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            status_code = str(response.status_code)
        except Exception:
            status_code = "500"
            raise
        finally:
            duration = time.perf_counter() - start_time
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()
            HTTP_REQUEST_DURATION.labels(
                method=method, endpoint=endpoint, status_code=status_code
            ).observe(duration)
            HTTP_REQUESTS_TOTAL.labels(
                method=method, endpoint=endpoint, status_code=status_code
            ).inc()

        return response

    def _get_endpoint(self, request: Request) -> str:
        """Get the route pattern for the request."""
        # Try to match the request path to a route
        for route in request.app.routes:
            match, _ = route.matches(request.scope)
            if match == Match.FULL:
                return route.path
        return request.url.path


def get_metrics_app() -> FastAPI:
    """Create a separate FastAPI app for metrics endpoint."""
    metrics_app = FastAPI(title="Metrics", docs_url=None, redoc_url=None)

    @metrics_app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint."""
        return Response(
            content=generate_latest(REGISTRY),
            media_type=CONTENT_TYPE_LATEST,
        )

    return metrics_app


def record_llm_call(
    model: str,
    agent: str,
    organization_id: str,
    input_tokens: int,
    output_tokens: int,
    duration_seconds: float,
    cost_dollars: float,
) -> None:
    """Record metrics for an LLM API call."""
    LLM_CALLS_TOTAL.labels(
        model=model, agent=agent, organization_id=organization_id
    ).inc()

    LLM_TOKENS_TOTAL.labels(
        model=model, token_type="input", organization_id=organization_id
    ).inc(input_tokens)

    LLM_TOKENS_TOTAL.labels(
        model=model, token_type="output", organization_id=organization_id
    ).inc(output_tokens)

    LLM_CALL_DURATION.labels(model=model, agent=agent).observe(duration_seconds)

    LLM_COST_TOTAL.labels(model=model, organization_id=organization_id).inc(
        cost_dollars
    )


def record_workflow_duration(
    workflow: str,
    organization_id: str,
    duration_seconds: float,
    success: bool,
) -> None:
    """Record metrics for a workflow execution."""
    status = "success" if success else "failure"
    WORKFLOW_EXECUTIONS_TOTAL.labels(
        workflow=workflow, status=status, organization_id=organization_id
    ).inc()
    WORKFLOW_DURATION.labels(workflow=workflow).observe(duration_seconds)


def record_job_execution(
    job_type: str,
    duration_seconds: float,
    status: str,  # success, failure, timeout
) -> None:
    """Record metrics for a background job execution."""
    JOB_EXECUTIONS_TOTAL.labels(job_type=job_type, status=status).inc()
    JOB_DURATION.labels(job_type=job_type).observe(duration_seconds)


def update_circuit_breaker_state(name: str, state: str) -> None:
    """Update circuit breaker state metric."""
    state_value = {"closed": 0, "open": 1, "half_open": 2}.get(state.lower(), 0)
    CIRCUIT_BREAKER_STATE.labels(name=name).set(state_value)


def record_circuit_breaker_failure(name: str) -> None:
    """Record a circuit breaker failure."""
    CIRCUIT_BREAKER_FAILURES.labels(name=name).inc()


def update_queue_depth(queue: str, depth: int) -> None:
    """Update the queue depth gauge."""
    JOBS_IN_QUEUE.labels(queue=queue).set(depth)
