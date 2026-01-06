"""
Webhook management API endpoints.

Provides REST API for:
- Creating and managing webhook endpoints
- Viewing webhook delivery history
- Testing webhook connections
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import Auth, hash_password
from api.deps import get_session
from db.models import WebhookDelivery, WebhookEndpoint
from notifications.webhooks import (
    WebhookConfig,
    WebhookEventType,
    WebhookPayload,
    send_webhook,
)

logger = structlog.get_logger()
router = APIRouter()


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class WebhookCreate(BaseModel):
    """Request to create a webhook endpoint."""

    name: str
    url: HttpUrl
    secret: Optional[str] = None
    events: list[str] = []  # Empty = all events
    headers: dict[str, str] = {}
    description: Optional[str] = None


class WebhookUpdate(BaseModel):
    """Request to update a webhook endpoint."""

    name: Optional[str] = None
    url: Optional[HttpUrl] = None
    secret: Optional[str] = None
    events: Optional[list[str]] = None
    headers: Optional[dict[str, str]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class WebhookResponse(BaseModel):
    """Response model for webhook endpoint."""

    id: str
    name: Optional[str]
    url: str
    events: list[str]
    is_active: bool
    last_triggered_at: Optional[str]
    last_success_at: Optional[str]
    last_failure_at: Optional[str]
    consecutive_failures: int
    created_at: str


class WebhookDeliveryResponse(BaseModel):
    """Response model for webhook delivery record."""

    id: str
    webhook_id: str
    event_type: str
    event_id: str
    success: bool
    status_code: Optional[int]
    error_message: Optional[str]
    attempts: int
    created_at: str


class WebhookTestRequest(BaseModel):
    """Request to test a webhook endpoint."""

    event_type: str = "test.ping"


class WebhookTestResponse(BaseModel):
    """Response from webhook test."""

    success: bool
    status_code: Optional[int]
    response_preview: Optional[str]
    error: Optional[str]
    latency_ms: Optional[int]


# =============================================================================
# WEBHOOK ENDPOINTS
# =============================================================================


@router.post("/", response_model=WebhookResponse)
async def create_webhook(
    request: WebhookCreate,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """
    Create a new webhook endpoint.

    The webhook will receive notifications for the specified event types.
    If no events are specified, all events will be sent.
    """
    # Validate event types
    valid_events = {e.value for e in WebhookEventType}
    for event in request.events:
        if event not in valid_events:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid event type: {event}. Valid types: {list(valid_events)}",
            )

    webhook = WebhookEndpoint(
        organization_id=auth.organization_id,
        name=request.name,
        url=str(request.url),
        secret_hash=hash_password(request.secret) if request.secret else None,
        events=request.events,
        headers=request.headers,
        description=request.description,
    )

    session.add(webhook)
    await session.commit()
    await session.refresh(webhook)

    logger.info(
        "webhook_created",
        webhook_id=str(webhook.id),
        organization_id=str(auth.organization_id),
    )

    return WebhookResponse(
        id=str(webhook.id),
        name=webhook.name,
        url=webhook.url,
        events=webhook.events or [],
        is_active=webhook.is_active,
        last_triggered_at=None,
        last_success_at=None,
        last_failure_at=None,
        consecutive_failures=webhook.consecutive_failures,
        created_at=webhook.created_at.isoformat(),
    )


@router.get("/", response_model=list[WebhookResponse])
async def list_webhooks(
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """List all webhook endpoints for the organization."""
    result = await session.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.organization_id == auth.organization_id
        ).order_by(WebhookEndpoint.created_at.desc())
    )
    webhooks = result.scalars().all()

    return [
        WebhookResponse(
            id=str(w.id),
            name=w.name,
            url=w.url,
            events=w.events or [],
            is_active=w.is_active,
            last_triggered_at=w.last_triggered_at.isoformat() if w.last_triggered_at else None,
            last_success_at=w.last_success_at.isoformat() if w.last_success_at else None,
            last_failure_at=w.last_failure_at.isoformat() if w.last_failure_at else None,
            consecutive_failures=w.consecutive_failures,
            created_at=w.created_at.isoformat(),
        )
        for w in webhooks
    ]


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Get a specific webhook endpoint."""
    result = await session.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == webhook_id,
            WebhookEndpoint.organization_id == auth.organization_id,
        )
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return WebhookResponse(
        id=str(webhook.id),
        name=webhook.name,
        url=webhook.url,
        events=webhook.events or [],
        is_active=webhook.is_active,
        last_triggered_at=webhook.last_triggered_at.isoformat() if webhook.last_triggered_at else None,
        last_success_at=webhook.last_success_at.isoformat() if webhook.last_success_at else None,
        last_failure_at=webhook.last_failure_at.isoformat() if webhook.last_failure_at else None,
        consecutive_failures=webhook.consecutive_failures,
        created_at=webhook.created_at.isoformat(),
    )


