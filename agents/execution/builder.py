"""
The Builder - Technical SEO Specialist

"I make sure AI can actually find and access the content. Fastest site in the world
doesn't matter if it's returning 403s to AI crawlers. Best content doesn't matter
if it takes 8 seconds to load. I build the infrastructure that makes visibility possible."
"""

from datetime import datetime
from typing import Any

import structlog

from agents.base import Agent, AgentPersonality

logger = structlog.get_logger()


class TechnicalIssue:
    """A technical SEO issue with priority."""

    def __init__(
        self,
        issue_type: str,
        severity: str,  # critical, high, medium, low
        description: str,
        affected_urls: list[str],
        recommendation: str,
        implementation: str,
        estimated_impact: str,
    ):
        self.issue_type = issue_type
        self.severity = severity
        self.description = description
        self.affected_urls = affected_urls
        self.recommendation = recommendation
        self.implementation = implementation
        self.estimated_impact = estimated_impact

    def to_dict(self) -> dict:
        return {
            "issue_type": self.issue_type,
            "severity": self.severity,
            "description": self.description,
            "affected_urls": self.affected_urls,
            "recommendation": self.recommendation,
            "implementation": self.implementation,
            "estimated_impact": self.estimated_impact,
        }


class CrawlabilityReport:
    """Report on site crawlability for AI engines."""

    def __init__(
        self,
        domain: str,
        robots_txt_analysis: dict,
        ai_crawler_access: dict,  # which AI bots can access
        sitemap_analysis: dict,
        page_speed_metrics: dict,
        mobile_friendly: bool,
        https_enabled: bool,
        issues: list[TechnicalIssue],
        recommendations: list[dict],
        overall_score: float,
    ):
        self.domain = domain
        self.robots_txt_analysis = robots_txt_analysis
        self.ai_crawler_access = ai_crawler_access
        self.sitemap_analysis = sitemap_analysis
        self.page_speed_metrics = page_speed_metrics
        self.mobile_friendly = mobile_friendly
        self.https_enabled = https_enabled
        self.issues = issues
        self.recommendations = recommendations
        self.overall_score = overall_score
        self.created_at = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "robots_txt_analysis": self.robots_txt_analysis,
            "ai_crawler_access": self.ai_crawler_access,
            "sitemap_analysis": self.sitemap_analysis,
            "page_speed_metrics": self.page_speed_metrics,
            "mobile_friendly": self.mobile_friendly,
            "https_enabled": self.https_enabled,
            "issues": [i.to_dict() for i in self.issues],
            "recommendations": self.recommendations,
            "overall_score": self.overall_score,
            "created_at": self.created_at.isoformat(),
        }


class TechnicalAudit:
    """Complete technical SEO audit results."""

    def __init__(
        self,
        domain: str,
        crawlability: CrawlabilityReport,
        indexability_issues: list[dict],
        performance_issues: list[dict],
        structured_data_issues: list[dict],
        priority_fixes: list[dict],
        implementation_plan: list[dict],
        estimated_improvement: float,
    ):
        self.domain = domain
        self.crawlability = crawlability
        self.indexability_issues = indexability_issues
        self.performance_issues = performance_issues
        self.structured_data_issues = structured_data_issues
        self.priority_fixes = priority_fixes
        self.implementation_plan = implementation_plan
        self.estimated_improvement = estimated_improvement
        self.created_at = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "crawlability": self.crawlability.to_dict(),
            "indexability_issues": self.indexability_issues,
            "performance_issues": self.performance_issues,
            "structured_data_issues": self.structured_data_issues,
            "priority_fixes": self.priority_fixes,
            "implementation_plan": self.implementation_plan,
            "estimated_improvement": self.estimated_improvement,
            "created_at": self.created_at.isoformat(),
        }


