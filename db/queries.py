"""Database query functions for AEO system with multi-tenancy."""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from config import get_settings
from db.models import (
    Alert,
    APIKey,
    Client,
    ClientIntelligence,
    LLMUsage,
    MonitoringQuery,
    MonitoringResult,
    Organization,
    PerformanceSnapshot,
    User,
)


def get_async_engine():
    """Get async database engine."""
    settings = get_settings()
    return create_async_engine(settings.database_url, echo=False)


def get_session_maker():
    """Get async session maker."""
    engine = get_async_engine()
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# =============================================================================
# ORGANIZATION OPERATIONS
# =============================================================================


async def create_organization(
    session: AsyncSession,
    name: str,
    slug: str,
    plan: str = "free",
) -> Organization:
    """Create a new organization."""
    org = Organization(name=name, slug=slug, plan=plan)
    session.add(org)
    await session.commit()
    await session.refresh(org)
    return org


async def get_organization(session: AsyncSession, org_id: UUID) -> Organization | None:
    """Get organization by ID."""
    result = await session.execute(select(Organization).where(Organization.id == org_id))
    return result.scalar_one_or_none()


async def get_organization_by_slug(session: AsyncSession, slug: str) -> Organization | None:
    """Get organization by slug."""
    result = await session.execute(select(Organization).where(Organization.slug == slug))
    return result.scalar_one_or_none()


# =============================================================================
# USER OPERATIONS
# =============================================================================


