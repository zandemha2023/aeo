"""
Pytest configuration and fixtures for AEO Orchestrator tests.

Provides fixtures for:
- Database sessions (in-memory SQLite for unit tests)
- Test client for API testing
- Factory functions for creating test data
- Authentication fixtures
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import AsyncGenerator, Generator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import create_access_token, hash_password, generate_api_key
from api.deps import get_session
from api.main import app
from config import Settings, get_settings
from db.models import (
    Base,
    Organization,
    User,
    APIKey,
    Client,
    ClientIntelligence,
    MonitoringQuery,
    MonitoringResult,
    Alert,
    LLMUsage,
)


# =============================================================================
# TEST SETTINGS
# =============================================================================


def get_test_settings() -> Settings:
    """Get settings configured for testing."""
    return Settings(
        anthropic_api_key="test-api-key",
        database_url="sqlite+aiosqlite:///:memory:",
        database_sync_url="sqlite:///:memory:",
        jwt_secret_key="test-secret-key-for-testing-only",
        app_env="testing",
        log_level="DEBUG",
        rate_limit_enabled=False,
        redis_url="redis://localhost:6379",
    )


# =============================================================================
# DATABASE FIXTURES
# =============================================================================


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_engine():
    """Create async database engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for testing."""
    async_session_maker = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
def override_get_session(db_session: AsyncSession):
    """Override the get_session dependency for testing."""

    async def _override_get_session():
        yield db_session

    return _override_get_session


# =============================================================================
# TEST CLIENT FIXTURES
# =============================================================================


@pytest.fixture
def test_client(override_get_session) -> Generator[TestClient, None, None]:
    """Create synchronous test client."""
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_settings] = get_test_settings

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def async_client(override_get_session) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client."""
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_settings] = get_test_settings

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


# =============================================================================
# FACTORY FIXTURES
# =============================================================================


@pytest.fixture
async def organization_factory(db_session: AsyncSession):
    """Factory for creating test organizations."""

    async def _create_organization(
        name: str = "Test Organization",
        slug: str | None = None,
        plan: str = "free",
        monthly_llm_budget_usd: Decimal = Decimal("100.00"),
        rate_limit_rpm: int = 60,
        status: str = "active",
    ) -> Organization:
        org = Organization(
            id=uuid4(),
            name=name,
            slug=slug or f"test-org-{uuid4().hex[:8]}",
            plan=plan,
            monthly_llm_budget_usd=monthly_llm_budget_usd,
            rate_limit_rpm=rate_limit_rpm,
            status=status,
        )
        db_session.add(org)
        await db_session.commit()
        await db_session.refresh(org)
        return org

    return _create_organization


