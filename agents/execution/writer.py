"""
The Writer - AEO Content Specialist

"I write content that AI wants to cite. Not keyword-stuffed SEO garbage. Not fluffy
thought leadership. Clear, authoritative, factual content structured so AI can parse it,
trust it, and excerpt it. Every sentence I write could end up in a ChatGPT response—
I write accordingly."
"""

from datetime import datetime
from typing import Any

import structlog

from agents.base import Agent, AgentPersonality
from knowledge.schemas import ClientIntelligenceProfile, CitabilitySignals

logger = structlog.get_logger()


class ContentSection:
    """A section of content with AI optimization."""

    def __init__(
        self,
        heading: str,
        content: str,
        citable_excerpt: str,
        key_facts: list[str],
    ):
        self.heading = heading
        self.content = content
        self.citable_excerpt = citable_excerpt
        self.key_facts = key_facts

    def to_dict(self) -> dict:
        return {
            "heading": self.heading,
            "content": self.content,
            "citable_excerpt": self.citable_excerpt,
            "key_facts": self.key_facts,
        }


class GeneratedContent:
    """Complete generated content piece."""

    def __init__(
        self,
        title: str,
        meta_description: str,
        content_type: str,
        target_queries: list[str],
        sections: list[ContentSection],
        schema_markup: dict,
        citability_score: float,
        citability_signals: CitabilitySignals,
        word_count: int,
        quality_assessment: dict,
    ):
        self.title = title
        self.meta_description = meta_description
        self.content_type = content_type
        self.target_queries = target_queries
        self.sections = sections
        self.schema_markup = schema_markup
        self.citability_score = citability_score
        self.citability_signals = citability_signals
        self.word_count = word_count
        self.quality_assessment = quality_assessment
        self.created_at = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "meta_description": self.meta_description,
            "content_type": self.content_type,
            "target_queries": self.target_queries,
            "sections": [s.to_dict() for s in self.sections],
            "schema_markup": self.schema_markup,
            "citability_score": self.citability_score,
            "citability_signals": self.citability_signals.model_dump(),
            "word_count": self.word_count,
            "quality_assessment": self.quality_assessment,
            "created_at": self.created_at.isoformat(),
        }

    def to_markdown(self) -> str:
        """Convert content to markdown format."""
        lines = [f"# {self.title}", ""]

        for section in self.sections:
            lines.append(f"## {section.heading}")
            lines.append("")
            lines.append(section.content)
            lines.append("")

        return "\n".join(lines)

    def to_html(self) -> str:
        """Convert content to HTML format."""
        lines = [f"<h1>{self.title}</h1>"]

        for section in self.sections:
            lines.append(f"<h2>{section.heading}</h2>")
            # Convert paragraphs
            paragraphs = section.content.split("\n\n")
            for p in paragraphs:
                if p.strip():
                    lines.append(f"<p>{p.strip()}</p>")

        return "\n".join(lines)


