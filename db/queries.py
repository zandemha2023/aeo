"""Database query functions for AEO system."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from config import get_settings
from db.models import (
    Alert,
    Client,
    ClientIntelligence,
    MonitoringQuery,
    MonitoringResult,
    PerformanceSnapshot,
)


def get_async_engine():
    """Get async database engine."""
    settings = get_settings()
    return create_async_engine(settings.database_url, echo=False)


def get_session_maker():
    """Get async session maker."""
    engine = get_async_engine()
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# === CLIENT OPERATIONS ===


async def create_client(
    session: AsyncSession,
    name: str,
    domain: str,
    industry: str | None = None,
) -> Client:
    """Create a new client."""
    client = Client(name=name, domain=domain, industry=industry)
    session.add(client)
    await session.commit()
    await session.refresh(client)
    return client


async def get_client(session: AsyncSession, client_id: UUID) -> Client | None:
    """Get client by ID."""
    result = await session.execute(select(Client).where(Client.id == client_id))
    return result.scalar_one_or_none()


async def get_client_by_domain(session: AsyncSession, domain: str) -> Client | None:
    """Get client by domain."""
    result = await session.execute(select(Client).where(Client.domain == domain))
    return result.scalar_one_or_none()


async def list_active_clients(session: AsyncSession) -> list[Client]:
    """List all active clients."""
    result = await session.execute(
        select(Client).where(Client.status == "active").order_by(Client.name)
    )
    return list(result.scalars().all())


# === INTELLIGENCE OPERATIONS ===


async def store_intelligence(
    session: AsyncSession,
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
    client_id: UUID,
    intelligence_type: str,
) -> ClientIntelligence | None:
    """Get the latest intelligence of a specific type."""
    result = await session.execute(
        select(ClientIntelligence)
        .where(
            and_(
                ClientIntelligence.client_id == client_id,
                ClientIntelligence.intelligence_type == intelligence_type,
            )
        )
        .order_by(ClientIntelligence.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


# === MONITORING OPERATIONS ===


async def create_monitoring_query(
    session: AsyncSession,
    client_id: UUID,
    query: str,
    query_type: str,
    priority: int = 50,
) -> MonitoringQuery:
    """Create a new monitoring query."""
    mq = MonitoringQuery(
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
    client_id: UUID,
    active_only: bool = True,
) -> list[MonitoringQuery]:
    """Get monitoring queries for a client."""
    query = select(MonitoringQuery).where(MonitoringQuery.client_id == client_id)

    if active_only:
        query = query.where(MonitoringQuery.active == True)

    query = query.order_by(MonitoringQuery.priority.desc())

    result = await session.execute(query)
    return list(result.scalars().all())


async def store_monitoring_result(
    session: AsyncSession,
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
    client_id: UUID,
    hours: int = 24,
) -> list[MonitoringResult]:
    """Get recent monitoring results for a client."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    result = await session.execute(
        select(MonitoringResult)
        .where(
            and_(
                MonitoringResult.client_id == client_id,
                MonitoringResult.created_at >= cutoff,
            )
        )
        .order_by(MonitoringResult.created_at.desc())
    )
    return list(result.scalars().all())


# === ALERT OPERATIONS ===


async def create_alert(
    session: AsyncSession,
    client_id: UUID,
    severity: str,
    alert_type: str,
    title: str,
    details: dict,
) -> Alert:
    """Create a new alert."""
    alert = Alert(
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
    client_id: UUID,
) -> list[Alert]:
    """Get active (non-resolved) alerts for a client."""
    result = await session.execute(
        select(Alert)
        .where(
            and_(
                Alert.client_id == client_id,
                Alert.status != "resolved",
            )
        )
        .order_by(Alert.created_at.desc())
    )
    return list(result.scalars().all())


async def acknowledge_alert(session: AsyncSession, alert_id: UUID) -> Alert | None:
    """Acknowledge an alert."""
    result = await session.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()

    if alert:
        alert.status = "acknowledged"
        alert.acknowledged_at = datetime.utcnow()
        await session.commit()
        await session.refresh(alert)

    return alert


async def resolve_alert(session: AsyncSession, alert_id: UUID) -> Alert | None:
    """Resolve an alert."""
    result = await session.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()

    if alert:
        alert.status = "resolved"
        alert.resolved_at = datetime.utcnow()
        await session.commit()
        await session.refresh(alert)

    return alert


# === PERFORMANCE OPERATIONS ===


async def store_performance_snapshot(
    session: AsyncSession,
    client_id: UUID,
    metrics: dict,
    benchmarks: dict,
) -> PerformanceSnapshot:
    """Store a performance snapshot."""
    snapshot = PerformanceSnapshot(
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
    client_id: UUID,
    days: int = 30,
) -> list[PerformanceSnapshot]:
    """Get performance history for a client."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = await session.execute(
        select(PerformanceSnapshot)
        .where(
            and_(
                PerformanceSnapshot.client_id == client_id,
                PerformanceSnapshot.snapshot_date >= cutoff,
            )
        )
        .order_by(PerformanceSnapshot.snapshot_date.asc())
    )
    return list(result.scalars().all())
