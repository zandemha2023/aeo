"""
The Cartographer - Client Intelligence Specialist

"I map territories others don't even know exist. Before you can win a game,
you need to understand the board—every piece, every player, every possible move.
I see the complete picture of who you are, what you offer, and where you fit in the world."
"""

from typing import Any

import httpx
import structlog
from bs4 import BeautifulSoup

from agents.base import Agent, AgentPersonality
from knowledge.schemas import (
    Audience,
    BrandPerception,
    BrandVoice,
    ClientIntelligenceProfile,
    MarketPosition,
    Offering,
)

logger = structlog.get_logger()


class CartographerAgent(Agent):
    """
    Client Intelligence Specialist.

    Builds and maintains a comprehensive, nuanced understanding of the client's
    business that enables all other agents to make intelligent decisions.
    """

    @property
    def personality(self) -> AgentPersonality:
        return AgentPersonality(
            name="The Cartographer",
            title="Client Intelligence Specialist",
            identity="""I map territories others don't even know exist. Before you can win
a game, you need to understand the board—every piece, every player, every possible move.
I see the complete picture of who you are, what you offer, and where you fit in the world.""",
            personality_traits=[
                "Obsessively thorough—leaves no stone unturned",
                "Systems thinker—sees connections between disparate information",
                "Skeptical of surface-level understanding",
                "Patient—willing to dig deep before drawing conclusions",
            ],
            core_mission="""Build and maintain a comprehensive, nuanced understanding of
the client's business that enables all other agents to make intelligent decisions.""",
            thinking_style="""When I encounter a new client, I don't just catalog their products.
I ask: What problem did this company exist to solve? Who are the people they serve?
What makes them genuinely different—not marketing different, actually different?
What do their customers say when they're not being prompted? What would make someone
choose them over the 50 alternatives?

I build a mental model so complete that I could explain this business to a stranger
and they'd understand not just what the company does, but why it matters.""",
        )

    async def run(
        self,
        domain: str,
        company_name: str,
        additional_context: str = "",
    ) -> ClientIntelligenceProfile:
        """
        Gather comprehensive intelligence about a client.

        Args:
            domain: The client's website domain (e.g., "example.com")
            company_name: The client's company name
            additional_context: Any additional context provided by the user

        Returns:
            Complete ClientIntelligenceProfile
        """
        self._log_task_start(
            "gather_client_intelligence",
            domain=domain,
            company_name=company_name,
        )

        # Gather raw information from the website
        website_content = await self._crawl_website(domain)

        # Build the intelligence profile using LLM analysis
        profile = await self._analyze_and_build_profile(
            domain=domain,
            company_name=company_name,
            website_content=website_content,
            additional_context=additional_context,
        )

        self._log_task_complete(
            "gather_client_intelligence",
            offerings_count=len(profile.offerings),
            audiences_count=len(profile.primary_audiences),
        )

        return profile

    async def _crawl_website(self, domain: str) -> dict[str, str]:
        """
        Crawl key pages from the client's website.

        Returns dict mapping page type to content.
        """
        self._log.info("crawling_website", domain=domain)

        key_paths = [
            "/",  # Homepage
            "/about",
            "/about-us",
            "/company",
            "/products",
            "/services",
            "/solutions",
            "/pricing",
            "/features",
        ]

        content = {}
        base_url = f"https://{domain}"

        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "AEO-Cartographer/1.0"},
        ) as client:
            for path in key_paths:
                try:
                    url = f"{base_url}{path}"
                    response = await client.get(url)

                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, "lxml")

                        # Remove script and style elements
                        for element in soup(["script", "style", "nav", "footer"]):
                            element.decompose()

                        # Get text content
                        text = soup.get_text(separator="\n", strip=True)

                        # Limit content length
                        if len(text) > 10000:
                            text = text[:10000] + "..."

                        content[path] = text
                        self._log.debug("page_crawled", url=url, length=len(text))

                except httpx.HTTPError as e:
                    self._log.debug("page_failed", path=path, error=str(e))
                    continue

        self._log.info("crawl_complete", pages_found=len(content))
        return content

    async def _analyze_and_build_profile(
        self,
        domain: str,
        company_name: str,
        website_content: dict[str, str],
        additional_context: str,
    ) -> ClientIntelligenceProfile:
        """Use LLM to analyze website content and build intelligence profile."""

        # Prepare content summary for the LLM
        content_text = "\n\n---\n\n".join(
            f"PAGE: {path}\n{content}" for path, content in website_content.items()
        )

        task_context = """Your task is to analyze this company's website and build a comprehensive
intelligence profile. Focus on understanding:

1. CORE IDENTITY: What does this company actually do? What problem do they solve?
2. PRODUCTS/SERVICES: What do they offer? What are the key differentiators?
3. AUDIENCE: Who are they serving? What do those people need?
4. POSITIONING: How do they position themselves? What's their market position?
5. VOICE: How do they communicate? What's their brand personality?
6. AUTHORITY: What are they experts in? What credentials do they have?

Be thorough but also skeptical. Don't just repeat marketing language—extract the real substance.
Look for concrete facts, specific features, actual customer problems solved."""

        prompt = f"""Analyze the following website content for {company_name} ({domain}):

{content_text}

{f"Additional context provided: {additional_context}" if additional_context else ""}

Based on this analysis, build a comprehensive client intelligence profile.

Key questions to answer:
- What is this company's essence in one paragraph?
- What core problem do they solve?
- What makes them genuinely different (not marketing speak)?
- What products/services do they offer?
- Who are their target audiences and what do they need?
- What is their market position (leader/challenger/niche/emerging)?
- How do customers perceive them (based on any testimonials or reviews)?
- What is their brand voice and communication style?
- What topics do they have genuine authority in?
- What are their likely business goals?

Provide specific, concrete answers based on evidence from the content."""

        # Call LLM for structured analysis
        profile = self._call_llm_structured(
            user_prompt=prompt,
            output_schema=ClientIntelligenceProfile,
            task_context=task_context,
            max_tokens=8192,
        )

        return profile

    async def update_profile(
        self,
        existing_profile: ClientIntelligenceProfile,
        new_information: str,
    ) -> ClientIntelligenceProfile:
        """
        Update an existing profile with new information.

        Used for incremental updates rather than full re-analysis.
        """
        self._log_task_start("update_profile")

        task_context = """You are updating an existing client intelligence profile with new
information. Preserve what's still accurate, update what's changed, and add new insights.
Be conservative—don't make changes unless the new information clearly warrants them."""

        prompt = f"""Current profile:
{existing_profile.model_dump_json(indent=2)}

New information to incorporate:
{new_information}

Update the profile to incorporate this new information while preserving existing
accurate information. Only make changes that are clearly warranted by the new data."""

        updated_profile = self._call_llm_structured(
            user_prompt=prompt,
            output_schema=ClientIntelligenceProfile,
            task_context=task_context,
            max_tokens=8192,
        )

        self._log_task_complete("update_profile")
        return updated_profile
