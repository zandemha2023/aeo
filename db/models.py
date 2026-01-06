"""SQLAlchemy models for AEO database."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


# =============================================================================
# MULTI-TENANCY MODELS
# =============================================================================


class Organization(Base):
    """
    Multi-tenant organization (the tenant).

    All user data is scoped to an organization.
    """

    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False, unique=True)

    # Billing and limits
    plan = Column(String(50), default="free")  # free, starter, pro, enterprise
    monthly_llm_budget_usd = Column(Numeric(10, 2), default=100.00)
    rate_limit_rpm = Column(Integer, default=60)  # requests per minute

    # Status
    status = Column(String(20), default="active")  # active, suspended, cancelled

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users = relationship("User", back_populates="organization")
    api_keys = relationship("APIKey", back_populates="organization")
    clients = relationship("Client", back_populates="organization")
    llm_usage = relationship("LLMUsage", back_populates="organization")


class User(Base):
    """
    User account within an organization.
    """

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)

    # Profile
    name = Column(String(255))
    role = Column(String(50), default="member")  # owner, admin, member, viewer

    # Status
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)

    # Tracking
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="users")

    __table_args__ = (
        Index("ix_users_org_email", "organization_id", "email"),
    )


class APIKey(Base):
    """
    API key for programmatic access.

    Keys are hashed - never store plaintext.
    """

    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Key identification (prefix is the first 8 chars, shown to user)
    key_prefix = Column(String(12), nullable=False)
    key_hash = Column(String(255), nullable=False, unique=True)

    # Metadata
    name = Column(String(100), nullable=False)  # User-provided name
    scopes = Column(JSONB, default=list)  # ["read", "write", "admin"]

    # Status and usage
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime)
    expires_at = Column(DateTime)  # Optional expiration

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="api_keys")


# =============================================================================
# COST TRACKING
# =============================================================================


class LLMUsage(Base):
    """
    Track every LLM API call for cost attribution.

    This is the source of truth for billing and cost visibility.
    """

    __tablename__ = "llm_usage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # What made the call
    agent = Column(String(100), nullable=False)  # cartographer, auditor, etc.
    workflow = Column(String(100))  # onboarding, monitoring, strategy, etc.

    # LLM details
    provider = Column(String(50), nullable=False)  # anthropic, openai, google, perplexity
    model = Column(String(100), nullable=False)

    # Token usage
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)

    # Cost (in USD, calculated at time of call)
    cost_usd = Column(Numeric(10, 6), nullable=False, default=0)

    # Request metadata
    latency_ms = Column(Integer)
    success = Column(Boolean, default=True)
    error_message = Column(Text)

    # Optional: link to specific client if applicable
    client_id = Column(UUID(as_uuid=True), ForeignKey("aeo_clients.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="llm_usage")

    __table_args__ = (
        Index("ix_llm_usage_org_created", "organization_id", "created_at"),
        Index("ix_llm_usage_org_agent", "organization_id", "agent"),
    )


# =============================================================================
# AEO BUSINESS MODELS (now with tenant_id)
# =============================================================================


class Client(Base):
    """AEO client - scoped to an organization."""

    __tablename__ = "aeo_clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(String(255), nullable=False)
    domain = Column(String(255), nullable=False)
    industry = Column(String(100), nullable=True)
    status = Column(String(50), default="active")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="clients")
    intelligence = relationship("ClientIntelligence", back_populates="client", cascade="all, delete-orphan")
    monitoring_queries = relationship("MonitoringQuery", back_populates="client", cascade="all, delete-orphan")
    monitoring_results = relationship("MonitoringResult", back_populates="client", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="client", cascade="all, delete-orphan")
    performance_snapshots = relationship("PerformanceSnapshot", back_populates="client", cascade="all, delete-orphan")

    __table_args__ = (
        # Domain is unique within an organization, not globally
        UniqueConstraint("organization_id", "domain", name="uq_client_org_domain"),
        Index("ix_clients_org_status", "organization_id", "status"),
    )


class ClientIntelligence(Base):
    """Client intelligence gathered by agents."""

    __tablename__ = "client_intelligence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(UUID(as_uuid=True), ForeignKey("aeo_clients.id", ondelete="CASCADE"), nullable=False)

    intelligence_type = Column(String(50), nullable=False)  # cartographer, scout, librarian, auditor
    data = Column(JSONB, nullable=False)
    version = Column(Integer, default=1)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    client = relationship("Client", back_populates="intelligence")

    __table_args__ = (
        Index("ix_intel_org_client_type", "organization_id", "client_id", "intelligence_type"),
    )


class MonitoringQuery(Base):
    """Queries to monitor for brand mentions."""

    __tablename__ = "monitoring_queries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(UUID(as_uuid=True), ForeignKey("aeo_clients.id", ondelete="CASCADE"), nullable=False)

    query = Column(Text, nullable=False)
    query_type = Column(String(50))  # brand, product, comparison, category, how_to
    priority = Column(Integer, default=50)
    active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    client = relationship("Client", back_populates="monitoring_queries")
    results = relationship("MonitoringResult", back_populates="query", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_queries_org_client_active", "organization_id", "client_id", "active"),
    )


class MonitoringResult(Base):
    """Results from monitoring queries."""

    __tablename__ = "monitoring_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(UUID(as_uuid=True), ForeignKey("aeo_clients.id", ondelete="CASCADE"), nullable=False)
    query_id = Column(UUID(as_uuid=True), ForeignKey("monitoring_queries.id", ondelete="CASCADE"), nullable=False)

    engine = Column(String(50), nullable=False)
    response_text = Column(Text)

    # Parsed metrics
    brand_mentioned = Column(Boolean, default=False)
    mention_position = Column(Integer)
    mention_type = Column(String(50))
    recommended = Column(Boolean, default=False)
    sentiment = Column(String(20))  # positive, neutral, negative
    accuracy = Column(String(20))  # accurate, inaccurate, partially_accurate
    sources_cited = Column(JSONB)
    competitors_mentioned = Column(JSONB)

    # Quality score
    mention_quality_score = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    client = relationship("Client", back_populates="monitoring_results")
    query = relationship("MonitoringQuery", back_populates="results")

    __table_args__ = (
        Index("ix_results_org_client_created", "organization_id", "client_id", "created_at"),
    )


class Alert(Base):
    """Alerts for significant AEO events."""

    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(UUID(as_uuid=True), ForeignKey("aeo_clients.id", ondelete="CASCADE"), nullable=False)

    severity = Column(String(20), nullable=False)  # critical, warning, opportunity, info
    alert_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    details = Column(JSONB, nullable=False)
    status = Column(String(20), default="new")  # new, acknowledged, resolved

    created_at = Column(DateTime, default=datetime.utcnow)
    acknowledged_at = Column(DateTime)
    resolved_at = Column(DateTime)

    # Relationships
    client = relationship("Client", back_populates="alerts")

    __table_args__ = (
        Index("ix_alerts_org_client_status", "organization_id", "client_id", "status"),
    )


class PerformanceSnapshot(Base):
    """Daily performance snapshots for trend analysis."""

    __tablename__ = "performance_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(UUID(as_uuid=True), ForeignKey("aeo_clients.id", ondelete="CASCADE"), nullable=False)

    snapshot_date = Column(DateTime, nullable=False)
    metrics = Column(JSONB, nullable=False)
    benchmarks = Column(JSONB, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    client = relationship("Client", back_populates="performance_snapshots")

    __table_args__ = (
        Index("ix_snapshots_org_client_date", "organization_id", "client_id", "snapshot_date"),
    )


# =============================================================================
# WEBHOOK CONFIGURATION
# =============================================================================


class WebhookEndpoint(Base):
    """
    Webhook endpoint configuration for notifications.

    Organizations can configure webhooks to receive notifications
    about alerts, monitoring results, and system events.
    """

    __tablename__ = "webhook_endpoints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Endpoint configuration
    url = Column(String(2048), nullable=False)
    secret_hash = Column(String(255))  # Hashed secret for signature verification
    events = Column(JSONB, default=list)  # List of subscribed event types
    headers = Column(JSONB, default=dict)  # Additional headers to send

    # Status
    is_active = Column(Boolean, default=True)
    last_triggered_at = Column(DateTime)
    last_success_at = Column(DateTime)
    last_failure_at = Column(DateTime)
    consecutive_failures = Column(Integer, default=0)

    # Metadata
    name = Column(String(255))  # User-provided name
    description = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_webhooks_org_active", "organization_id", "is_active"),
    )


class WebhookDelivery(Base):
    """
    Log of webhook delivery attempts.

    Tracks each delivery attempt for debugging and retry purposes.
    """

    __tablename__ = "webhook_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    webhook_id = Column(
        UUID(as_uuid=True),
        ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Event details
    event_type = Column(String(100), nullable=False)
    event_id = Column(String(100), nullable=False)
    payload = Column(JSONB, nullable=False)

    # Delivery result
    success = Column(Boolean, nullable=False)
    status_code = Column(Integer)
    response_body = Column(Text)
    error_message = Column(Text)
    attempts = Column(Integer, default=1)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_webhook_deliveries_webhook_created", "webhook_id", "created_at"),
    )
