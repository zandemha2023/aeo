"""SQLAlchemy models for AEO database."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class Client(Base):
    """AEO client."""

    __tablename__ = "aeo_clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    domain = Column(String(255), nullable=False, unique=True)
    industry = Column(String(100), nullable=True)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    intelligence = relationship("ClientIntelligence", back_populates="client")
    monitoring_queries = relationship("MonitoringQuery", back_populates="client")
    monitoring_results = relationship("MonitoringResult", back_populates="client")
    alerts = relationship("Alert", back_populates="client")


class ClientIntelligence(Base):
    """Client intelligence gathered by agents."""

    __tablename__ = "client_intelligence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("aeo_clients.id"), nullable=False)
    intelligence_type = Column(String(50), nullable=False)  # cartographer, scout, librarian, auditor
    data = Column(JSONB, nullable=False)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    client = relationship("Client", back_populates="intelligence")


class MonitoringQuery(Base):
    """Queries to monitor for brand mentions."""

    __tablename__ = "monitoring_queries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("aeo_clients.id"), nullable=False)
    query = Column(Text, nullable=False)
    query_type = Column(String(50))  # brand, product, comparison, category, how_to
    priority = Column(Integer, default=50)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    client = relationship("Client", back_populates="monitoring_queries")
    results = relationship("MonitoringResult", back_populates="query")


class MonitoringResult(Base):
    """Results from monitoring queries."""

    __tablename__ = "monitoring_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("aeo_clients.id"), nullable=False)
    query_id = Column(UUID(as_uuid=True), ForeignKey("monitoring_queries.id"), nullable=False)
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


class Alert(Base):
    """Alerts for significant AEO events."""

    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("aeo_clients.id"), nullable=False)
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


class PerformanceSnapshot(Base):
    """Daily performance snapshots for trend analysis."""

    __tablename__ = "performance_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("aeo_clients.id"), nullable=False)
    snapshot_date = Column(DateTime, nullable=False)
    metrics = Column(JSONB, nullable=False)
    benchmarks = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
