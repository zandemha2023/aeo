"""
API middleware for rate limiting, logging, and request tracking.
"""

import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Callable
from uuid import UUID

import structlog
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from config import get_settings

logger = structlog.get_logger()


class RateLimitStore:
    """
    In-memory rate limit tracking.

    For production, replace with Redis for distributed rate limiting.
    """

    def __init__(self):
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._cleanup_interval = 60  # seconds
        self._last_cleanup = time.time()

    def _cleanup(self) -> None:
        """Remove old request timestamps."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        cutoff = now - 60  # Keep last minute
        for key in list(self._requests.keys()):
            self._requests[key] = [
                ts for ts in self._requests[key] if ts > cutoff
            ]
            if not self._requests[key]:
                del self._requests[key]

        self._last_cleanup = now

    def check_rate_limit(self, key: str, limit: int) -> tuple[bool, int]:
        """
        Check if request is within rate limit.

        Returns:
            Tuple of (allowed, remaining_requests)
        """
        self._cleanup()

        now = time.time()
        minute_ago = now - 60

        # Get requests in the last minute
        recent = [ts for ts in self._requests[key] if ts > minute_ago]
        self._requests[key] = recent

        if len(recent) >= limit:
            return False, 0

        # Record this request
        self._requests[key].append(now)
        return True, limit - len(recent) - 1

    def get_retry_after(self, key: str) -> int:
        """Get seconds until rate limit resets."""
        if key not in self._requests or not self._requests[key]:
            return 0

        oldest = min(self._requests[key])
        return max(0, int(60 - (time.time() - oldest)))


# Global rate limit store
_rate_limit_store = RateLimitStore()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware based on organization.

    Uses the organization's rate_limit_rpm setting from the database.
    Falls back to default limit for unauthenticated requests.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()

        if not settings.rate_limit_enabled:
            return await call_next(request)

        # Skip rate limiting for health checks
        if request.url.path in ["/", "/health", "/ready"]:
            return await call_next(request)

        # Get rate limit key and limit
        # The auth middleware should have set these
        org_id = getattr(request.state, "organization_id", None)
        rate_limit = getattr(request.state, "rate_limit_rpm", settings.default_rate_limit_rpm)

        if org_id:
            key = f"org:{org_id}"
        else:
            # Fall back to IP-based limiting for unauthenticated requests
            client_ip = request.client.host if request.client else "unknown"
            key = f"ip:{client_ip}"
            rate_limit = settings.default_rate_limit_rpm

        # Check rate limit
        allowed, remaining = _rate_limit_store.check_rate_limit(key, rate_limit)

        if not allowed:
            retry_after = _rate_limit_store.get_retry_after(key)
            logger.warning(
                "rate_limit_exceeded",
                key=key,
                limit=rate_limit,
                retry_after=retry_after,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(rate_limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Process request and add rate limit headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(rate_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for structured request logging with timing.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID", str(time.time_ns()))

        # Add request ID to state for correlation
        request.state.request_id = request_id

        start_time = time.time()

        # Log request
        logger.info(
            "request_started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else None,
        )

        try:
            response = await call_next(request)

            # Log response
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                "request_completed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

            # Add request ID to response
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "request_failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_ms=round(duration_ms, 2),
            )
            raise