@pytest.fixture
async def user_factory(db_session: AsyncSession):
    """Factory for creating test users."""

    async def _create_user(
        organization: Organization,
        email: str | None = None,
        password: str = "testpassword123",
        name: str = "Test User",
        role: str = "member",
        is_active: bool = True,
    ) -> User:
        user = User(
            id=uuid4(),
            organization_id=organization.id,
            email=email or f"user-{uuid4().hex[:8]}@test.com",
            password_hash=hash_password(password),
            name=name,
            role=role,
            is_active=is_active,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    return _create_user


@pytest.fixture
async def api_key_factory(db_session: AsyncSession):
    """Factory for creating test API keys."""

    async def _create_api_key(
        organization: Organization,
        name: str = "Test API Key",
        scopes: list[str] | None = None,
        is_active: bool = True,
        expires_at: datetime | None = None,
    ) -> tuple[APIKey, str]:
        """Returns tuple of (APIKey model, plain text key)."""
        full_key, key_prefix, key_hash = generate_api_key()

        api_key = APIKey(
            id=uuid4(),
            organization_id=organization.id,
            key_prefix=key_prefix,
            key_hash=key_hash,
            name=name,
            scopes=scopes or ["read", "write"],
            is_active=is_active,
            expires_at=expires_at,
        )
        db_session.add(api_key)
        await db_session.commit()
        await db_session.refresh(api_key)
        return api_key, full_key

    return _create_api_key


@pytest.fixture
async def client_factory(db_session: AsyncSession):
    """Factory for creating test AEO clients."""

    async def _create_client(
        organization: Organization,
        name: str = "Test Client",
        domain: str | None = None,
        industry: str = "Technology",
        status: str = "active",
    ) -> Client:
        client = Client(
            id=uuid4(),
            organization_id=organization.id,
            name=name,
            domain=domain or f"test-{uuid4().hex[:8]}.com",
            industry=industry,
            status=status,
        )
        db_session.add(client)
        await db_session.commit()
        await db_session.refresh(client)
        return client

    return _create_client


# =============================================================================
# AUTH FIXTURES
# =============================================================================


@pytest.fixture
async def test_org(organization_factory) -> Organization:
    """Create a default test organization."""
    return await organization_factory(name="Test Org", slug="test-org")


@pytest.fixture
async def test_user(user_factory, test_org) -> User:
    """Create a default test user."""
    return await user_factory(
        organization=test_org,
        email="testuser@test.com",
        role="admin",
    )


@pytest.fixture
async def test_api_key(api_key_factory, test_org) -> tuple[APIKey, str]:
    """Create a default test API key."""
    return await api_key_factory(organization=test_org, name="Test Key")


@pytest.fixture
def auth_token(test_user: User, test_org: Organization) -> str:
    """Create a JWT token for the test user."""
    return create_access_token(
        user_id=test_user.id,
        organization_id=test_org.id,
        email=test_user.email,
        role=test_user.role,
        expires_delta=timedelta(hours=1),
    )


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    """Get authorization headers with JWT token."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def api_key_headers(test_api_key: tuple[APIKey, str]) -> dict[str, str]:
    """Get authorization headers with API key."""
    _, plain_key = test_api_key
    return {"X-API-Key": plain_key}


# =============================================================================
# TEST DATA FIXTURES
# =============================================================================


@pytest.fixture
async def test_client_entity(client_factory, test_org) -> Client:
    """Create a default test AEO client entity."""
    return await client_factory(
        organization=test_org,
        name="Acme Corp",
        domain="acme.com",
        industry="Technology",
    )


@pytest.fixture
async def monitoring_query_factory(db_session: AsyncSession):
    """Factory for creating test monitoring queries."""

    async def _create_query(
        organization: Organization,
        client: Client,
        query: str = "best CRM software",
        query_type: str = "category",
        priority: int = 50,
        active: bool = True,
    ) -> MonitoringQuery:
        mq = MonitoringQuery(
            id=uuid4(),
            organization_id=organization.id,
            client_id=client.id,
            query=query,
            query_type=query_type,
            priority=priority,
            active=active,
        )
        db_session.add(mq)
        await db_session.commit()
        await db_session.refresh(mq)
        return mq

    return _create_query


@pytest.fixture
async def llm_usage_factory(db_session: AsyncSession):
    """Factory for creating test LLM usage records."""

    async def _create_usage(
        organization: Organization,
        agent: str = "cartographer",
        workflow: str = "onboarding",
        provider: str = "anthropic",
        model: str = "claude-sonnet-4-20250514",
        input_tokens: int = 1000,
        output_tokens: int = 500,
        cost_usd: Decimal = Decimal("0.015"),
        latency_ms: int = 2000,
        success: bool = True,
        client: Client | None = None,
    ) -> LLMUsage:
        usage = LLMUsage(
            id=uuid4(),
            organization_id=organization.id,
            agent=agent,
            workflow=workflow,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            success=success,
            client_id=client.id if client else None,
        )
        db_session.add(usage)
        await db_session.commit()
        await db_session.refresh(usage)
        return usage

    return _create_usage
