"""
The Scout - Competitive Intelligence Specialist

"I live in enemy territory. I know what your competitors are doing before they
announce it, what content they're creating, where they're showing up in AI answers,
and most importantly—where they're vulnerable. Every competitor has blind spots. I find them."
"""

import asyncio
from datetime import datetime
from typing import Any

import httpx
import structlog
from bs4 import BeautifulSoup

from agents.base import Agent, AgentPersonality
from engine.query import query_all_engines
from engine.parse import extract_brand_mentions
from knowledge.schemas import (
    AIQuery,
    CompetitiveAlert,
    CompetitiveIntelligence,
    CompetitorProfile,
    MarketOpportunity,
    QueryComparison,
)

logger = structlog.get_logger()


class ScoutAgent(Agent):
    """
    Competitive Intelligence Specialist.

    Monitors competitive landscape continuously. Understands not just what
    competitors are doing, but why they're winning or losing in AI visibility,
    and where opportunities exist.
    """

    @property
    def personality(self) -> AgentPersonality:
        return AgentPersonality(
            name="The Scout",
            title="Competitive Intelligence Specialist",
            identity="""I live in enemy territory. I know what your competitors are doing
before they announce it, what content they're creating, where they're showing up
in AI answers, and most importantly—where they're vulnerable. Every competitor
has blind spots. I find them.""",
            personality_traits=[
                "Paranoid in a productive way—always watching",
                "Competitive—takes satisfaction in finding weaknesses",
                "Strategic—thinks about competitive moves as chess, not checkers",
                "Dispassionate—reports reality, not what client wants to hear",
            ],
            core_mission="""Monitor competitive landscape continuously. Understand not just
what competitors are doing, but why they're winning or losing in AI visibility,
and where opportunities exist.""",
            thinking_style="""When I analyze a competitor, I'm not just listing their features.
I'm asking: Why does ChatGPT recommend them for X query? What content do they have
that we don't? What authority signals are they leveraging? Where are they overexposed
and vulnerable to being displaced? What queries are they winning that we should be winning?

I think about competitive intelligence as finding asymmetries—places where we can win
disproportionately because of something the competitor can't easily copy or respond to.""",
        )

    async def run(
        self,
        client_name: str,
        client_domain: str,
        competitors: list[dict[str, str]],
        category_queries: list[str],
    ) -> CompetitiveIntelligence:
        """
        Gather comprehensive competitive intelligence.

        Args:
            client_name: The client's company name
            client_domain: The client's domain
            competitors: List of competitor dicts with 'name' and 'domain'
            category_queries: Queries to test for competitive visibility

        Returns:
            Complete CompetitiveIntelligence analysis
        """
        self._log_task_start(
            "gather_competitive_intelligence",
            client=client_name,
            competitor_count=len(competitors),
        )

        # Analyze each competitor
        competitor_profiles = await asyncio.gather(
            *[
                self._analyze_competitor(
                    comp["name"],
                    comp["domain"],
                    client_name,
                    category_queries,
                )
                for comp in competitors
            ]
        )

        # Calculate share of voice
        share_of_voice = self._calculate_share_of_voice(
            client_name,
            competitor_profiles,
        )

        # Identify market opportunities
        opportunities = await self._identify_opportunities(
            client_name,
            competitor_profiles,
            category_queries,
        )

        # Generate competitive alerts
        alerts = self._generate_alerts(competitor_profiles, client_name)

        intelligence = CompetitiveIntelligence(
            competitors=competitor_profiles,
            share_of_voice=share_of_voice,
            market_opportunities=opportunities,
            competitive_alerts=alerts,
            last_updated=datetime.utcnow(),
        )

        self._log_task_complete(
            "gather_competitive_intelligence",
            competitors_analyzed=len(competitor_profiles),
            opportunities_found=len(opportunities),
        )

        return intelligence

    async def _analyze_competitor(
        self,
        competitor_name: str,
        competitor_domain: str,
        client_name: str,
        category_queries: list[str],
    ) -> CompetitorProfile:
        """Analyze a single competitor's AI visibility and positioning."""
        self._log.info("analyzing_competitor", competitor=competitor_name)

        # Query AI engines for competitor mentions
        mention_results = await self._query_competitor_visibility(
            competitor_name,
            category_queries,
        )

        # Analyze competitor website for positioning
        positioning_data = await self._analyze_competitor_website(
            competitor_domain,
            competitor_name,
        )

        # Compare with client
        comparisons = await self._compare_with_client(
            competitor_name,
            client_name,
            category_queries,
        )

        # Calculate metrics
        total_queries = len(mention_results)
        mentioned_count = sum(1 for m in mention_results if m["mentioned"])
        recommended_count = sum(1 for m in mention_results if m.get("recommended"))
        cited_count = sum(1 for m in mention_results if m.get("cited"))

        mention_rate = mentioned_count / total_queries if total_queries > 0 else 0
        recommendation_rate = recommended_count / mentioned_count if mentioned_count > 0 else 0
        citation_rate = cited_count / mentioned_count if mentioned_count > 0 else 0

        # Determine engine strengths
        engine_performance = {}
        for result in mention_results:
            engine = result["engine"]
            if engine not in engine_performance:
                engine_performance[engine] = {"mentioned": 0, "total": 0}
            engine_performance[engine]["total"] += 1
            if result["mentioned"]:
                engine_performance[engine]["mentioned"] += 1

        engines_strong = [
            e for e, p in engine_performance.items()
            if p["total"] > 0 and p["mentioned"] / p["total"] > 0.5
        ]
        engines_weak = [
            e for e, p in engine_performance.items()
            if p["total"] > 0 and p["mentioned"] / p["total"] < 0.3
        ]

        return CompetitorProfile(
            name=competitor_name,
            website=competitor_domain,
            ai_mention_rate=mention_rate,
            ai_recommendation_rate=recommendation_rate,
            ai_citation_rate=citation_rate,
            engines_strong_on=engines_strong,
            engines_weak_on=engines_weak,
            content_strengths=positioning_data.get("strengths", []),
            content_gaps=positioning_data.get("gaps", []),
            authority_sources=positioning_data.get("authority_sources", []),
            positioning=positioning_data.get("positioning", ""),
            key_differentiators=positioning_data.get("differentiators", []),
            vulnerabilities=positioning_data.get("vulnerabilities", []),
            beating_us_on=comparisons.get("they_win", []),
            we_beat_them_on=comparisons.get("we_win", []),
            neither_winning=comparisons.get("neither", []),
        )

    async def _query_competitor_visibility(
        self,
        competitor_name: str,
        queries: list[str],
    ) -> list[dict]:
        """Query AI engines to measure competitor visibility."""
        results = []

        for query_text in queries[:10]:  # Limit to avoid rate limits
            query = AIQuery(
                query_text=query_text,
                query_type="category",
                brand_names=[competitor_name],
                competitor_names=[],
            )

            try:
                responses = await query_all_engines(query)

                for response in responses:
                    if response.error:
                        continue

                    mentioned = competitor_name.lower() in response.response_text.lower()
                    recommended = self._check_if_recommended(
                        response.response_text,
                        competitor_name,
                    )

                    results.append({
                        "query": query_text,
                        "engine": response.engine,
                        "mentioned": mentioned,
                        "recommended": recommended,
                        "cited": bool(response.sources_cited),
                    })

            except Exception as e:
                self._log.warning(
                    "competitor_query_failed",
                    query=query_text,
                    error=str(e),
                )

        return results

    def _check_if_recommended(self, response_text: str, brand: str) -> bool:
        """Check if a brand is recommended in the response."""
        response_lower = response_text.lower()
        brand_lower = brand.lower()

        recommendation_patterns = [
            f"recommend {brand_lower}",
            f"{brand_lower} is a great",
            f"{brand_lower} is excellent",
            f"consider {brand_lower}",
            f"try {brand_lower}",
            f"best.*{brand_lower}",
            f"{brand_lower}.*top pick",
        ]

        import re
        for pattern in recommendation_patterns:
            if re.search(pattern, response_lower):
                return True

        return False

    async def _analyze_competitor_website(
        self,
        domain: str,
        name: str,
    ) -> dict:
        """Analyze competitor website for positioning and content."""
        self._log.info("analyzing_competitor_website", domain=domain)

        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
            ) as client:
                response = await client.get(f"https://{domain}")

                if response.status_code != 200:
                    return self._empty_positioning()

                soup = BeautifulSoup(response.text, "lxml")

                # Remove noise
                for element in soup(["script", "style", "nav", "footer"]):
                    element.decompose()

                text = soup.get_text(separator="\n", strip=True)[:8000]

        except Exception as e:
            self._log.warning("website_analysis_failed", domain=domain, error=str(e))
            return self._empty_positioning()

        # Use LLM to analyze positioning
        task_context = """Analyze this competitor's website to understand their positioning,
strengths, weaknesses, and authority signals. Be specific and actionable."""

        prompt = f"""Analyze this competitor website content for {name} ({domain}):

{text}

Provide analysis as JSON:
{{
    "positioning": "One sentence describing their market positioning",
    "differentiators": ["List of key differentiators"],
    "strengths": ["Content/authority strengths"],
    "gaps": ["Notable content gaps or weaknesses"],
    "authority_sources": ["Where they derive authority (awards, press, certifications)"],
    "vulnerabilities": ["Strategic vulnerabilities we could exploit"]
}}

Respond ONLY with the JSON object."""

        try:
            response_text = self._call_llm(prompt, task_context, max_tokens=2048)

            import json
            import re

            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                return json.loads(json_match.group())

        except Exception as e:
            self._log.warning("positioning_analysis_failed", error=str(e))

        return self._empty_positioning()

    def _empty_positioning(self) -> dict:
        """Return empty positioning data."""
        return {
            "positioning": "",
            "differentiators": [],
            "strengths": [],
            "gaps": [],
            "authority_sources": [],
            "vulnerabilities": [],
        }

    async def _compare_with_client(
        self,
        competitor_name: str,
        client_name: str,
        queries: list[str],
    ) -> dict:
        """Compare client and competitor on specific queries."""
        comparisons = {"they_win": [], "we_win": [], "neither": []}

        for query_text in queries[:5]:  # Limit comparisons
            query = AIQuery(
                query_text=query_text,
                query_type="comparison",
                brand_names=[client_name, competitor_name],
                competitor_names=[],
            )

            try:
                responses = await query_all_engines(query, engines=["chatgpt", "claude"])

                client_mentioned = 0
                competitor_mentioned = 0

                for response in responses:
                    if client_name.lower() in response.response_text.lower():
                        client_mentioned += 1
                    if competitor_name.lower() in response.response_text.lower():
                        competitor_mentioned += 1

                if competitor_mentioned > client_mentioned:
                    comparisons["they_win"].append(
                        QueryComparison(
                            query=query_text,
                            why_they_win=f"Mentioned in {competitor_mentioned}/{len(responses)} engines vs our {client_mentioned}",
                            what_we_need="Content optimization for this query type",
                        )
                    )
                elif client_mentioned > competitor_mentioned:
                    comparisons["we_win"].append(
                        QueryComparison(
                            query=query_text,
                            why_they_win="N/A - we're winning",
                            what_we_need="Maintain current advantage",
                        )
                    )
                else:
                    comparisons["neither"].append(query_text)

            except Exception as e:
                self._log.warning("comparison_failed", query=query_text, error=str(e))

        return comparisons

    def _calculate_share_of_voice(
        self,
        client_name: str,
        competitor_profiles: list[CompetitorProfile],
    ) -> dict[str, float]:
        """Calculate share of voice across all competitors."""
        total_mention_rate = sum(c.ai_mention_rate for c in competitor_profiles)

        if total_mention_rate == 0:
            return {c.name: 0.0 for c in competitor_profiles}

        return {
            c.name: round(c.ai_mention_rate / total_mention_rate * 100, 1)
            for c in competitor_profiles
        }

    async def _identify_opportunities(
        self,
        client_name: str,
        competitor_profiles: list[CompetitorProfile],
        queries: list[str],
    ) -> list[MarketOpportunity]:
        """Identify market opportunities based on competitive gaps."""
        opportunities = []

        # Find queries where no competitor is strong
        for query in queries[:5]:
            weak_competitors = []
            for comp in competitor_profiles:
                if comp.ai_mention_rate < 0.3:
                    weak_competitors.append(comp.name)

            if len(weak_competitors) >= len(competitor_profiles) / 2:
                opportunities.append(
                    MarketOpportunity(
                        opportunity=f"Low competition for: {query}",
                        competitors_missing=weak_competitors,
                        difficulty="medium",
                        potential_impact="high",
                    )
                )

        # Find vulnerability-based opportunities
        for comp in competitor_profiles:
            for vulnerability in comp.vulnerabilities[:2]:
                opportunities.append(
                    MarketOpportunity(
                        opportunity=f"Exploit {comp.name}'s weakness: {vulnerability}",
                        competitors_missing=[comp.name],
                        difficulty="medium",
                        potential_impact="medium",
                    )
                )

        return opportunities[:10]  # Limit to top 10

    def _generate_alerts(
        self,
        competitor_profiles: list[CompetitorProfile],
        client_name: str,
    ) -> list[CompetitiveAlert]:
        """Generate alerts for significant competitive situations."""
        alerts = []

        for comp in competitor_profiles:
            # Alert if competitor has very high visibility
            if comp.ai_mention_rate > 0.7:
                alerts.append(
                    CompetitiveAlert(
                        competitor=comp.name,
                        event=f"High AI visibility ({comp.ai_mention_rate:.0%} mention rate)",
                        threat_level="respond",
                        recommended_response="Analyze their content strategy and identify differentiating angles",
                    )
                )

            # Alert if they're beating us significantly
            if len(comp.beating_us_on) > 3:
                alerts.append(
                    CompetitiveAlert(
                        competitor=comp.name,
                        event=f"Winning on {len(comp.beating_us_on)} query categories",
                        threat_level="respond",
                        recommended_response="Prioritize content creation for lost queries",
                    )
                )

        return alerts
