"""
API middleware for rate limiting, logging, and request tracking.

Rate limiting uses Redis for distributed tracking across multiple instances.
"""

import time
from typing import Callable

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from config import get_settings

logger = structlog.get_logger()


class RedisRateLimiter:
    """
    Redis-backed sliding window rate limiter.

    Uses Redis sorted sets for accurate distributed rate limiting.
    """

    def __init__(self):
        self._redis = None
        self._window_seconds = 60

    async def _get_redis(self):
        """Lazy Redis connection."""
        if self._redis is None:
            from redis.asyncio import Redis
            settings = get_settings()
            self._redis = Redis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    async def check_rate_limit(self, key: str, limit: int) -> tuple[bool, int]:
        """
        Check if request is within rate limit using sliding window.

        Returns:
            Tuple of (allowed, remaining_requests)
        """
        try:
            redis = await self._get_redis()
            now = time.time()
            window_start = now - self._window_seconds

            pipe = redis.pipeline()

            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)

            # Count current requests in window
            pipe.zcard(key)

            # Add current request
            pipe.zadd(key, {str(now): now})

            # Set expiry on the key
            pipe.expire(key, self._window_seconds + 1)

            results = await pipe.execute()
            current_count = results[1]  # zcard result

            if current_count >= limit:
                # Remove the request we just added since we're rejecting
                await redis.zrem(key, str(now))
                return False, 0

            remaining = limit - current_count - 1
            return True, max(0, remaining)

        except Exception as e:
            # If Redis fails, allow the request but log the error
            logger.error("rate_limit_redis_error", error=str(e))
            return True, limit

    async def get_retry_after(self, key: str) -> int:
        """Get seconds until oldest request expires from window."""
        try:
            redis = await self._get_redis()
            oldest = await redis.zrange(key, 0, 0, withscores=True)

            if not oldest:
                return 0

            oldest_time = oldest[0][1]
            retry_after = int(self._window_seconds - (time.time() - oldest_time))
            return max(0, retry_after)

        except Exception:
            return 60  # Default retry

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()


# Global rate limiter instance
_rate_limiter = RedisRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware based on organization.

    Uses Redis for distributed rate limiting across multiple instances.
    Falls back to allowing requests if Redis is unavailable.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()

        if not settings.rate_limit_enabled:
            return await call_next(request)

        # Skip rate limiting for health checks and metrics
        if request.url.path in ["/", "/health", "/ready", "/metrics"]:
            return await call_next(request)

        # Get rate limit key and limit
        org_id = getattr(request.state, "organization_id", None)
        rate_limit = getattr(request.state, "rate_limit_rpm", settings.default_rate_limit_rpm)

        if org_id:
            key = f"ratelimit:org:{org_id}"
        else:
            # Fall back to IP-based limiting for unauthenticated requests
            client_ip = request.client.host if request.client else "unknown"
            key = f"ratelimit:ip:{client_ip}"
            rate_limit = settings.default_rate_limit_rpm

        # Check rate limit
        allowed, remaining = await _rate_limiter.check_rate_limit(key, rate_limit)

        if not allowed:
            retry_after = await _rate_limiter.get_retry_after(key)
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