async def create_user(
    session: AsyncSession,
    organization_id: UUID,
    email: str,
    password_hash: str,
    name: str | None = None,
    role: str = "member",
) -> User:
    """Create a new user."""
    user = User(
        organization_id=organization_id,
        email=email,
        password_hash=password_hash,
        name=name,
        role=role,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    """Get user by email."""
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user(session: AsyncSession, user_id: UUID) -> User | None:
    """Get user by ID."""
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def update_user_login(session: AsyncSession, user_id: UUID) -> None:
    """Update user's last login time."""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.last_login_at = datetime.utcnow()
        await session.commit()


# =============================================================================
# API KEY OPERATIONS
# =============================================================================


async def create_api_key(
    session: AsyncSession,
    organization_id: UUID,
    name: str,
    key_prefix: str,
    key_hash: str,
    scopes: list[str] | None = None,
    expires_at: datetime | None = None,
) -> APIKey:
    """Create a new API key."""
    api_key = APIKey(
        organization_id=organization_id,
        name=name,
        key_prefix=key_prefix,
        key_hash=key_hash,
        scopes=scopes or ["read", "write"],
        expires_at=expires_at,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    return api_key


async def list_api_keys(
    session: AsyncSession,
    organization_id: UUID,
) -> list[APIKey]:
    """List all API keys for an organization."""
    result = await session.execute(
        select(APIKey)
        .where(APIKey.organization_id == organization_id)
        .order_by(APIKey.created_at.desc())
    )
    return list(result.scalars().all())


async def revoke_api_key(
    session: AsyncSession,
    organization_id: UUID,
    key_id: UUID,
) -> bool:
    """Revoke an API key."""
    result = await session.execute(
        select(APIKey).where(
            and_(
                APIKey.id == key_id,
                APIKey.organization_id == organization_id,
            )
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key:
        api_key.is_active = False
        await session.commit()
        return True
    return False


# =============================================================================
# LLM USAGE OPERATIONS (Cost Tracking)
# =============================================================================


async def log_llm_usage(
    session: AsyncSession,
    organization_id: UUID,
    agent: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: Decimal,
    workflow: str | None = None,
    client_id: UUID | None = None,
    latency_ms: int | None = None,
    success: bool = True,
    error_message: str | None = None,
) -> LLMUsage:
    """Log an LLM API call for cost tracking."""
    usage = LLMUsage(
        organization_id=organization_id,
        agent=agent,
        workflow=workflow,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        success=success,
        error_message=error_message,
        client_id=client_id,
    )
    session.add(usage)
    await session.commit()
    await session.refresh(usage)
    return usage


async def get_usage_summary(
    session: AsyncSession,
    organization_id: UUID,
    days: int = 30,
) -> dict:
    """Get usage summary for an organization."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Total cost
    cost_result = await session.execute(
        select(func.sum(LLMUsage.cost_usd))
        .where(
            and_(
                LLMUsage.organization_id == organization_id,
                LLMUsage.created_at >= cutoff,
            )
        )
    )
    total_cost = cost_result.scalar() or Decimal("0")

    # Total tokens
    tokens_result = await session.execute(
        select(
            func.sum(LLMUsage.input_tokens),
            func.sum(LLMUsage.output_tokens),
        )
        .where(
            and_(
                LLMUsage.organization_id == organization_id,
                LLMUsage.created_at >= cutoff,
            )
        )
    )
    tokens = tokens_result.one()
    total_input_tokens = tokens[0] or 0
    total_output_tokens = tokens[1] or 0

    # Call count
    count_result = await session.execute(
        select(func.count(LLMUsage.id))
        .where(
            and_(
                LLMUsage.organization_id == organization_id,
                LLMUsage.created_at >= cutoff,
            )
        )
    )
    total_calls = count_result.scalar() or 0

    # By agent
    agent_result = await session.execute(
        select(LLMUsage.agent, func.sum(LLMUsage.cost_usd))
        .where(
            and_(
                LLMUsage.organization_id == organization_id,
                LLMUsage.created_at >= cutoff,
            )
        )
        .group_by(LLMUsage.agent)
    )
    cost_by_agent = {row[0]: float(row[1]) for row in agent_result.all()}

    return {
        "period_days": days,
        "total_cost_usd": float(total_cost),
        "total_calls": total_calls,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "cost_by_agent": cost_by_agent,
    }


# =============================================================================
# CLIENT OPERATIONS (with tenant isolation)
# =============================================================================


async def create_client(
    session: AsyncSession,
    organization_id: UUID,
    name: str,
    domain: str,
    industry: str | None = None,
) -> Client:
    """Create a new client within an organization."""
    client = Client(
        organization_id=organization_id,
        name=name,
        domain=domain,
        industry=industry,
    )
    session.add(client)
    await session.commit()
    await session.refresh(client)
    return client


async def get_client(
    session: AsyncSession,
    organization_id: UUID,
    client_id: UUID,
) -> Client | None:
    """Get client by ID within an organization."""
    result = await session.execute(
        select(Client).where(
            and_(
                Client.id == client_id,
                Client.organization_id == organization_id,
            )
        )
    )
    return result.scalar_one_or_none()


async def get_client_by_domain(
    session: AsyncSession,
    organization_id: UUID,
    domain: str,
) -> Client | None:
    """Get client by domain within an organization."""
    result = await session.execute(
        select(Client).where(
            and_(
                Client.domain == domain,
                Client.organization_id == organization_id,
            )
        )
    )
    return result.scalar_one_or_none()


async def list_active_clients(
    session: AsyncSession,
    organization_id: UUID,
) -> list[Client]:
    """List all active clients for an organization."""
    result = await session.execute(
        select(Client)
        .where(
            and_(
                Client.organization_id == organization_id,
                Client.status == "active",
            )
        )
        .order_by(Client.name)
    )
    return list(result.scalars().all())


# =============================================================================
# INTELLIGENCE OPERATIONS (with tenant isolation)
# =============================================================================


async def store_intelligence(
    session: AsyncSession,
    organization_id: UUID,
    client_id: UUID,
    intelligence_type: str,
    data: dict,
) -> ClientIntelligence:
    """Store intelligence data, incrementing version if exists."""
    # Check for existing intelligence of this type
    result = await session.execute(
        select(ClientIntelligence)
        .where(
            and_(
                ClientIntelligence.organization_id == organization_id,
                ClientIntelligence.client_id == client_id,
                ClientIntelligence.intelligence_type == intelligence_type,
            )
        )
        .order_by(ClientIntelligence.version.desc())
        .limit(1)
    )
    existing = result.scalar_one_or_none()

    new_version = (existing.version + 1) if existing else 1

    intelligence = ClientIntelligence(
        organization_id=organization_id,
        client_id=client_id,
        intelligence_type=intelligence_type,
        data=data,
        version=new_version,
    )
    session.add(intelligence)
    await session.commit()
    await session.refresh(intelligence)
    return intelligence


async def get_latest_intelligence(
    session: AsyncSession,
    organization_id: UUID,
    client_id: UUID,
    intelligence_type: str,
) -> ClientIntelligence | None:
    """Get the latest intelligence of a specific type."""
    result = await session.execute(
        select(ClientIntelligence)
        .where(
            and_(
                ClientIntelligence.organization_id == organization_id,
                ClientIntelligence.client_id == client_id,
                ClientIntelligence.intelligence_type == intelligence_type,
            )
        )
        .order_by(ClientIntelligence.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


# =============================================================================
# MONITORING OPERATIONS (with tenant isolation)
# =============================================================================


async def create_monitoring_query(
    session: AsyncSession,
    organization_id: UUID,
    client_id: UUID,
    query: str,
    query_type: str,
    priority: int = 50,
) -> MonitoringQuery:
    """Create a new monitoring query."""
    mq = MonitoringQuery(
        organization_id=organization_id,
        client_id=client_id,
        query=query,
        query_type=query_type,
        priority=priority,
    )
    session.add(mq)
    await session.commit()
    await session.refresh(mq)
    return mq


async def get_monitoring_queries(
    session: AsyncSession,
    organization_id: UUID,
    client_id: UUID,
    active_only: bool = True,
) -> list[MonitoringQuery]:
    """Get monitoring queries for a client."""
    query = select(MonitoringQuery).where(
        and_(
            MonitoringQuery.organization_id == organization_id,
            MonitoringQuery.client_id == client_id,
        )
    )

    if active_only:
        query = query.where(MonitoringQuery.active == True)

    query = query.order_by(MonitoringQuery.priority.desc())

    result = await session.execute(query)
    return list(result.scalars().all())


async def store_monitoring_result(
    session: AsyncSession,
    organization_id: UUID,
    client_id: UUID,
    query_id: UUID,
    engine: str,
    response_text: str,
    brand_mentioned: bool,
    mention_position: int | None = None,
    recommended: bool = False,
    sentiment: str | None = None,
    accuracy: str | None = None,
    sources_cited: list[str] | None = None,
    competitors_mentioned: list[str] | None = None,
    mention_quality_score: float | None = None,
) -> MonitoringResult:
    """Store a monitoring result."""
    result = MonitoringResult(
        organization_id=organization_id,
        client_id=client_id,
        query_id=query_id,
        engine=engine,
        response_text=response_text,
        brand_mentioned=brand_mentioned,
        mention_position=mention_position,
        recommended=recommended,
        sentiment=sentiment,
        accuracy=accuracy,
        sources_cited=sources_cited or [],
        competitors_mentioned=competitors_mentioned or [],
        mention_quality_score=mention_quality_score,
    )
    session.add(result)
    await session.commit()
    await session.refresh(result)
    return result


async def get_recent_monitoring_results(
    session: AsyncSession,
    organization_id: UUID,
    client_id: UUID,
    hours: int = 24,
) -> list[MonitoringResult]:
    """Get recent monitoring results for a client."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    result = await session.execute(
        select(MonitoringResult)
        .where(
            and_(
                MonitoringResult.organization_id == organization_id,
                MonitoringResult.client_id == client_id,
                MonitoringResult.created_at >= cutoff,
            )
        )
        .order_by(MonitoringResult.created_at.desc())
    )
    return list(result.scalars().all())


# =============================================================================
# ALERT OPERATIONS (with tenant isolation)
# =============================================================================


async def create_alert(
    session: AsyncSession,
    organization_id: UUID,
    client_id: UUID,
    severity: str,
    alert_type: str,
    title: str,
    details: dict,
) -> Alert:
    """Create a new alert."""
    alert = Alert(
        organization_id=organization_id,
        client_id=client_id,
        severity=severity,
        alert_type=alert_type,
        title=title,
        details=details,
    )
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return alert


async def get_active_alerts(
    session: AsyncSession,
    organization_id: UUID,
    client_id: UUID,
) -> list[Alert]:
    """Get active (non-resolved) alerts for a client."""
    result = await session.execute(
        select(Alert)
        .where(
            and_(
                Alert.organization_id == organization_id,
                Alert.client_id == client_id,
                Alert.status != "resolved",
            )
        )
        .order_by(Alert.created_at.desc())
    )
    return list(result.scalars().all())


async def acknowledge_alert(
    session: AsyncSession,
    organization_id: UUID,
    alert_id: UUID,
) -> Alert | None:
    """Acknowledge an alert."""
    result = await session.execute(
        select(Alert).where(
            and_(
                Alert.id == alert_id,
                Alert.organization_id == organization_id,
            )
        )
    )
    alert = result.scalar_one_or_none()

    if alert:
        alert.status = "acknowledged"
        alert.acknowledged_at = datetime.utcnow()
        await session.commit()
        await session.refresh(alert)

    return alert


async def resolve_alert(
    session: AsyncSession,
    organization_id: UUID,
    alert_id: UUID,
) -> Alert | None:
    """Resolve an alert."""
    result = await session.execute(
        select(Alert).where(
            and_(
                Alert.id == alert_id,
                Alert.organization_id == organization_id,
            )
        )
    )
    alert = result.scalar_one_or_none()

    if alert:
        alert.status = "resolved"
        alert.resolved_at = datetime.utcnow()
        await session.commit()
        await session.refresh(alert)

    return alert


# =============================================================================
# PERFORMANCE OPERATIONS (with tenant isolation)
# =============================================================================


async def store_performance_snapshot(
    session: AsyncSession,
    organization_id: UUID,
    client_id: UUID,
    metrics: dict,
    benchmarks: dict,
) -> PerformanceSnapshot:
    """Store a performance snapshot."""
    snapshot = PerformanceSnapshot(
        organization_id=organization_id,
        client_id=client_id,
        snapshot_date=datetime.utcnow(),
        metrics=metrics,
        benchmarks=benchmarks,
    )
    session.add(snapshot)
    await session.commit()
    await session.refresh(snapshot)
    return snapshot


async def get_performance_history(
    session: AsyncSession,
    organization_id: UUID,
    client_id: UUID,
    days: int = 30,
) -> list[PerformanceSnapshot]:
    """Get performance history for a client."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = await session.execute(
        select(PerformanceSnapshot)
        .where(
            and_(
                PerformanceSnapshot.organization_id == organization_id,
                PerformanceSnapshot.client_id == client_id,
                PerformanceSnapshot.snapshot_date >= cutoff,
            )
        )
        .order_by(PerformanceSnapshot.snapshot_date.asc())
    )
    return list(result.scalars().all())


# Alias for backward compatibility
async def record_llm_usage(
    session: AsyncSession,
    organization_id: UUID,
    agent_name: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: Decimal,
    metadata: dict | None = None,
) -> LLMUsage:
    """Record LLM usage (alias for log_llm_usage with simplified signature)."""
    return await log_llm_usage(
        session=session,
        organization_id=organization_id,
        agent=agent_name,
        provider="anthropic",
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        workflow=metadata.get("workflow") if metadata else None,
    )