class WriterAgent(Agent):
    """
    AEO Content Specialist.

    Creates content optimized for AI citation while maintaining quality and brand voice.
    """

    @property
    def personality(self) -> AgentPersonality:
        return AgentPersonality(
            name="The Writer",
            title="AEO Content Specialist",
            identity="""I write content that AI wants to cite. Not keyword-stuffed SEO garbage.
Not fluffy thought leadership. Clear, authoritative, factual content structured so AI
can parse it, trust it, and excerpt it. Every sentence I write could end up in a
ChatGPT response—I write accordingly.""",
            personality_traits=[
                "Clarity-obsessed—no ambiguity, no fluff",
                "Fact-driven—every claim is substantiated",
                "Structure-minded—thinks in outlines and hierarchies",
                "AI-aware—understands what makes content citable",
            ],
            core_mission="""Create content optimized for AI citation while maintaining
quality and brand voice.""",
            thinking_style="""When I write, I'm thinking about how an AI will read this.

Will it be able to extract a clear answer from this paragraph? Is this claim specific
enough to cite? Is the structure clear enough to navigate? Are there concrete examples,
numbers, facts that add authority?

I write in a way that's simultaneously great for humans AND optimized for AI extraction.
That's not a contradiction—both want clarity, authority, and usefulness.""",
        )

    async def run(
        self,
        blueprint: dict,
        client_profile: ClientIntelligenceProfile,
    ) -> GeneratedContent:
        """
        Generate content from a blueprint.

        Args:
            blueprint: ContentBlueprint from The Architect
            client_profile: Client intelligence for brand voice

        Returns:
            Complete GeneratedContent
        """
        self._log_task_start(
            "generate_content",
            title=blueprint.get("title", ""),
            content_type=blueprint.get("content_type", ""),
        )

        # Generate the content using LLM
        content = await self._generate_content(blueprint, client_profile)

        # Generate schema markup
        schema = self._generate_schema_markup(content, blueprint)
        content.schema_markup = schema

        # Assess quality
        quality = self._assess_quality(content, blueprint)
        content.quality_assessment = quality

        self._log_task_complete(
            "generate_content",
            word_count=content.word_count,
            citability_score=content.citability_score,
        )

        return content

    async def _generate_content(
        self,
        blueprint: dict,
        profile: ClientIntelligenceProfile,
    ) -> GeneratedContent:
        """Generate content using LLM."""

        task_context = f"""You are The Writer generating AI-optimized content.

WRITING PRINCIPLES:
1. Lead with the answer - First sentence of each section should be citable
2. Be specific - "increases conversion by 23%" not "improves conversion"
3. Use clear structure - Headers that AI can parse
4. Include citable facts - Statistics, dates, specific claims
5. Add authority signals - Credentials, methodology, sources
6. Write definitively - "X is Y" not "X might be Y in some cases"

BRAND VOICE:
- Tone: {profile.brand_voice.tone}
- Traits: {', '.join(profile.brand_voice.personality_traits[:3])}
- Avoid: {', '.join(profile.brand_voice.things_they_never_say[:3]) if profile.brand_voice.things_they_never_say else 'N/A'}

Every paragraph should contain at least one citable fact or clear statement."""

        sections_spec = blueprint.get("sections", [])
        sections_text = "\n".join(
            f"- {s.get('heading', '')}: {s.get('purpose', '')} (Key points: {', '.join(s.get('key_points', []))})"
            for s in sections_spec
        )

        prompt = f"""Generate content based on this blueprint:

TITLE: {blueprint.get('title', '')}
TYPE: {blueprint.get('content_type', '')}
FORMAT: {blueprint.get('format_type', '')}
TARGET LENGTH: {blueprint.get('target_length', '1500-2000 words')}
TARGET QUERIES: {', '.join(blueprint.get('target_queries', []))}

SECTIONS TO WRITE:
{sections_text}

AI OPTIMIZATION REQUIREMENTS:
{chr(10).join('- ' + r for r in blueprint.get('ai_optimization_requirements', []))}

AUTHORITY SIGNALS NEEDED:
{chr(10).join('- ' + s for s in blueprint.get('authority_signals_needed', []))}

HOW TO BEAT COMPETITORS: {blueprint.get('how_we_beat_it', 'Be more comprehensive and authoritative')}

Generate the COMPLETE content as JSON:
{{
    "title": "Final title",
    "meta_description": "150-160 char meta description",
    "sections": [
        {{
            "heading": "Section heading",
            "content": "Full section content with multiple paragraphs. Each paragraph should be 3-5 sentences. Include specific facts, numbers, and examples.",
            "citable_excerpt": "The single most citable sentence from this section",
            "key_facts": ["Fact 1", "Fact 2"]
        }}
    ]
}}

IMPORTANT:
- Write FULL content, not summaries or placeholders
- Each section should be 200-400 words
- Include specific statistics, examples, and actionable advice
- Lead each section with a clear, citable statement
- Ensure content directly answers the target queries

Respond ONLY with the JSON object."""

        try:
            response = self._call_llm(prompt, task_context, max_tokens=8192)

            import json
            import re

            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())

                sections = [
                    ContentSection(
                        heading=s.get("heading", ""),
                        content=s.get("content", ""),
                        citable_excerpt=s.get("citable_excerpt", ""),
                        key_facts=s.get("key_facts", []),
                    )
                    for s in data.get("sections", [])
                ]

                # Calculate word count
                total_words = sum(
                    len(s.content.split()) for s in sections
                )

                # Assess citability
                signals = self._assess_citability_signals(sections)

                return GeneratedContent(
                    title=data.get("title", blueprint.get("title", "")),
                    meta_description=data.get("meta_description", ""),
                    content_type=blueprint.get("content_type", ""),
                    target_queries=blueprint.get("target_queries", []),
                    sections=sections,
                    schema_markup={},
                    citability_score=signals.calculate_score() / 100,
                    citability_signals=signals,
                    word_count=total_words,
                    quality_assessment={},
                )

        except Exception as e:
            self._log.error("content_generation_failed", error=str(e))

        # Return empty content on failure
        return GeneratedContent(
            title=blueprint.get("title", ""),
            meta_description="",
            content_type=blueprint.get("content_type", ""),
            target_queries=blueprint.get("target_queries", []),
            sections=[],
            schema_markup={},
            citability_score=0,
            citability_signals=CitabilitySignals(),
            word_count=0,
            quality_assessment={"error": "Content generation failed"},
        )

    def _assess_citability_signals(self, sections: list[ContentSection]) -> CitabilitySignals:
        """Assess citability signals from generated content."""
        all_content = " ".join(s.content for s in sections)

        return CitabilitySignals(
            clear_hierarchy=len(sections) >= 3,
            answerable_sections=all(s.citable_excerpt for s in sections),
            lead_sentences_extractable=all(
                len(s.content.split(".")[0]) < 200 for s in sections if s.content
            ),
            has_citations=any(
                word in all_content.lower()
                for word in ["according to", "research", "study", "data shows"]
            ),
            has_credentials=any(
                word in all_content.lower()
                for word in ["expert", "certified", "years", "experience"]
            ),
            has_data=any(
                char.isdigit() and "%" in all_content
                for char in all_content
            ) or any(c.isdigit() for c in all_content),
            has_freshness=True,
            specific_claims=any(
                word in all_content.lower()
                for word in ["specifically", "exactly", "precisely", "%"]
            ),
            concrete_examples=any(
                word in all_content.lower()
                for word in ["for example", "such as", "including", "like"]
            ),
            actionable_content=any(
                word in all_content.lower()
                for word in ["step", "how to", "tips", "guide", "ways"]
            ),
            has_schema_markup=False,  # Will be added separately
            mobile_friendly=True,
            fast_loading=True,
        )

    def _generate_schema_markup(
        self,
        content: GeneratedContent,
        blueprint: dict,
    ) -> dict:
        """Generate appropriate schema markup."""
        schema_type = blueprint.get("schema_markup_type", "Article")

        if schema_type == "HowTo":
            return self._generate_howto_schema(content)
        elif schema_type == "FAQ":
            return self._generate_faq_schema(content)
        elif schema_type == "Article":
            return self._generate_article_schema(content)
        else:
            return self._generate_article_schema(content)

    def _generate_article_schema(self, content: GeneratedContent) -> dict:
        """Generate Article schema markup."""
        return {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": content.title,
            "description": content.meta_description,
            "articleBody": content.to_markdown(),
            "wordCount": content.word_count,
            "datePublished": content.created_at.isoformat(),
            "dateModified": content.created_at.isoformat(),
        }

    def _generate_howto_schema(self, content: GeneratedContent) -> dict:
        """Generate HowTo schema markup."""
        steps = []
        for i, section in enumerate(content.sections):
            steps.append({
                "@type": "HowToStep",
                "position": i + 1,
                "name": section.heading,
                "text": section.content[:500],
            })

        return {
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": content.title,
            "description": content.meta_description,
            "step": steps,
        }

    def _generate_faq_schema(self, content: GeneratedContent) -> dict:
        """Generate FAQ schema markup."""
        questions = []
        for section in content.sections:
            if "?" in section.heading or section.heading.lower().startswith(("what", "how", "why", "when", "where")):
                questions.append({
                    "@type": "Question",
                    "name": section.heading,
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": section.citable_excerpt or section.content[:500],
                    },
                })

        return {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": questions,
        }

    def _assess_quality(
        self,
        content: GeneratedContent,
        blueprint: dict,
    ) -> dict:
        """Assess content quality against acceptance criteria."""
        criteria = blueprint.get("acceptance_criteria", [])
        results = {}

        # Check word count
        target_length = blueprint.get("target_length", "1500-2000 words")
        min_words = 1500
        if "-" in target_length:
            try:
                min_words = int(target_length.split("-")[0].replace(",", "").split()[0])
            except (ValueError, IndexError):
                pass

        results["word_count_met"] = content.word_count >= min_words
        results["actual_word_count"] = content.word_count
        results["target_word_count"] = min_words

        # Check citability score
        results["citability_score"] = content.citability_score
        results["citability_threshold_met"] = content.citability_score >= 0.7

        # Check sections
        expected_sections = len(blueprint.get("sections", []))
        results["sections_complete"] = len(content.sections) >= expected_sections
        results["actual_sections"] = len(content.sections)
        results["expected_sections"] = expected_sections

        # Check for citable excerpts
        results["has_citable_excerpts"] = all(
            s.citable_excerpt for s in content.sections
        )

        # Overall pass/fail
        results["passed"] = all([
            results["word_count_met"],
            results["citability_threshold_met"],
            results["sections_complete"],
            results["has_citable_excerpts"],
        ])

        return results
