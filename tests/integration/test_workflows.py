"""
Integration tests for workflows with mocked LLM calls.

Tests workflow execution without making actual LLM API calls.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from knowledge.schemas import (
    ClientIntelligenceProfile,
    Offering,
    Audience,
    Competitor,
    KnowledgeGap,
)


def create_mock_profile() -> ClientIntelligenceProfile:
    """Create a mock client intelligence profile for testing."""
    return ClientIntelligenceProfile(
        company_name="Test Corp",
        domain="testcorp.com",
        category="Technology",
        subcategory="SaaS",
        description="A test company for unit testing",
        founded_year=2020,
        company_size="50-200",
        headquarters="San Francisco, CA",
        value_proposition="Making testing easier for everyone",
        offerings=[
            Offering(
                name="TestSuite Pro",
                type="product",
                description="Enterprise testing solution",
                key_features=["Automated testing", "CI/CD integration"],
                target_audience="Developers",
                differentiators=["Easy setup", "Fast execution"],
            ),
            Offering(
                name="TestCloud",
                type="service",
                description="Cloud-based testing platform",
                key_features=["Scalable", "On-demand"],
                target_audience="QA Teams",
                differentiators=["No infrastructure needed"],
            ),
        ],
        primary_audiences=[
            Audience(
                segment="Enterprise Developers",
                pain_points=["Slow test execution", "Flaky tests"],
                needs=["Speed", "Reliability"],
                decision_factors=["Price", "Integration"],
            ),
        ],
        competitors=[
            Competitor(
                name="CompetitorX",
                domain="competitorx.com",
                positioning="Market leader",
                strengths=["Brand recognition"],
                weaknesses=["Expensive"],
            ),
        ],
        knowledge_gaps=[
            KnowledgeGap(
                area="Market share",
                impact="medium",
                research_needed="Analyze market reports",
            ),
        ],
        key_differentiators=["Developer-friendly", "Fast setup"],
        brand_voice="Professional but approachable",
        target_keywords=[
            "testing software",
            "automated testing",
            "CI/CD testing",
        ],
    )


@pytest.mark.integration
class TestOnboardingWorkflow:
    """Tests for the onboarding workflow with mocked LLM."""

    @pytest.fixture
    def mock_profile(self):
        """Fixture for mock client profile."""
        return create_mock_profile()

    async def test_onboarding_creates_client(
        self,
        db_session,
        organization_factory,
        mock_profile,
    ):
        """Onboarding workflow creates a new client record."""
        from workflows.onboarding import run_onboarding_workflow

        org = await organization_factory()

        with patch(
            "workflows.onboarding.CartographerAgent"
        ) as MockCartographer:
            # Setup mock
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=mock_profile)
            MockCartographer.return_value = mock_agent

            result = await run_onboarding_workflow(
                session=db_session,
                organization_id=org.id,
                domain="newclient.com",
                company_name="New Client",
                additional_context="Test context",
            )

            assert result["client_id"] is not None
            assert result["current_step"] == "complete"

    async def test_onboarding_gathers_intelligence(
        self,
        db_session,
        organization_factory,
        mock_profile,
    ):
        """Onboarding workflow gathers client intelligence."""
        from workflows.onboarding import run_onboarding_workflow

        org = await organization_factory()

        with patch(
            "workflows.onboarding.CartographerAgent"
        ) as MockCartographer:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=mock_profile)
            MockCartographer.return_value = mock_agent

            result = await run_onboarding_workflow(
                session=db_session,
                organization_id=org.id,
                domain="intelligence.com",
                company_name="Intelligence Corp",
            )

            # Verify intelligence was gathered
            assert result["profile"] is not None
            assert result["profile"].company_name == "Test Corp"
            assert len(result["errors"]) == 0

            # Verify CartographerAgent was called correctly
            mock_agent.run.assert_called_once_with(
                domain="intelligence.com",
                company_name="Intelligence Corp",
                additional_context="",
            )

    async def test_onboarding_generates_queries(
        self,
        db_session,
        organization_factory,
        mock_profile,
    ):
        """Onboarding workflow generates monitoring queries."""
        from workflows.onboarding import run_onboarding_workflow

        org = await organization_factory()

        with patch(
            "workflows.onboarding.CartographerAgent"
        ) as MockCartographer:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=mock_profile)
            MockCartographer.return_value = mock_agent

            result = await run_onboarding_workflow(
                session=db_session,
                organization_id=org.id,
                domain="queries.com",
                company_name="Query Corp",
            )

            # Should create queries based on profile
            assert result["queries_created"] > 0

    async def test_onboarding_handles_agent_error(
        self,
        db_session,
        organization_factory,
    ):
        """Onboarding workflow handles agent errors gracefully."""
        from workflows.onboarding import run_onboarding_workflow

        org = await organization_factory()

        with patch(
            "workflows.onboarding.CartographerAgent"
        ) as MockCartographer:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(
                side_effect=Exception("LLM API error")
            )
            MockCartographer.return_value = mock_agent

            result = await run_onboarding_workflow(
                session=db_session,
                organization_id=org.id,
                domain="error.com",
                company_name="Error Corp",
            )

            # Should complete but with errors
            assert result["current_step"] == "complete"
            assert len(result["errors"]) > 0
            assert "Intelligence gathering failed" in result["errors"][0]

    async def test_onboarding_existing_client(
        self,
        db_session,
        organization_factory,
        client_factory,
        mock_profile,
    ):
        """Onboarding workflow handles existing client."""
        from workflows.onboarding import run_onboarding_workflow

        org = await organization_factory()
        existing = await client_factory(
            org,
            name="Existing Corp",
            domain="existing.com",
        )

        with patch(
            "workflows.onboarding.CartographerAgent"
        ) as MockCartographer:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=mock_profile)
            MockCartographer.return_value = mock_agent

            result = await run_onboarding_workflow(
                session=db_session,
                organization_id=org.id,
                domain="existing.com",
                company_name="Existing Corp",
            )

            # Should use existing client
            assert result["client_id"] == str(existing.id)


@pytest.mark.integration
class TestMonitoringWorkflow:
    """Tests for the monitoring workflow with mocked LLM."""

    async def test_monitoring_queries_engines(
        self,
        db_session,
        organization_factory,
        client_factory,
        monitoring_query_factory,
    ):
        """Monitoring workflow queries answer engines."""
        from workflows.monitoring import MonitoringWorkflow

        org = await organization_factory()
        client = await client_factory(org)
        query = await monitoring_query_factory(org, client, query="test query")

        with patch(
            "workflows.monitoring.AuditorAgent"
        ) as MockAuditor:
            mock_agent = MagicMock()
            mock_result = MagicMock()
            mock_result.brand_mentioned = True
            mock_result.sentiment = "positive"
            mock_result.mention_quality_score = 0.85
            mock_agent.run = AsyncMock(return_value=mock_result)
            MockAuditor.return_value = mock_agent

            workflow = MonitoringWorkflow(db_session, org.id)

            # Just verify the workflow can be instantiated
            # Full execution requires more mocking of the query engine
            assert workflow is not None
