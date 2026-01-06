"""
Webhook notification system for AEO Orchestrator.

Sends webhook notifications for:
- New alerts (critical, warning, opportunity)
- Monitoring results with significant changes
- System events (errors, threshold breaches)
"""

import asyncio
import hashlib
import hmac
import json
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

import httpx
import structlog
from pydantic import BaseModel, HttpUrl

logger = structlog.get_logger()


class WebhookEventType(str, Enum):
    """Types of webhook events."""

    ALERT_CREATED = "alert.created"
    ALERT_RESOLVED = "alert.resolved"
    MONITORING_COMPLETE = "monitoring.complete"
    CONTENT_PUBLISHED = "content.published"
    BUDGET_WARNING = "budget.warning"
    BUDGET_EXCEEDED = "budget.exceeded"
    SYSTEM_ERROR = "system.error"


class WebhookConfig(BaseModel):
    """Configuration for a webhook endpoint."""

    url: HttpUrl
    secret: Optional[str] = None  # For HMAC signature verification
    events: list[WebhookEventType] = []  # Empty = all events
    headers: dict[str, str] = {}  # Additional headers
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: float = 1.0


class WebhookPayload(BaseModel):
    """Standard webhook payload structure."""

    event_type: WebhookEventType
    event_id: str
    timestamp: str
    organization_id: str
    data: dict[str, Any]


class WebhookDeliveryResult(BaseModel):
    """Result of webhook delivery attempt."""

    success: bool
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    error: Optional[str] = None
    attempts: int = 1
    delivered_at: Optional[str] = None


def generate_signature(payload: str, secret: str) -> str:
    """
    Generate HMAC-SHA256 signature for payload.

    The signature can be verified by the receiving server to ensure
    the webhook came from a trusted source.
    """
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def send_webhook(
    config: WebhookConfig,
    payload: WebhookPayload,
) -> WebhookDeliveryResult:
    """
    Send a webhook notification with retry logic.

    Features:
    - HMAC signature for payload verification
    - Exponential backoff retry
    - Configurable timeout
    - Custom headers support
    """
    payload_json = payload.model_dump_json()

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "AEO-Orchestrator-Webhook/1.0",
        "X-AEO-Event": payload.event_type.value,
        "X-AEO-Event-ID": payload.event_id,
        "X-AEO-Timestamp": payload.timestamp,
        **config.headers,
    }

    # Add signature if secret is configured
    if config.secret:
        signature = generate_signature(payload_json, config.secret)
        headers["X-AEO-Signature"] = f"sha256={signature}"

    last_error: Optional[str] = None
    attempts = 0

    async with httpx.AsyncClient() as client:
        for attempt in range(config.max_retries):
            attempts = attempt + 1
            try:
                response = await client.post(
                    str(config.url),
                    content=payload_json,
                    headers=headers,
                    timeout=config.timeout_seconds,
                )

                if response.status_code < 300:
                    logger.info(
                        "webhook_delivered",
                        url=str(config.url),
                        event=payload.event_type.value,
                        status=response.status_code,
                        attempts=attempts,
                    )
                    return WebhookDeliveryResult(
                        success=True,
                        status_code=response.status_code,
                        response_body=response.text[:500] if response.text else None,
                        attempts=attempts,
                        delivered_at=datetime.utcnow().isoformat(),
                    )

                # Non-2xx response
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.warning(
                    "webhook_failed_response",
                    url=str(config.url),
                    status=response.status_code,
                    attempt=attempts,
                )

            except httpx.TimeoutException:
                last_error = "Request timeout"
                logger.warning(
                    "webhook_timeout",
                    url=str(config.url),
                    attempt=attempts,
                )

            except httpx.RequestError as e:
                last_error = str(e)
                logger.warning(
                    "webhook_request_error",
                    url=str(config.url),
                    error=str(e),
                    attempt=attempts,
                )

            # Wait before retry (exponential backoff)
            if attempt < config.max_retries - 1:
                delay = config.retry_delay_seconds * (2**attempt)
                await asyncio.sleep(delay)

    logger.error(
        "webhook_delivery_failed",
        url=str(config.url),
        event=payload.event_type.value,
        error=last_error,
        attempts=attempts,
    )

    return WebhookDeliveryResult(
        success=False,
        error=last_error,
        attempts=attempts,
    )


