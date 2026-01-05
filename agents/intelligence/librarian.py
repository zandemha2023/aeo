"""
The Librarian - Content & Authority Analyst

"I know every piece of content you have, every place you're cited, every source of
authority you've built—and every gap where you should be but aren't. Content is power
in the AI age, but only if it's the right content in the right places."
"""

import asyncio
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import structlog
from bs4 import BeautifulSoup

from agents.base import Agent, AgentPersonality
from knowledge.schemas import (
    AuthoritySource,
    CitableContent,
    CitationOpportunity,
    CitabilitySignals,
    ContentAuthorityAnalysis,
    ContentGap,
    ContentPriority,
)

logger = structlog.get_logger()


class LibrarianAgent(Agent):
    """
    Content & Authority Analyst.

    Catalogs and assesses all client content, identifies what's working as AI
    source material, finds gaps, and understands where authority needs to be built.
    """

    @property
    def personality(self) -> AgentPersonality:
        return AgentPersonality(
            name="The Librarian",
            title="Content & Authority Analyst",
            identity="""I know every piece of content you have, every place you're cited,
every source of authority you've built—and every gap where you should be but aren't.
Content is power in the AI age, but only if it's the right content in the right places.""",
            personality_traits=[
                "Encyclopedic memory—knows all client content",
                "Quality-focused—distinguishes between content that will get cited and content that won't",
                "Strategic—thinks about content as authority-building assets",
                "Organized—maintains perfect information architecture",
            ],
            core_mission="""Catalog and assess all client content, identify what's working
as AI source material, find gaps, and understand where authority needs to be built.""",
            thinking_style="""When I analyze content, I'm not counting blog posts.
I'm asking: Is this content structured in a way AI can parse? Does it contain clear,
factual statements that can be excerpted? Is it on a domain/platform that AI engines
trust? Does it have the authority signals (citations, credentials, freshness) that
make it citable?

Most content is invisible to AI. I find the content that isn't—and figure out how
to create more of it.""",
        )

    async def run(
        self,
        domain: str,
        company_name: str,
        topics_of_authority: list[str],
        target_queries: list[str],
    ) -> ContentAuthorityAnalysis:
        """
        Analyze client's content and authority landscape.

        Args:
            domain: Client website domain
            company_name: Client company name
            topics_of_authority: Topics the client should be known for
            target_queries: Queries the client wants to appear for

        Returns:
            Complete ContentAuthorityAnalysis
        """
        self._log_task_start(
            "analyze_content_authority",
            domain=domain,
            topics=len(topics_of_authority),
        )

        # Crawl and analyze website content
        content_inventory = await self._crawl_content(domain)

        # Analyze citability of each piece
        citable_content = await self._analyze_citability(content_inventory, company_name)

        # Find external authority sources
        external_authority = await self._find_external_authority(
            company_name,
            domain,
        )

        # Identify content gaps
        content_gaps = await self._identify_content_gaps(
            citable_content,
            topics_of_authority,
            target_queries,
        )

        # Find citation opportunities
        citation_opportunities = self._identify_citation_opportunities(
            company_name,
            topics_of_authority,
            external_authority,
        )

        # Calculate content by type
        content_by_type = {}
        for content in citable_content:
            content_type = content.content_type
            content_by_type[content_type] = content_by_type.get(content_type, 0) + 1

        analysis = ContentAuthorityAnalysis(
            total_content_pieces=len(citable_content),
            content_by_type=content_by_type,
            ai_citable_content=citable_content,
            external_authority=external_authority,
            content_gaps=content_gaps,
            citation_opportunities=citation_opportunities,
            last_updated=datetime.utcnow(),
        )

        self._log_task_complete(
            "analyze_content_authority",
            content_pieces=len(citable_content),
            gaps_found=len(content_gaps),
            opportunities=len(citation_opportunities),
        )

        return analysis

    async def _crawl_content(self, domain: str) -> list[dict]:
        """Crawl website to build content inventory."""
        self._log.info("crawling_content", domain=domain)

        content_paths = [
            "/",
            "/blog",
            "/resources",
            "/guides",
            "/help",
            "/docs",
            "/documentation",
            "/learn",
            "/academy",
            "/knowledge-base",
        ]

        content_inventory = []
        base_url = f"https://{domain}"
        visited = set()

        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "AEO-Librarian/1.0"},
        ) as client:
            # First pass: get main content pages
            for path in content_paths:
                url = f"{base_url}{path}"
                if url in visited:
                    continue

                try:
                    response = await client.get(url)
                    if response.status_code == 200:
                        visited.add(url)
                        content = self._extract_page_content(response.text, url)
                        if content:
                            content_inventory.append(content)

                        # Find linked content pages
                        links = self._extract_content_links(response.text, base_url)
                        for link in links[:20]:  # Limit per section
                            if link not in visited:
                                try:
                                    link_response = await client.get(link)
                                    if link_response.status_code == 200:
                                        visited.add(link)
                                        link_content = self._extract_page_content(
                                            link_response.text,
                                            link,
                                        )
                                        if link_content:
                                            content_inventory.append(link_content)
                                except Exception:
                                    pass

                except Exception as e:
                    self._log.debug("crawl_path_failed", path=path, error=str(e))

        self._log.info("content_crawled", pages=len(content_inventory))
        return content_inventory

    def _extract_page_content(self, html: str, url: str) -> dict | None:
        """Extract content metadata from a page."""
        soup = BeautifulSoup(html, "lxml")

        # Get title
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # Get meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        description = meta_desc.get("content", "") if meta_desc else ""

        # Determine content type from URL and structure
        content_type = self._determine_content_type(url, soup)

        # Check for schema markup
        has_schema = bool(soup.find("script", type="application/ld+json"))

        # Get main content
        main_content = ""
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        article = soup.find("article") or soup.find("main") or soup.find("body")
        if article:
            main_content = article.get_text(separator="\n", strip=True)[:5000]

        if not main_content or len(main_content) < 100:
            return None

        # Extract headings
        headings = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3"])]

        return {
            "url": url,
            "title": title,
            "description": description,
            "content_type": content_type,
            "main_content": main_content,
            "headings": headings[:10],
            "has_schema": has_schema,
            "word_count": len(main_content.split()),
        }

    def _determine_content_type(self, url: str, soup: BeautifulSoup) -> str:
        """Determine the type of content."""
        url_lower = url.lower()

        if "/blog" in url_lower or "/post" in url_lower:
            return "blog"
        elif "/guide" in url_lower or "/how-to" in url_lower:
            return "guide"
        elif "/doc" in url_lower or "/help" in url_lower:
            return "documentation"
        elif "/case-stud" in url_lower or "/customer" in url_lower:
            return "case_study"
        elif "/comparison" in url_lower or "/vs" in url_lower:
            return "comparison"
        elif "/product" in url_lower or "/feature" in url_lower:
            return "product_page"
        elif "/pricing" in url_lower:
            return "pricing"
        elif "/about" in url_lower or "/team" in url_lower:
            return "about"
        elif "/faq" in url_lower:
            return "faq"
        else:
            return "page"

    def _extract_content_links(self, html: str, base_url: str) -> list[str]:
        """Extract links to other content pages."""
        soup = BeautifulSoup(html, "lxml")
        links = []

        content_patterns = [
            "/blog/", "/guides/", "/resources/", "/docs/",
            "/help/", "/learn/", "/article/", "/post/",
        ]

        for a in soup.find_all("a", href=True):
            href = a["href"]

            # Make absolute URL
            if href.startswith("/"):
                href = urljoin(base_url, href)
            elif not href.startswith("http"):
                continue

            # Check if it's on the same domain
            if urlparse(href).netloc != urlparse(base_url).netloc:
                continue

            # Check if it's a content page
            if any(pattern in href.lower() for pattern in content_patterns):
                links.append(href)

        return list(set(links))

    async def _analyze_citability(
        self,
        content_inventory: list[dict],
        company_name: str,
    ) -> list[CitableContent]:
        """Analyze each content piece for AI citability."""
        self._log.info("analyzing_citability", content_count=len(content_inventory))

        citable_content = []

        for content in content_inventory:
            signals = self._assess_citability_signals(content)
            score = signals.calculate_score() / 100  # Normalize to 0-1

            # Use LLM to extract topics and improvement opportunities
            analysis = await self._analyze_content_piece(content, company_name)

            citable_content.append(
                CitableContent(
                    url=content["url"],
                    title=content["title"],
                    content_type=content["content_type"],
                    topics_covered=analysis.get("topics", []),
                    citability_score=score,
                    citability_factors=self._get_citability_factors(signals),
                    improvement_opportunities=analysis.get("improvements", []),
                    actual_citations_detected=0,  # Would need external API
                )
            )

        # Sort by citability score
        citable_content.sort(key=lambda x: x.citability_score, reverse=True)

        return citable_content

    def _assess_citability_signals(self, content: dict) -> CitabilitySignals:
        """Assess citability signals for a content piece."""
        main_content = content.get("main_content", "")
        headings = content.get("headings", [])

        return CitabilitySignals(
            clear_hierarchy=len(headings) >= 3,
            answerable_sections=any(
                h.endswith("?") or h.startswith("How") or h.startswith("What")
                for h in headings
            ),
            lead_sentences_extractable=self._check_lead_sentences(main_content),
            has_citations=self._check_for_citations(main_content),
            has_credentials=self._check_for_credentials(main_content),
            has_data=self._check_for_data(main_content),
            has_freshness=True,  # Would check publish date
            specific_claims=self._check_specific_claims(main_content),
            concrete_examples=self._check_examples(main_content),
            actionable_content=self._check_actionable(main_content),
            has_schema_markup=content.get("has_schema", False),
            mobile_friendly=True,  # Would need actual check
            fast_loading=True,  # Would need actual check
        )

    def _check_lead_sentences(self, content: str) -> bool:
        """Check if content has extractable lead sentences."""
        paragraphs = content.split("\n\n")
        for p in paragraphs[:5]:
            sentences = p.split(". ")
            if sentences and len(sentences[0]) < 200:
                return True
        return False

    def _check_for_citations(self, content: str) -> bool:
        """Check if content contains citations."""
        citation_patterns = [
            "according to", "research shows", "study found",
            "data from", "source:", "[1]", "[2]",
        ]
        content_lower = content.lower()
        return any(pattern in content_lower for pattern in citation_patterns)

    def _check_for_credentials(self, content: str) -> bool:
        """Check if content mentions credentials."""
        credential_patterns = [
            "certified", "expert", "years of experience",
            "PhD", "MBA", "founded", "award",
        ]
        content_lower = content.lower()
        return any(pattern in content_lower for pattern in credential_patterns)

    def _check_for_data(self, content: str) -> bool:
        """Check if content contains data/statistics."""
        import re
        # Look for percentages, numbers with units
        return bool(re.search(r'\d+%|\d+\s*(users|customers|companies|percent)', content))

    def _check_specific_claims(self, content: str) -> bool:
        """Check for specific, citable claims."""
        import re
        # Look for specific numbers or definitive statements
        return bool(re.search(r'\d+\s*(x|times|percent|%)|increases?|decreases?|improves?', content.lower()))

    def _check_examples(self, content: str) -> bool:
        """Check for concrete examples."""
        example_patterns = ["for example", "such as", "like", "including"]
        content_lower = content.lower()
        return any(pattern in content_lower for pattern in example_patterns)

    def _check_actionable(self, content: str) -> bool:
        """Check for actionable content."""
        action_patterns = ["step", "how to", "guide", "tips", "ways to"]
        content_lower = content.lower()
        return any(pattern in content_lower for pattern in action_patterns)

    def _get_citability_factors(self, signals: CitabilitySignals) -> list[str]:
        """Get list of positive citability factors."""
        factors = []
        if signals.clear_hierarchy:
            factors.append("Clear content hierarchy")
        if signals.has_citations:
            factors.append("Contains citations/sources")
        if signals.has_data:
            factors.append("Includes data/statistics")
        if signals.specific_claims:
            factors.append("Specific, verifiable claims")
        if signals.has_schema_markup:
            factors.append("Schema markup implemented")
        if signals.actionable_content:
            factors.append("Actionable, practical content")
        return factors

    async def _analyze_content_piece(
        self,
        content: dict,
        company_name: str,
    ) -> dict:
        """Use LLM to analyze a content piece."""
        task_context = """Analyze this content for AEO optimization.
Focus on what topics it covers and how it could be improved for AI citation."""

        prompt = f"""Analyze this content from {company_name}:

Title: {content['title']}
Type: {content['content_type']}
Content preview: {content['main_content'][:2000]}

Respond with JSON:
{{
    "topics": ["List of topics this content covers"],
    "improvements": ["Specific improvements to make this more citable by AI"]
}}

Respond ONLY with the JSON object."""

        try:
            response = self._call_llm(prompt, task_context, max_tokens=1024)

            import json
            import re

            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                return json.loads(json_match.group())

        except Exception as e:
            self._log.warning("content_analysis_failed", error=str(e))

        return {"topics": [], "improvements": []}

    async def _find_external_authority(
        self,
        company_name: str,
        domain: str,
    ) -> list[AuthoritySource]:
        """Find external sources of authority for the company."""
        self._log.info("finding_external_authority", company=company_name)

        authority_sources = []

        # Check common authority platforms
        platforms = [
            ("Wikipedia", f"https://en.wikipedia.org/wiki/{company_name.replace(' ', '_')}"),
            ("Crunchbase", f"https://www.crunchbase.com/organization/{company_name.lower().replace(' ', '-')}"),
            ("G2", f"https://www.g2.com/products/{company_name.lower().replace(' ', '-')}/reviews"),
        ]

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            for platform, url in platforms:
                try:
                    response = await client.get(url)
                    if response.status_code == 200:
                        authority_sources.append(
                            AuthoritySource(
                                source_type=platform.lower(),
                                url=url,
                                authority_level="high" if platform == "Wikipedia" else "medium",
                                what_it_says_about_client=f"Presence on {platform}",
                                opportunity_to_improve=f"Enhance {platform} presence",
                            )
                        )
                except Exception:
                    pass

        return authority_sources

    async def _identify_content_gaps(
        self,
        existing_content: list[CitableContent],
        topics_of_authority: list[str],
        target_queries: list[str],
    ) -> list[ContentGap]:
        """Identify gaps in content coverage."""
        gaps = []

        # Get topics already covered
        covered_topics = set()
        for content in existing_content:
            covered_topics.update(t.lower() for t in content.topics_covered)

        # Find missing authority topics
        for topic in topics_of_authority:
            if topic.lower() not in covered_topics:
                gaps.append(
                    ContentGap(
                        topic=topic,
                        why_needed=f"Authority topic '{topic}' not covered in existing content",
                        queries_this_would_answer=[f"What is {topic}?", f"Best {topic} practices"],
                        competitor_content_exists=True,  # Would need actual check
                        recommended_content_type="guide",
                        priority=ContentPriority.HIGH,
                        effort_to_create="medium",
                    )
                )

        # Find content types we're missing
        content_types = set(c.content_type for c in existing_content)
        important_types = {"comparison", "faq", "guide", "case_study"}

        for content_type in important_types - content_types:
            gaps.append(
                ContentGap(
                    topic=f"{content_type} content",
                    why_needed=f"No {content_type} content found - high-value for AI citation",
                    queries_this_would_answer=[],
                    competitor_content_exists=True,
                    recommended_content_type=content_type,
                    priority=ContentPriority.MEDIUM,
                    effort_to_create="medium",
                )
            )

        return gaps

    def _identify_citation_opportunities(
        self,
        company_name: str,
        topics_of_authority: list[str],
        existing_authority: list[AuthoritySource],
    ) -> list[CitationOpportunity]:
        """Identify opportunities to get cited on external platforms."""
        opportunities = []

        # Check for missing platform presences
        existing_platforms = set(a.source_type for a in existing_authority)

        important_platforms = [
            ("wikipedia", "Highest authority for AI citations"),
            ("quora", "Q&A platform AI frequently cites"),
            ("reddit", "Community discussions AI references"),
            ("industry_publications", "Industry-specific authority"),
        ]

        for platform, value in important_platforms:
            if platform not in existing_platforms:
                opportunities.append(
                    CitationOpportunity(
                        platform=platform,
                        topic=topics_of_authority[0] if topics_of_authority else company_name,
                        why_valuable=value,
                        current_status="not present",
                        action_required=f"Build presence on {platform}",
                    )
                )

        return opportunities