@router.patch("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: UUID,
    request: WebhookUpdate,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Update a webhook endpoint."""
    result = await session.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == webhook_id,
            WebhookEndpoint.organization_id == auth.organization_id,
        )
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    if request.name is not None:
        webhook.name = request.name
    if request.url is not None:
        webhook.url = str(request.url)
    if request.secret is not None:
        webhook.secret_hash = hash_password(request.secret)
    if request.events is not None:
        webhook.events = request.events
    if request.headers is not None:
        webhook.headers = request.headers
    if request.description is not None:
        webhook.description = request.description
    if request.is_active is not None:
        webhook.is_active = request.is_active

    await session.commit()
    await session.refresh(webhook)

    return WebhookResponse(
        id=str(webhook.id),
        name=webhook.name,
        url=webhook.url,
        events=webhook.events or [],
        is_active=webhook.is_active,
        last_triggered_at=webhook.last_triggered_at.isoformat() if webhook.last_triggered_at else None,
        last_success_at=webhook.last_success_at.isoformat() if webhook.last_success_at else None,
        last_failure_at=webhook.last_failure_at.isoformat() if webhook.last_failure_at else None,
        consecutive_failures=webhook.consecutive_failures,
        created_at=webhook.created_at.isoformat(),
    )


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: UUID,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """Delete a webhook endpoint."""
    result = await session.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == webhook_id,
            WebhookEndpoint.organization_id == auth.organization_id,
        )
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    await session.delete(webhook)
    await session.commit()

    return {"status": "deleted", "webhook_id": str(webhook_id)}


@router.post("/{webhook_id}/test", response_model=WebhookTestResponse)
async def test_webhook(
    webhook_id: UUID,
    request: WebhookTestRequest,
    auth: Auth,
    session: AsyncSession = Depends(get_session),
):
    """
    Test a webhook endpoint.

    Sends a test event to verify the endpoint is reachable
    and configured correctly.
    """
    import time

    result = await session.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == webhook_id,
            WebhookEndpoint.organization_id == auth.organization_id,
        )
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    # Create test payload
    from uuid import uuid4

    config = WebhookConfig(
        url=webhook.url,
        secret=None,  # Don't use secret for test (we don't store plaintext)
        events=[],
        headers=webhook.headers or {},
        timeout_seconds=10,
        max_retries=1,
    )

    payload = WebhookPayload(
        event_type=WebhookEventType.SYSTEM_ERROR,  # Use system error as test type
        event_id=str(uuid4()),
        timestamp=datetime.utcnow().isoformat(),
        organization_id=str(auth.organization_id),
        data={
            "type": "test",
            "message": "This is a test webhook from AEO Orchestrator",
        },
    )

    start = time.time()
    delivery_result = await send_webhook(config, payload)
    latency_ms = int((time.time() - start) * 1000)

    return WebhookTestResponse(
        success=delivery_result.success,
        status_code=delivery_result.status_code,
        response_preview=delivery_result.response_body[:200] if delivery_result.response_body else None,
        error=delivery_result.error,
        latency_ms=latency_ms,
    )


@router.get("/{webhook_id}/deliveries", response_model=list[WebhookDeliveryResponse])
async def list_webhook_deliveries(
    webhook_id: UUID,
    auth: Auth,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """
    List delivery history for a webhook endpoint.

    Shows recent delivery attempts with their results.
    """
    # Verify webhook belongs to org
    result = await session.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == webhook_id,
            WebhookEndpoint.organization_id == auth.organization_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Webhook not found")

    result = await session.execute(
        select(WebhookDelivery).where(
            WebhookDelivery.webhook_id == webhook_id
        ).order_by(WebhookDelivery.created_at.desc()).limit(limit)
    )
    deliveries = result.scalars().all()

    return [
        WebhookDeliveryResponse(
            id=str(d.id),
            webhook_id=str(d.webhook_id),
            event_type=d.event_type,
            event_id=d.event_id,
            success=d.success,
            status_code=d.status_code,
            error_message=d.error_message,
            attempts=d.attempts,
            created_at=d.created_at.isoformat(),
        )
        for d in deliveries
    ]


@router.get("/events/types")
async def list_event_types():
    """List all available webhook event types."""
    return {
        "event_types": [
            {
                "type": e.value,
                "description": _get_event_description(e),
            }
            for e in WebhookEventType
        ]
    }


def _get_event_description(event: WebhookEventType) -> str:
    """Get description for an event type."""
    descriptions = {
        WebhookEventType.ALERT_CREATED: "A new alert has been created",
        WebhookEventType.ALERT_RESOLVED: "An alert has been resolved",
        WebhookEventType.MONITORING_COMPLETE: "Monitoring cycle completed",
        WebhookEventType.CONTENT_PUBLISHED: "Content has been published",
        WebhookEventType.BUDGET_WARNING: "LLM budget usage warning (80%)",
        WebhookEventType.BUDGET_EXCEEDED: "LLM budget has been exceeded",
        WebhookEventType.SYSTEM_ERROR: "System error occurred",
    }
    return descriptions.get(event, "No description available")
