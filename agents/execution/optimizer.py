"""
The Optimizer - Content Enhancement Specialist

"Most existing content is invisible to AI. My job is to take what exists and transform
it into something AI engines will actually cite. Same core information, restructured
for machines. It's renovation, not demolition."
"""

from datetime import datetime
from typing import Any

import structlog

from agents.base import Agent, AgentPersonality
from knowledge.schemas import CitabilitySignals

logger = structlog.get_logger()


class ContentChange:
    """A single change to optimize content."""

    def __init__(
        self,
        section: str,
        change_type: str,
        original: str,
        optimized: str,
        rationale: str,
        expected_impact: str,
    ):
        self.section = section
        self.change_type = change_type
        self.original = original
        self.optimized = optimized
        self.rationale = rationale
        self.expected_impact = expected_impact

    def to_dict(self) -> dict:
        return {
            "section": self.section,
            "change_type": self.change_type,
            "original": self.original,
            "optimized": self.optimized,
            "rationale": self.rationale,
            "expected_impact": self.expected_impact,
        }


class ContentOptimization:
    """Complete optimization result for a content piece."""

    def __init__(
        self,
        original_url: str,
        original_title: str,
        original_citability_score: float,
        changes: list[ContentChange],
        new_citability_score: float,
        improvement_percentage: float,
        schema_markup_added: dict | None,
        optimized_content: str,
        optimization_summary: str,
    ):
        self.original_url = original_url
        self.original_title = original_title
        self.original_citability_score = original_citability_score
        self.changes = changes
        self.new_citability_score = new_citability_score
        self.improvement_percentage = improvement_percentage
        self.schema_markup_added = schema_markup_added
        self.optimized_content = optimized_content
        self.optimization_summary = optimization_summary
        self.created_at = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "original_url": self.original_url,
            "original_title": self.original_title,
            "original_citability_score": self.original_citability_score,
            "changes": [c.to_dict() for c in self.changes],
            "new_citability_score": self.new_citability_score,
            "improvement_percentage": self.improvement_percentage,
            "schema_markup_added": self.schema_markup_added,
            "optimized_content": self.optimized_content,
            "optimization_summary": self.optimization_summary,
            "created_at": self.created_at.isoformat(),
        }