class BuilderAgent(Agent):
    """
    Technical SEO Specialist.

    Ensures sites are technically optimized for AI crawlers and search engines.
    """

    # Known AI crawler user agents
    AI_CRAWLERS = {
        "GPTBot": "OpenAI's GPTBot for ChatGPT",
        "Google-Extended": "Google's AI training crawler",
        "CCBot": "Common Crawl bot (used by many AI)",
        "anthropic-ai": "Anthropic's web crawler",
        "ClaudeBot": "Anthropic's ClaudeBot",
        "PerplexityBot": "Perplexity AI crawler",
        "cohere-ai": "Cohere AI crawler",
    }

    @property
    def personality(self) -> AgentPersonality:
        return AgentPersonality(
            name="The Builder",
            title="Technical SEO Specialist",
            identity="""I make sure AI can actually find and access the content. Fastest
site in the world doesn't matter if it's returning 403s to AI crawlers. Best content
doesn't matter if it takes 8 seconds to load. I build the infrastructure that makes
visibility possible.""",
            personality_traits=[
                "Detail-oriented—catches issues others miss",
                "Systematic—follows checklists, misses nothing",
                "Practical—focuses on fixes that matter",
                "Performance-obsessed—milliseconds count",
            ],
            core_mission="""Ensure sites are technically optimized for AI crawler access
and indexing.""",
            thinking_style="""When I audit a site, I'm thinking like a bot. Can GPTBot
actually crawl this? Is robots.txt blocking AI engines? How long does this page
take to become interactive? Is the sitemap comprehensive and accurate?

Technical SEO for AI isn't the same as traditional SEO. AI crawlers have different
needs—they need clean, parseable content. They need fast access. They need to be
allowed in the first place.""",
        )

    async def run(
        self,
        domain: str,
        sample_urls: list[str] | None = None,
        robots_txt_content: str | None = None,
        sitemap_content: str | None = None,
    ) -> TechnicalAudit:
        """
        Perform a technical SEO audit.

        Args:
            domain: Domain to audit
            sample_urls: Sample URLs to analyze
            robots_txt_content: robots.txt content if available
            sitemap_content: Sitemap content if available

        Returns:
            Complete TechnicalAudit
        """
        self._log_task_start("technical_audit", domain=domain)

        # Perform audit
        audit = await self._perform_audit(
            domain,
            sample_urls or [],
            robots_txt_content,
            sitemap_content,
        )

        self._log_task_complete(
            "technical_audit",
            issues=len(audit.crawlability.issues),
            score=audit.crawlability.overall_score,
        )

        return audit

    async def _perform_audit(
        self,
        domain: str,
        sample_urls: list[str],
        robots_txt: str | None,
        sitemap: str | None,
    ) -> TechnicalAudit:
        """Perform the technical audit using LLM analysis."""

        task_context = """You are The Builder performing a technical SEO audit for AI visibility.

AUDIT FRAMEWORK:
1. Crawlability - Can AI bots access the site?
2. Robots.txt - Are AI crawlers explicitly allowed or blocked?
3. Sitemap - Is content properly indexed?
4. Performance - Is the site fast enough for crawlers?
5. Structure - Is content parseable and clean?

AI CRAWLER CONTEXT:
- GPTBot (OpenAI) - Used for ChatGPT training and browsing
- Google-Extended - Google's AI/Bard crawler
- CCBot - Common Crawl (used by many AI systems)
- anthropic-ai/ClaudeBot - Anthropic's crawler
- PerplexityBot - Perplexity AI

Focus on issues that specifically affect AI visibility, not just traditional SEO."""

        robots_text = robots_txt if robots_txt else "Not provided"
        sitemap_text = sitemap[:3000] if sitemap else "Not provided"
        urls_text = "\n".join(sample_urls[:10]) if sample_urls else "Not provided"

        prompt = f"""Perform a technical SEO audit for AI visibility:

DOMAIN: {domain}

ROBOTS.TXT:
{robots_text}

SITEMAP (first 3000 chars):
{sitemap_text}

SAMPLE URLS:
{urls_text}

Analyze and provide audit results as JSON:
{{
    "robots_txt_analysis": {{
        "allows_gptbot": true/false,
        "allows_google_extended": true/false,
        "allows_ccbot": true/false,
        "allows_anthropic": true/false,
        "allows_perplexity": true/false,
        "crawl_delay": null or number,
        "blocked_paths": ["list of blocked paths"],
        "notes": "analysis notes"
    }},
    "ai_crawler_access": {{
        "GPTBot": {{"allowed": true/false, "notes": ""}},
        "Google-Extended": {{"allowed": true/false, "notes": ""}},
        "CCBot": {{"allowed": true/false, "notes": ""}},
        "anthropic-ai": {{"allowed": true/false, "notes": ""}},
        "PerplexityBot": {{"allowed": true/false, "notes": ""}}
    }},
    "sitemap_analysis": {{
        "exists": true/false,
        "format_valid": true/false,
        "estimated_urls": number,
        "last_modified_recent": true/false,
        "issues": ["list of issues"]
    }},
    "page_speed_metrics": {{
        "estimated_lcp": "good/needs_improvement/poor",
        "estimated_fid": "good/needs_improvement/poor",
        "estimated_cls": "good/needs_improvement/poor",
        "notes": "performance notes"
    }},
    "mobile_friendly": true/false,
    "https_enabled": true/false,
    "issues": [
        {{
            "issue_type": "crawlability/indexability/performance/structured_data",
            "severity": "critical/high/medium/low",
            "description": "Issue description",
            "affected_urls": ["urls affected"],
            "recommendation": "What to do",
            "implementation": "How to implement",
            "estimated_impact": "Impact on AI visibility"
        }}
    ],
    "indexability_issues": [
        {{"issue": "", "severity": "", "fix": ""}}
    ],
    "performance_issues": [
        {{"issue": "", "severity": "", "fix": ""}}
    ],
    "structured_data_issues": [
        {{"issue": "", "severity": "", "fix": ""}}
    ],
    "priority_fixes": [
        {{
            "priority": 1,
            "fix": "Description",
            "impact": "Expected impact",
            "effort": "low/medium/high"
        }}
    ],
    "implementation_plan": [
        {{
            "phase": 1,
            "name": "Phase name",
            "tasks": ["task1", "task2"],
            "expected_impact": "Impact description"
        }}
    ],
    "overall_score": 0-100,
    "estimated_improvement": 0-100
}}

Be specific about AI crawler access. Many sites unknowingly block AI crawlers.

Respond ONLY with the JSON object."""

        try:
            response = self._call_llm(prompt, task_context, max_tokens=4096)

            import json
            import re

            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())

                issues = [
                    TechnicalIssue(
                        issue_type=i.get("issue_type", ""),
                        severity=i.get("severity", "medium"),
                        description=i.get("description", ""),
                        affected_urls=i.get("affected_urls", []),
                        recommendation=i.get("recommendation", ""),
                        implementation=i.get("implementation", ""),
                        estimated_impact=i.get("estimated_impact", ""),
                    )
                    for i in data.get("issues", [])
                ]

                crawlability = CrawlabilityReport(
                    domain=domain,
                    robots_txt_analysis=data.get("robots_txt_analysis", {}),
                    ai_crawler_access=data.get("ai_crawler_access", {}),
                    sitemap_analysis=data.get("sitemap_analysis", {}),
                    page_speed_metrics=data.get("page_speed_metrics", {}),
                    mobile_friendly=data.get("mobile_friendly", True),
                    https_enabled=data.get("https_enabled", True),
                    issues=issues,
                    recommendations=[
                        {"recommendation": fix.get("fix", ""), "priority": fix.get("priority", 99)}
                        for fix in data.get("priority_fixes", [])
                    ],
                    overall_score=data.get("overall_score", 50) / 100,
                )

                return TechnicalAudit(
                    domain=domain,
                    crawlability=crawlability,
                    indexability_issues=data.get("indexability_issues", []),
                    performance_issues=data.get("performance_issues", []),
                    structured_data_issues=data.get("structured_data_issues", []),
                    priority_fixes=data.get("priority_fixes", []),
                    implementation_plan=data.get("implementation_plan", []),
                    estimated_improvement=data.get("estimated_improvement", 0) / 100,
                )

        except Exception as e:
            self._log.error("audit_failed", error=str(e))

        # Return minimal audit on failure
        return TechnicalAudit(
            domain=domain,
            crawlability=CrawlabilityReport(
                domain=domain,
                robots_txt_analysis={},
                ai_crawler_access={},
                sitemap_analysis={},
                page_speed_metrics={},
                mobile_friendly=True,
                https_enabled=True,
                issues=[],
                recommendations=[],
                overall_score=0.5,
            ),
            indexability_issues=[],
            performance_issues=[],
            structured_data_issues=[],
            priority_fixes=[],
            implementation_plan=[],
            estimated_improvement=0,
        )

    async def generate_robots_txt(
        self,
        domain: str,
        allow_ai_crawlers: bool = True,
        blocked_paths: list[str] | None = None,
    ) -> str:
        """
        Generate an optimized robots.txt file.

        Args:
            domain: Domain for the robots.txt
            allow_ai_crawlers: Whether to allow AI crawlers
            blocked_paths: Paths to block for all crawlers

        Returns:
            robots.txt content
        """
        self._log.info("generating_robots_txt", domain=domain, allow_ai=allow_ai_crawlers)

        lines = [
            "# robots.txt for " + domain,
            "# Generated by AEO Orchestrator",
            "",
            "# Allow all crawlers by default",
            "User-agent: *",
            "Allow: /",
        ]

        # Add blocked paths
        if blocked_paths:
            lines.append("")
            lines.append("# Blocked paths")
            for path in blocked_paths:
                lines.append(f"Disallow: {path}")

        # AI crawler specific rules
        if allow_ai_crawlers:
            lines.extend([
                "",
                "# AI Crawlers - Explicitly allowed for AEO",
                "",
                "# OpenAI GPTBot",
                "User-agent: GPTBot",
                "Allow: /",
                "",
                "# Google AI",
                "User-agent: Google-Extended",
                "Allow: /",
                "",
                "# Anthropic",
                "User-agent: anthropic-ai",
                "Allow: /",
                "User-agent: ClaudeBot",
                "Allow: /",
                "",
                "# Perplexity",
                "User-agent: PerplexityBot",
                "Allow: /",
                "",
                "# Common Crawl",
                "User-agent: CCBot",
                "Allow: /",
            ])
        else:
            lines.extend([
                "",
                "# AI Crawlers - Blocked",
                "User-agent: GPTBot",
                "Disallow: /",
                "",
                "User-agent: Google-Extended",
                "Disallow: /",
                "",
                "User-agent: anthropic-ai",
                "Disallow: /",
                "",
                "User-agent: ClaudeBot",
                "Disallow: /",
                "",
                "User-agent: PerplexityBot",
                "Disallow: /",
                "",
                "User-agent: CCBot",
                "Disallow: /",
            ])

        lines.extend([
            "",
            "# Sitemap",
            f"Sitemap: https://{domain}/sitemap.xml",
        ])

        return "\n".join(lines)

    def analyze_robots_txt(self, content: str) -> dict:
        """
        Analyze robots.txt for AI crawler access.

        Args:
            content: robots.txt content

        Returns:
            Analysis results
        """
        lines = content.lower().split("\n")

        result = {
            "allows_all": True,
            "ai_crawler_status": {},
            "blocked_paths": [],
            "issues": [],
        }

        current_agent = "*"
        for line in lines:
            line = line.strip()

            if line.startswith("user-agent:"):
                current_agent = line.split(":", 1)[1].strip()

            elif line.startswith("disallow:"):
                path = line.split(":", 1)[1].strip()
                if path == "/" and current_agent == "*":
                    result["allows_all"] = False
                    result["issues"].append("Disallows all crawlers by default")

                if path:
                    for crawler in self.AI_CRAWLERS:
                        if crawler.lower() in current_agent or current_agent == "*":
                            if crawler not in result["ai_crawler_status"]:
                                result["ai_crawler_status"][crawler] = {"allowed": True, "blocked_paths": []}
                            if path == "/":
                                result["ai_crawler_status"][crawler]["allowed"] = False
                            else:
                                result["ai_crawler_status"][crawler]["blocked_paths"].append(path)

            elif line.startswith("allow:"):
                path = line.split(":", 1)[1].strip()
                for crawler in self.AI_CRAWLERS:
                    if crawler.lower() in current_agent:
                        if crawler not in result["ai_crawler_status"]:
                            result["ai_crawler_status"][crawler] = {"allowed": True, "blocked_paths": []}
                        if path == "/":
                            result["ai_crawler_status"][crawler]["allowed"] = True

        # Set defaults for crawlers not mentioned
        for crawler in self.AI_CRAWLERS:
            if crawler not in result["ai_crawler_status"]:
                result["ai_crawler_status"][crawler] = {
                    "allowed": result["allows_all"],
                    "blocked_paths": [],
                }

        return result
