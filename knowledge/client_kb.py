"""
Client Knowledge Base.

Central repository for all client intelligence that other agents access.
"""

from datetime import datetime
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from db.queries import (
    get_client,
    get_latest_intelligence,
    store_intelligence,
    get_monitoring_queries,
    get_recent_monitoring_results,
)
from knowledge.schemas import (
    ClientIntelligenceProfile,
    CompetitiveIntelligence,
    ContentAuthorityAnalysis,
    AEOPerformanceReport,
    BrandMention,
    AIQuery,
)

logger = structlog.get_logger()


class ClientKnowledgeBase:
    """
    Central knowledge repository for a client.

    Provides unified access to:
    - Client intelligence (from Cartographer)
    - Competitive intelligence (from Scout)
    - Content analysis (from Librarian)
    - Performance data (from Auditor)
    - Monitoring queries
    """

    def __init__(self, session: AsyncSession, client_id: UUID):
        self.session = session
        self.client_id = client_id
        self._log = logger.bind(client_id=str(client_id))

    async def get_client_profile(self) -> ClientIntelligenceProfile | None:
        """Get the latest client intelligence profile."""
        intel = await get_latest_intelligence(
            self.session,
            self.client_id,
            "cartographer",
        )
        if intel:
            return ClientIntelligenceProfile.model_validate(intel.data)
        return None

    async def store_client_profile(self, profile: ClientIntelligenceProfile) -> None:
        """Store/update client intelligence profile."""
        await store_intelligence(
            self.session,
            self.client_id,
            "cartographer",
            profile.model_dump(mode="json"),
        )
        self._log.info("client_profile_stored")

    async def get_competitive_intelligence(self) -> CompetitiveIntelligence | None:
        """Get the latest competitive intelligence."""
        intel = await get_latest_intelligence(
            self.session,
            self.client_id,
            "scout",
        )
        if intel:
            return CompetitiveIntelligence.model_validate(intel.data)
        return None

    async def store_competitive_intelligence(
        self, intelligence: CompetitiveIntelligence
    ) -> None:
        """Store/update competitive intelligence."""
        await store_intelligence(
            self.session,
            self.client_id,
            "scout",
            intelligence.model_dump(mode="json"),
        )
        self._log.info("competitive_intelligence_stored")

    async def get_content_analysis(self) -> ContentAuthorityAnalysis | None:
        """Get the latest content analysis."""
        intel = await get_latest_intelligence(
            self.session,
            self.client_id,
            "librarian",
        )
        if intel:
            return ContentAuthorityAnalysis.model_validate(intel.data)
        return None

    async def store_content_analysis(self, analysis: ContentAuthorityAnalysis) -> None:
        """Store/update content analysis."""
        await store_intelligence(
            self.session,
            self.client_id,
            "librarian",
            analysis.model_dump(mode="json"),
        )
        self._log.info("content_analysis_stored")

    async def get_performance_report(self) -> AEOPerformanceReport | None:
        """Get the latest performance report."""
        intel = await get_latest_intelligence(
            self.session,
            self.client_id,
            "auditor",
        )
        if intel:
            return AEOPerformanceReport.model_validate(intel.data)
        return None

    async def store_performance_report(self, report: AEOPerformanceReport) -> None:
        """Store/update performance report."""
        await store_intelligence(
            self.session,
            self.client_id,
            "auditor",
            report.model_dump(mode="json"),
        )
        self._log.info("performance_report_stored")

    async def get_monitoring_queries(self) -> list[AIQuery]:
        """Get active monitoring queries for this client."""
        queries = await get_monitoring_queries(self.session, self.client_id)

        # Get client profile to add brand names
        profile = await self.get_client_profile()

        brand_names = []
        competitor_names = []

        if profile:
            # Extract brand names from profile
            brand_names = [profile.company_essence.split()[0]]  # Use first word as brand
            if profile.offerings:
                brand_names.extend([o.name for o in profile.offerings])

        # Get competitor names from competitive intelligence
        comp_intel = await self.get_competitive_intelligence()
        if comp_intel:
            competitor_names = [c.name for c in comp_intel.competitors]

        return [
            AIQuery(
                query_text=q.query,
                query_type=q.query_type or "general",
                brand_names=brand_names,
                competitor_names=competitor_names,
            )
            for q in queries
        ]

    async def get_recent_mentions(self, hours: int = 24) -> list[BrandMention]:
        """Get recent brand mentions from monitoring."""
        results = await get_recent_monitoring_results(
            self.session,
            self.client_id,
            hours=hours,
        )

        return [
            BrandMention(
                query=r.query.query if r.query else "",
                engine=r.engine,
                mentioned=r.brand_mentioned,
                position=r.mention_position,
                recommended=r.recommended,
                sentiment=r.sentiment,
                accuracy=r.accuracy,
                context="",  # Not stored in result
                sources_cited=r.sources_cited or [],
                competitors_mentioned=r.competitors_mentioned or [],
                response_text=r.response_text or "",
            )
            for r in results
        ]

    async def get_full_context(self) -> dict:
        """Get complete client context for agent use."""
        profile = await self.get_client_profile()
        comp_intel = await self.get_competitive_intelligence()
        content = await self.get_content_analysis()
        performance = await self.get_performance_report()

        client = await get_client(self.session, self.client_id)

        return {
            "client": {
                "id": str(self.client_id),
                "name": client.name if client else None,
                "domain": client.domain if client else None,
                "industry": client.industry if client else None,
            },
            "profile": profile.model_dump() if profile else None,
            "competitive_intelligence": comp_intel.model_dump() if comp_intel else None,
            "content_analysis": content.model_dump() if content else None,
            "performance": performance.model_dump() if performance else None,
        }