class OptimizerAgent(Agent):
    """
    Content Enhancement Specialist.

    Optimizes existing content for AI citation without starting from scratch.
    """

    @property
    def personality(self) -> AgentPersonality:
        return AgentPersonality(
            name="The Optimizer",
            title="Content Enhancement Specialist",
            identity="""Most existing content is invisible to AI. My job is to take what
exists and transform it into something AI engines will actually cite. Same core
information, restructured for machines. It's renovation, not demolition.""",
            personality_traits=[
                "Efficient—maximizes improvement with minimal changes",
                "Analytical—diagnoses exactly what's wrong",
                "Respectful—preserves what works while fixing what doesn't",
                "Measurable—can quantify improvement",
            ],
            core_mission="""Optimize existing content for AI citation without starting
from scratch.""",
            thinking_style="""When I see a piece of content that's not getting cited, I
diagnose why. Is the answer buried in paragraph 5 instead of leading? Are claims
vague instead of specific? Is the structure flat instead of hierarchical? Is it
missing schema markup?

I make targeted changes that dramatically improve citability without rewriting
everything. Sometimes moving one sentence to the top of a section is all it takes.""",
        )

    async def run(
        self,
        content_url: str,
        content_title: str,
        content_text: str,
        original_citability_score: float,
        target_queries: list[str] | None = None,
    ) -> ContentOptimization:
        """
        Optimize existing content for AI citation.

        Args:
            content_url: URL of the original content
            content_title: Title of the content
            content_text: The actual content text
            original_citability_score: Current citability score
            target_queries: Queries this content should answer

        Returns:
            Complete ContentOptimization with changes and optimized content
        """
        self._log_task_start(
            "optimize_content",
            url=content_url,
            original_score=original_citability_score,
        )

        # Analyze and optimize
        optimization = await self._analyze_and_optimize(
            content_url,
            content_title,
            content_text,
            original_citability_score,
            target_queries,
        )

        self._log_task_complete(
            "optimize_content",
            changes=len(optimization.changes),
            improvement=optimization.improvement_percentage,
        )

        return optimization

    async def _analyze_and_optimize(
        self,
        url: str,
        title: str,
        content: str,
        original_score: float,
        target_queries: list[str] | None,
    ) -> ContentOptimization:
        """Analyze content and generate optimizations."""

        task_context = """You are The Optimizer improving content for AI citation.

OPTIMIZATION FRAMEWORK:
1. Structure - Add clear headings, improve hierarchy
2. Lead sentences - Make first sentence of each section citable
3. Specificity - Add numbers, dates, concrete claims
4. Authority - Add citations, credentials, sources
5. Schema - Recommend appropriate structured data
6. Clarity - Remove ambiguity, hedge words, fluff

Make targeted changes that maximize impact. Don't rewrite everything—optimize strategically."""

        queries_text = ""
        if target_queries:
            queries_text = f"\nTARGET QUERIES THIS SHOULD ANSWER:\n" + "\n".join(f"- {q}" for q in target_queries)

        prompt = f"""Analyze and optimize this content for AI citation:

TITLE: {title}
URL: {url}
CURRENT CITABILITY SCORE: {original_score:.0%}
{queries_text}

CONTENT:
{content[:6000]}

Analyze the content and provide optimizations as JSON:
{{
    "diagnosis": "What's preventing this content from being cited by AI",
    "changes": [
        {{
            "section": "Section name or 'Overall'",
            "change_type": "structure/lead_sentence/specificity/authority/clarity",
            "original": "Original text (first 200 chars)",
            "optimized": "Optimized text",
            "rationale": "Why this change improves citability",
            "expected_impact": "high/medium/low"
        }}
    ],
    "schema_markup": {{
        "@context": "https://schema.org",
        "@type": "Article or HowTo or FAQ",
        "headline": "Title",
        "description": "Description"
    }},
    "optimized_content": "Full optimized content with all changes applied",
    "optimization_summary": "2-3 sentence summary of what was improved"
}}

Focus on HIGH IMPACT changes:
- Moving key answers to the beginning of sections
- Adding specific numbers/statistics
- Improving heading structure
- Adding citable excerpts

Respond ONLY with the JSON object."""

        try:
            response = self._call_llm(prompt, task_context, max_tokens=8192)

            import json
            import re

            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())

                changes = [
                    ContentChange(
                        section=c.get("section", ""),
                        change_type=c.get("change_type", ""),
                        original=c.get("original", ""),
                        optimized=c.get("optimized", ""),
                        rationale=c.get("rationale", ""),
                        expected_impact=c.get("expected_impact", "medium"),
                    )
                    for c in data.get("changes", [])
                ]

                # Calculate new citability score
                optimized_content = data.get("optimized_content", content)
                new_score = self._calculate_new_score(
                    original_score,
                    changes,
                    optimized_content,
                )

                improvement = ((new_score - original_score) / original_score * 100) if original_score > 0 else 0

                return ContentOptimization(
                    original_url=url,
                    original_title=title,
                    original_citability_score=original_score,
                    changes=changes,
                    new_citability_score=new_score,
                    improvement_percentage=round(improvement, 1),
                    schema_markup_added=data.get("schema_markup"),
                    optimized_content=optimized_content,
                    optimization_summary=data.get("optimization_summary", ""),
                )

        except Exception as e:
            self._log.error("optimization_failed", error=str(e))

        # Return minimal optimization on failure
        return ContentOptimization(
            original_url=url,
            original_title=title,
            original_citability_score=original_score,
            changes=[],
            new_citability_score=original_score,
            improvement_percentage=0,
            schema_markup_added=None,
            optimized_content=content,
            optimization_summary="Optimization failed - no changes made",
        )

    def _calculate_new_score(
        self,
        original_score: float,
        changes: list[ContentChange],
        optimized_content: str,
    ) -> float:
        """Calculate new citability score after optimizations."""
        # Base improvement from changes
        improvement = 0

        for change in changes:
            if change.expected_impact == "high":
                improvement += 0.08
            elif change.expected_impact == "medium":
                improvement += 0.04
            else:
                improvement += 0.02

        # Cap improvement
        improvement = min(improvement, 0.35)

        # Calculate signals on optimized content
        signals = self._assess_signals(optimized_content)
        signal_score = signals.calculate_score() / 100

        # Blend original improvement with signal assessment
        new_score = min(1.0, original_score + improvement)

        # Weight toward signal assessment
        final_score = (new_score * 0.4) + (signal_score * 0.6)

        return round(final_score, 2)

    def _assess_signals(self, content: str) -> CitabilitySignals:
        """Assess citability signals of content."""
        content_lower = content.lower()

        # Count headings
        heading_count = content.count("##") + content.count("<h2") + content.count("<h3")

        return CitabilitySignals(
            clear_hierarchy=heading_count >= 3,
            answerable_sections=True,  # Assume optimized content is answerable
            lead_sentences_extractable=True,
            has_citations=any(
                word in content_lower
                for word in ["according to", "research", "study", "source"]
            ),
            has_credentials=any(
                word in content_lower
                for word in ["expert", "certified", "experience", "professional"]
            ),
            has_data=any(c.isdigit() for c in content) and "%" in content,
            has_freshness=True,
            specific_claims="%" in content or any(
                word in content_lower for word in ["specifically", "exactly"]
            ),
            concrete_examples=any(
                word in content_lower
                for word in ["for example", "such as", "including"]
            ),
            actionable_content=any(
                word in content_lower
                for word in ["step", "how to", "guide", "tips"]
            ),
            has_schema_markup=False,
            mobile_friendly=True,
            fast_loading=True,
        )

    async def batch_optimize(
        self,
        content_items: list[dict],
    ) -> list[ContentOptimization]:
        """
        Optimize multiple content pieces.

        Args:
            content_items: List of dicts with url, title, content, score

        Returns:
            List of ContentOptimization results
        """
        self._log.info("batch_optimization_started", count=len(content_items))

        results = []
        for item in content_items:
            try:
                optimization = await self.run(
                    content_url=item.get("url", ""),
                    content_title=item.get("title", ""),
                    content_text=item.get("content", ""),
                    original_citability_score=item.get("score", 0.5),
                    target_queries=item.get("target_queries"),
                )
                results.append(optimization)
            except Exception as e:
                self._log.error(
                    "item_optimization_failed",
                    url=item.get("url"),
                    error=str(e),
                )

        self._log.info("batch_optimization_complete", optimized=len(results))
        return results
