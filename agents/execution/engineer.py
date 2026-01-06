"""
The Engineer - Schema & Structured Data Specialist

"Structured data is the language machines speak. AI engines can read content,
but structured data tells them what it means. Without schema markup, you're asking
AI to guess. I don't leave citation to chance."
"""

from datetime import datetime
from typing import Any

import structlog

from agents.base import Agent, AgentPersonality

logger = structlog.get_logger()


class SchemaMarkup:
    """A schema.org markup recommendation."""

    def __init__(
        self,
        schema_type: str,
        properties: dict,
        json_ld: str,
        purpose: str,
        expected_impact: str,
    ):
        self.schema_type = schema_type
        self.properties = properties
        self.json_ld = json_ld
        self.purpose = purpose
        self.expected_impact = expected_impact

    def to_dict(self) -> dict:
        return {
            "schema_type": self.schema_type,
            "properties": self.properties,
            "json_ld": self.json_ld,
            "purpose": self.purpose,
            "expected_impact": self.expected_impact,
        }


class SchemaAuditResult:
    """Results of schema markup audit."""

    def __init__(
        self,
        url: str,
        existing_schemas: list[dict],
        missing_schemas: list[str],
        invalid_schemas: list[dict],
        recommendations: list[SchemaMarkup],
        priority_additions: list[dict],
        validation_errors: list[str],
        coverage_score: float,
    ):
        self.url = url
        self.existing_schemas = existing_schemas
        self.missing_schemas = missing_schemas
        self.invalid_schemas = invalid_schemas
        self.recommendations = recommendations
        self.priority_additions = priority_additions
        self.validation_errors = validation_errors
        self.coverage_score = coverage_score
        self.created_at = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "existing_schemas": self.existing_schemas,
            "missing_schemas": self.missing_schemas,
            "invalid_schemas": self.invalid_schemas,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "priority_additions": self.priority_additions,
            "validation_errors": self.validation_errors,
            "coverage_score": self.coverage_score,
            "created_at": self.created_at.isoformat(),
        }


class SchemaImplementation:
    """Complete schema implementation for a site."""

    def __init__(
        self,
        domain: str,
        page_schemas: dict[str, list[SchemaMarkup]],  # url -> schemas
        organization_schema: dict,
        site_navigation_schema: dict,
        implementation_guide: list[dict],
        estimated_improvement: float,
    ):
        self.domain = domain
        self.page_schemas = page_schemas
        self.organization_schema = organization_schema
        self.site_navigation_schema = site_navigation_schema
        self.implementation_guide = implementation_guide
        self.estimated_improvement = estimated_improvement
        self.created_at = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "page_schemas": {
                url: [s.to_dict() for s in schemas]
                for url, schemas in self.page_schemas.items()
            },
            "organization_schema": self.organization_schema,
            "site_navigation_schema": self.site_navigation_schema,
            "implementation_guide": self.implementation_guide,
            "estimated_improvement": self.estimated_improvement,
            "created_at": self.created_at.isoformat(),
        }