async def send_alert_webhook(
    config: WebhookConfig,
    organization_id: UUID,
    alert_id: UUID,
    client_id: UUID,
    severity: str,
    alert_type: str,
    title: str,
    details: dict[str, Any],
) -> WebhookDeliveryResult:
    """
    Send a webhook notification for a new alert.

    Convenience function for alert notifications.
    """
    # Check if this event type is subscribed
    if config.events and WebhookEventType.ALERT_CREATED not in config.events:
        return WebhookDeliveryResult(
            success=True,
            error="Event type not subscribed",
            attempts=0,
        )

    payload = WebhookPayload(
        event_type=WebhookEventType.ALERT_CREATED,
        event_id=str(alert_id),
        timestamp=datetime.utcnow().isoformat(),
        organization_id=str(organization_id),
        data={
            "alert_id": str(alert_id),
            "client_id": str(client_id),
            "severity": severity,
            "alert_type": alert_type,
            "title": title,
            "details": details,
        },
    )

    return await send_webhook(config, payload)


async def send_monitoring_webhook(
    config: WebhookConfig,
    organization_id: UUID,
    client_id: UUID,
    results_summary: dict[str, Any],
) -> WebhookDeliveryResult:
    """
    Send a webhook notification for completed monitoring.

    Includes summary of monitoring results.
    """
    if config.events and WebhookEventType.MONITORING_COMPLETE not in config.events:
        return WebhookDeliveryResult(
            success=True,
            error="Event type not subscribed",
            attempts=0,
        )

    from uuid import uuid4

    payload = WebhookPayload(
        event_type=WebhookEventType.MONITORING_COMPLETE,
        event_id=str(uuid4()),
        timestamp=datetime.utcnow().isoformat(),
        organization_id=str(organization_id),
        data={
            "client_id": str(client_id),
            **results_summary,
        },
    )

    return await send_webhook(config, payload)


async def send_budget_webhook(
    config: WebhookConfig,
    organization_id: UUID,
    current_spend: float,
    budget_limit: float,
    percent_used: float,
    exceeded: bool = False,
) -> WebhookDeliveryResult:
    """
    Send a webhook notification for budget warnings/exceeded.
    """
    event_type = (
        WebhookEventType.BUDGET_EXCEEDED
        if exceeded
        else WebhookEventType.BUDGET_WARNING
    )

    if config.events and event_type not in config.events:
        return WebhookDeliveryResult(
            success=True,
            error="Event type not subscribed",
            attempts=0,
        )

    from uuid import uuid4

    payload = WebhookPayload(
        event_type=event_type,
        event_id=str(uuid4()),
        timestamp=datetime.utcnow().isoformat(),
        organization_id=str(organization_id),
        data={
            "current_spend_usd": current_spend,
            "budget_limit_usd": budget_limit,
            "percent_used": percent_used,
            "exceeded": exceeded,
        },
    )

    return await send_webhook(config, payload)


# =============================================================================
# WEBHOOK CONFIGURATION STORAGE (Database Model Integration)
# =============================================================================


class WebhookConfigCreate(BaseModel):
    """Request to create/update a webhook configuration."""

    url: HttpUrl
    secret: Optional[str] = None
    events: list[str] = []  # Empty = all events
    headers: dict[str, str] = {}
    is_active: bool = True


class WebhookConfigResponse(BaseModel):
    """Response model for webhook configuration."""

    id: str
    organization_id: str
    url: str
    events: list[str]
    is_active: bool
    last_triggered_at: Optional[str]
    created_at: str