class EngineerAgent(Agent):
    """
    Schema & Structured Data Specialist.

    Creates and optimizes structured data markup for AI understanding.
    """

    # Schema types most relevant for AEO
    AEO_SCHEMA_TYPES = {
        "Article": "For blog posts, news articles, and editorial content",
        "HowTo": "For step-by-step guides and tutorials",
        "FAQ": "For frequently asked questions",
        "Product": "For product pages",
        "Review": "For reviews and ratings",
        "Organization": "For company/brand information",
        "Person": "For author and expert profiles",
        "WebPage": "For general page metadata",
        "BreadcrumbList": "For navigation hierarchy",
        "VideoObject": "For video content",
        "ImageObject": "For important images",
        "SoftwareApplication": "For software/app pages",
        "Course": "For educational content",
        "Event": "For events and webinars",
        "LocalBusiness": "For local business information",
    }

    @property
    def personality(self) -> AgentPersonality:
        return AgentPersonality(
            name="The Engineer",
            title="Schema & Structured Data Specialist",
            identity="""Structured data is the language machines speak. AI engines can read
content, but structured data tells them what it means. Without schema markup, you're
asking AI to guess. I don't leave citation to chance.""",
            personality_traits=[
                "Precise—schema markup must be exactly right",
                "Comprehensive—covers all relevant entity types",
                "Standards-focused—follows schema.org specifications",
                "Forward-thinking—anticipates AI parsing needs",
            ],
            core_mission="""Create and optimize structured data markup for maximum AI
understanding and citation potential.""",
            thinking_style="""When I look at a page, I see entities and relationships.
That article has an author (Person), it's about a topic (Thing), it was published
by an organization (Organization), and it answers questions (FAQ).

Each of these entities deserves proper markup. The more explicitly I define these
relationships in structured data, the better AI engines understand and cite the content.
It's not about gaming algorithms—it's about being clear about what things are.""",
        )

    async def run(
        self,
        content_type: str,
        content: dict,
        url: str,
        additional_context: dict | None = None,
    ) -> list[SchemaMarkup]:
        """
        Generate schema markup for content.

        Args:
            content_type: Type of content (article, product, faq, etc.)
            content: Content details
            url: URL of the content
            additional_context: Extra context for schema generation

        Returns:
            List of SchemaMarkup recommendations
        """
        self._log_task_start("generate_schema", content_type=content_type)

        schemas = await self._generate_schemas(
            content_type,
            content,
            url,
            additional_context or {},
        )

        self._log_task_complete(
            "generate_schema",
            schemas_generated=len(schemas),
        )

        return schemas

    async def audit_schemas(
        self,
        url: str,
        existing_markup: str | None = None,
        page_content: str | None = None,
    ) -> SchemaAuditResult:
        """
        Audit existing schema markup on a page.

        Args:
            url: URL to audit
            existing_markup: Existing JSON-LD markup if available
            page_content: Page content for context

        Returns:
            SchemaAuditResult with findings and recommendations
        """
        self._log_task_start("audit_schemas", url=url)

        result = await self._audit_page_schemas(url, existing_markup, page_content)

        self._log_task_complete(
            "audit_schemas",
            existing=len(result.existing_schemas),
            missing=len(result.missing_schemas),
            recommendations=len(result.recommendations),
        )

        return result

    async def _generate_schemas(
        self,
        content_type: str,
        content: dict,
        url: str,
        context: dict,
    ) -> list[SchemaMarkup]:
        """Generate schemas using LLM."""

        task_context = """You are The Engineer generating schema.org structured data.

SCHEMA PRINCIPLES:
1. Be comprehensive - Include all relevant properties
2. Be accurate - Only include data that exists
3. Be specific - Use most specific schema type available
4. Nest properly - Connect related entities
5. Validate - Ensure all required properties are present

PRIORITY SCHEMA TYPES FOR AEO:
- Article/BlogPosting - For content pieces
- HowTo - For tutorials with steps
- FAQPage - For Q&A content
- Organization - For company info
- Person - For authors/experts
- Product - For product pages
- Review - For reviews

Generate valid JSON-LD that passes Google's structured data testing tool."""

        content_str = str(content)[:3000]

        prompt = f"""Generate schema.org markup for this content:

CONTENT TYPE: {content_type}
URL: {url}
CONTENT DETAILS:
{content_str}

ADDITIONAL CONTEXT:
{str(context)[:1000]}

Generate appropriate schema markup as JSON:
{{
    "schemas": [
        {{
            "schema_type": "Article or HowTo or FAQPage etc",
            "purpose": "What this schema communicates to AI",
            "expected_impact": "How this helps with AI citation",
            "json_ld": {{
                "@context": "https://schema.org",
                "@type": "SchemaType",
                ...complete valid JSON-LD...
            }}
        }}
    ]
}}

REQUIREMENTS:
1. Include primary schema for the content type
2. Include author/organization schema if applicable
3. Include BreadcrumbList for navigation context
4. All JSON-LD must be valid and complete
5. Use appropriate nested entities

Respond ONLY with the JSON object."""

        try:
            response = self._call_llm(prompt, task_context, max_tokens=4096)

            import json
            import re

            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())

                schemas = []
                for s in data.get("schemas", []):
                    json_ld = s.get("json_ld", {})
                    schemas.append(
                        SchemaMarkup(
                            schema_type=s.get("schema_type", json_ld.get("@type", "")),
                            properties=json_ld,
                            json_ld=json.dumps(json_ld, indent=2),
                            purpose=s.get("purpose", ""),
                            expected_impact=s.get("expected_impact", ""),
                        )
                    )

                return schemas

        except Exception as e:
            self._log.error("schema_generation_failed", error=str(e))

        return []

    async def _audit_page_schemas(
        self,
        url: str,
        existing_markup: str | None,
        page_content: str | None,
    ) -> SchemaAuditResult:
        """Audit existing schemas on a page."""

        task_context = """You are The Engineer auditing schema.org structured data.

AUDIT CRITERIA:
1. Completeness - Are required properties present?
2. Accuracy - Do values match page content?
3. Validity - Is the JSON-LD valid?
4. Coverage - Are all relevant entities marked up?
5. Best practices - Following Google's guidelines?

COMMON ISSUES:
- Missing required properties
- Invalid property values
- Missing author/organization info
- No breadcrumb navigation
- Incorrect date formats
- Missing main entity of page"""

        markup_text = existing_markup[:3000] if existing_markup else "No existing markup found"
        content_text = page_content[:2000] if page_content else "Content not provided"

        prompt = f"""Audit the schema markup for this page:

URL: {url}

EXISTING MARKUP:
{markup_text}

PAGE CONTENT SAMPLE:
{content_text}

Provide audit results as JSON:
{{
    "existing_schemas": [
        {{
            "type": "Schema type found",
            "valid": true/false,
            "completeness": 0-100,
            "issues": ["list of issues"]
        }}
    ],
    "missing_schemas": ["List of schema types that should be added"],
    "invalid_schemas": [
        {{
            "type": "Schema type",
            "errors": ["validation errors"]
        }}
    ],
    "recommendations": [
        {{
            "schema_type": "Type to add",
            "purpose": "Why this helps",
            "expected_impact": "Impact on AI visibility",
            "json_ld": {{complete JSON-LD object}}
        }}
    ],
    "priority_additions": [
        {{
            "priority": 1,
            "schema_type": "Type",
            "reason": "Why this is priority"
        }}
    ],
    "validation_errors": ["List of validation errors found"],
    "coverage_score": 0-100
}}

Be specific about what's missing and why it matters for AI citation.

Respond ONLY with the JSON object."""

        try:
            response = self._call_llm(prompt, task_context, max_tokens=4096)

            import json
            import re

            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())

                recommendations = []
                for r in data.get("recommendations", []):
                    json_ld = r.get("json_ld", {})
                    recommendations.append(
                        SchemaMarkup(
                            schema_type=r.get("schema_type", ""),
                            properties=json_ld,
                            json_ld=json.dumps(json_ld, indent=2) if json_ld else "",
                            purpose=r.get("purpose", ""),
                            expected_impact=r.get("expected_impact", ""),
                        )
                    )

                return SchemaAuditResult(
                    url=url,
                    existing_schemas=data.get("existing_schemas", []),
                    missing_schemas=data.get("missing_schemas", []),
                    invalid_schemas=data.get("invalid_schemas", []),
                    recommendations=recommendations,
                    priority_additions=data.get("priority_additions", []),
                    validation_errors=data.get("validation_errors", []),
                    coverage_score=data.get("coverage_score", 0) / 100,
                )

        except Exception as e:
            self._log.error("schema_audit_failed", error=str(e))

        return SchemaAuditResult(
            url=url,
            existing_schemas=[],
            missing_schemas=[],
            invalid_schemas=[],
            recommendations=[],
            priority_additions=[],
            validation_errors=["Audit failed"],
            coverage_score=0,
        )

    def generate_organization_schema(
        self,
        name: str,
        url: str,
        logo_url: str | None = None,
        description: str | None = None,
        social_profiles: list[str] | None = None,
        contact_info: dict | None = None,
    ) -> dict:
        """
        Generate Organization schema markup.

        Args:
            name: Organization name
            url: Organization website URL
            logo_url: URL to organization logo
            description: Organization description
            social_profiles: List of social media profile URLs
            contact_info: Contact information dict

        Returns:
            Organization JSON-LD schema
        """
        schema = {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": name,
            "url": url,
        }

        if logo_url:
            schema["logo"] = logo_url

        if description:
            schema["description"] = description

        if social_profiles:
            schema["sameAs"] = social_profiles

        if contact_info:
            contact_point = {
                "@type": "ContactPoint",
            }
            if "email" in contact_info:
                contact_point["email"] = contact_info["email"]
            if "phone" in contact_info:
                contact_point["telephone"] = contact_info["phone"]
            if "type" in contact_info:
                contact_point["contactType"] = contact_info["type"]
            schema["contactPoint"] = contact_point

        return schema

    def generate_article_schema(
        self,
        headline: str,
        description: str,
        url: str,
        author_name: str,
        publisher_name: str,
        date_published: str,
        date_modified: str | None = None,
        image_url: str | None = None,
        word_count: int | None = None,
    ) -> dict:
        """
        Generate Article schema markup.

        Args:
            headline: Article headline
            description: Article description
            url: Article URL
            author_name: Author name
            publisher_name: Publisher name
            date_published: ISO date string
            date_modified: ISO date string (optional)
            image_url: Featured image URL
            word_count: Article word count

        Returns:
            Article JSON-LD schema
        """
        schema = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": headline,
            "description": description,
            "url": url,
            "author": {
                "@type": "Person",
                "name": author_name,
            },
            "publisher": {
                "@type": "Organization",
                "name": publisher_name,
            },
            "datePublished": date_published,
        }

        if date_modified:
            schema["dateModified"] = date_modified

        if image_url:
            schema["image"] = image_url

        if word_count:
            schema["wordCount"] = word_count

        return schema

    def generate_howto_schema(
        self,
        name: str,
        description: str,
        steps: list[dict],  # Each step has name, text, optional image
        total_time: str | None = None,  # ISO 8601 duration
        tools: list[str] | None = None,
        supplies: list[str] | None = None,
    ) -> dict:
        """
        Generate HowTo schema markup.

        Args:
            name: HowTo name/title
            description: HowTo description
            steps: List of step dicts with name and text
            total_time: Total time in ISO 8601 duration format
            tools: List of tools needed
            supplies: List of supplies needed

        Returns:
            HowTo JSON-LD schema
        """
        schema = {
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": name,
            "description": description,
            "step": [
                {
                    "@type": "HowToStep",
                    "position": i + 1,
                    "name": step.get("name", f"Step {i + 1}"),
                    "text": step.get("text", ""),
                    **({"image": step["image"]} if step.get("image") else {}),
                }
                for i, step in enumerate(steps)
            ],
        }

        if total_time:
            schema["totalTime"] = total_time

        if tools:
            schema["tool"] = [
                {"@type": "HowToTool", "name": tool}
                for tool in tools
            ]

        if supplies:
            schema["supply"] = [
                {"@type": "HowToSupply", "name": supply}
                for supply in supplies
            ]

        return schema

    def generate_faq_schema(
        self,
        questions: list[dict],  # Each has question and answer
    ) -> dict:
        """
        Generate FAQPage schema markup.

        Args:
            questions: List of dicts with question and answer keys

        Returns:
            FAQPage JSON-LD schema
        """
        return {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": q.get("question", ""),
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": q.get("answer", ""),
                    },
                }
                for q in questions
            ],
        }

    def generate_breadcrumb_schema(
        self,
        items: list[dict],  # Each has name and url
    ) -> dict:
        """
        Generate BreadcrumbList schema markup.

        Args:
            items: List of breadcrumb items with name and url

        Returns:
            BreadcrumbList JSON-LD schema
        """
        return {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": i + 1,
                    "name": item.get("name", ""),
                    "item": item.get("url", ""),
                }
                for i, item in enumerate(items)
            ],
        }
