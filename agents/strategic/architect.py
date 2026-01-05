"""
The Architect - Content & Campaign Architect

"The Strategist says what to do. I figure out how to do it. Every piece of content,
every campaign, every initiative—I design the blueprint. What exactly will we create?
How will it be structured? What makes it better than what's already out there?
I turn strategy into detailed execution plans."
"""

from datetime import datetime
from typing import Any

import structlog

from agents.base import Agent, AgentPersonality
from knowledge.schemas import (
    ClientIntelligenceProfile,
    ContentGap,
    ContentPriority,
)

logger = structlog.get_logger()


class ContentBlueprint:
    """Detailed blueprint for a content piece."""

    def __init__(
        self,
        title: str,
        content_type: str,
        target_queries: list[str],
        format_type: str,
        target_length: str,
        sections: list[dict],
        ai_optimization_requirements: list[str],
        schema_markup_type: str,
        authority_signals_needed: list[str],
        content_to_beat: list[str],
        how_we_beat_it: str,
        target_platform: str,
        distribution_plan: str,
        acceptance_criteria: list[str],
    ):
        self.title = title
        self.content_type = content_type
        self.target_queries = target_queries
        self.format_type = format_type
        self.target_length = target_length
        self.sections = sections
        self.ai_optimization_requirements = ai_optimization_requirements
        self.schema_markup_type = schema_markup_type
        self.authority_signals_needed = authority_signals_needed
        self.content_to_beat = content_to_beat
        self.how_we_beat_it = how_we_beat_it
        self.target_platform = target_platform
        self.distribution_plan = distribution_plan
        self.acceptance_criteria = acceptance_criteria

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "content_type": self.content_type,
            "target_queries": self.target_queries,
            "format_type": self.format_type,
            "target_length": self.target_length,
            "sections": self.sections,
            "ai_optimization_requirements": self.ai_optimization_requirements,
            "schema_markup_type": self.schema_markup_type,
            "authority_signals_needed": self.authority_signals_needed,
            "content_to_beat": self.content_to_beat,
            "how_we_beat_it": self.how_we_beat_it,
            "target_platform": self.target_platform,
            "distribution_plan": self.distribution_plan,
            "acceptance_criteria": self.acceptance_criteria,
        }


class CitationTarget:
    """Target for citation building."""

    def __init__(
        self,
        platform: str,
        action: str,
        content_needed: str,
    ):
        self.platform = platform
        self.action = action
        self.content_needed = content_needed

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "action": self.action,
            "content_needed": self.content_needed,
        }


class Milestone:
    """Project milestone."""

    def __init__(self, name: str, deliverables: list[str], criteria: str):
        self.name = name
        self.deliverables = deliverables
        self.criteria = criteria

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "deliverables": self.deliverables,
            "criteria": self.criteria,
        }


class Initiative:
    """A strategic initiative with execution plan."""

    def __init__(
        self,
        name: str,
        objective: str,
        content_pieces: list[ContentBlueprint],
        citation_targets: list[CitationTarget],
        timeline: str,
        milestones: list[Milestone],
        success_metrics: list[str],
    ):
        self.name = name
        self.objective = objective
        self.content_pieces = content_pieces
        self.citation_targets = citation_targets
        self.timeline = timeline
        self.milestones = milestones
        self.success_metrics = success_metrics

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "objective": self.objective,
            "content_pieces": [c.to_dict() for c in self.content_pieces],
            "citation_targets": [c.to_dict() for c in self.citation_targets],
            "timeline": self.timeline,
            "milestones": [m.to_dict() for m in self.milestones],
            "success_metrics": self.success_metrics,
        }


class ExecutionPlan:
    """Complete execution plan for strategic priorities."""

    def __init__(
        self,
        strategic_priority_addressed: str,
        initiatives: list[Initiative],
    ):
        self.strategic_priority_addressed = strategic_priority_addressed
        self.initiatives = initiatives
        self.created_at = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "strategic_priority_addressed": self.strategic_priority_addressed,
            "initiatives": [i.to_dict() for i in self.initiatives],
            "created_at": self.created_at.isoformat(),
        }


class ArchitectAgent(Agent):
    """
    Content & Campaign Architect.

    Transforms strategic priorities into detailed execution plans. Designs
    content architectures, campaign structures, and initiatives that will
    achieve strategic goals.
    """

    @property
    def personality(self) -> AgentPersonality:
        return AgentPersonality(
            name="The Architect",
            title="Content & Campaign Architect",
            identity="""The Strategist says what to do. I figure out how to do it. Every
piece of content, every campaign, every initiative—I design the blueprint. What exactly
will we create? How will it be structured? What makes it better than what's already
out there? I turn strategy into detailed execution plans.""",
            personality_traits=[
                "Detail-oriented—nothing is 'figure it out later'",
                "Quality-obsessed—designs for excellence, not just completion",
                "AI-native thinker—understands what makes content citable",
                "Practical—designs things that can actually be built",
            ],
            core_mission="""Transform strategic priorities into detailed execution plans.
Design content architectures, campaign structures, and initiatives that will achieve
strategic goals.""",
            thinking_style="""When the Strategist says "we need content on topic X," I don't
just say "write a blog post." I ask: What format will AI engines prefer for this topic?
What structure makes it most citable? What existing content ranks well and how do we
beat it? What authority signals do we need to include? What specific claims should be
in there that AI can excerpt?

I design content that's engineered for AI citation, not just human readability. Every
section, every heading, every factual claim is intentional.""",
        )

    async def run(
        self,
        strategic_priority: dict,
        client_profile: ClientIntelligenceProfile,
        content_gaps: list[ContentGap] | None = None,
        target_queries: list[str] | None = None,
    ) -> ExecutionPlan:
        """
        Create detailed execution plan for a strategic priority.

        Args:
            strategic_priority: Priority from Strategist
            client_profile: Client intelligence
            content_gaps: Known content gaps
            target_queries: Queries to target

        Returns:
            Complete ExecutionPlan with content blueprints
        """
        self._log_task_start(
            "create_execution_plan",
            priority=strategic_priority.get("priority", ""),
        )

        # Generate initiatives for this priority
        initiatives = await self._design_initiatives(
            strategic_priority,
            client_profile,
            content_gaps,
            target_queries,
        )

        plan = ExecutionPlan(
            strategic_priority_addressed=strategic_priority.get("priority", ""),
            initiatives=initiatives,
        )

        self._log_task_complete(
            "create_execution_plan",
            initiatives=len(initiatives),
            content_pieces=sum(len(i.content_pieces) for i in initiatives),
        )

        return plan

    async def _design_initiatives(
        self,
        priority: dict,
        profile: ClientIntelligenceProfile,
        content_gaps: list[ContentGap] | None,
        target_queries: list[str] | None,
    ) -> list[Initiative]:
        """Design initiatives to address the strategic priority."""

        task_context = """You are The Architect designing detailed execution plans.
Every content piece must be engineered for AI citation. Include specific sections,
headings, and requirements that make content citable."""

        priority_text = priority.get("priority", "")
        rationale = priority.get("rationale", "")

        # Build relevant content gaps
        gaps_text = ""
        if content_gaps:
            gaps_text = "\n".join(
                f"- {g.topic}: {g.why_needed}" for g in content_gaps[:5]
            )

        queries_text = ""
        if target_queries:
            queries_text = "\n".join(f"- {q}" for q in target_queries[:10])

        prompt = f"""Design an execution plan for this strategic priority:

PRIORITY: {priority_text}
RATIONALE: {rationale}

CLIENT CONTEXT:
- Company: {profile.company_essence}
- Category: {profile.category}
- Topics of Authority: {', '.join(profile.topics_of_authority[:5])}
- Brand Voice: {profile.brand_voice.tone}

CONTENT GAPS:
{gaps_text if gaps_text else "No specific gaps identified"}

TARGET QUERIES:
{queries_text if queries_text else "No specific queries provided"}

Design 1-3 initiatives with detailed content blueprints. For each content piece:
1. Specify exact structure (sections with headings)
2. Include AI optimization requirements
3. Specify schema markup type
4. Define acceptance criteria

Respond with JSON:
{{
    "initiatives": [
        {{
            "name": "Initiative name",
            "objective": "What this achieves",
            "content_pieces": [
                {{
                    "title": "Specific content title",
                    "content_type": "guide/comparison/faq/case_study/etc",
                    "target_queries": ["Query 1", "Query 2"],
                    "format_type": "how-to/listicle/comparison/explainer",
                    "target_length": "1500-2000 words",
                    "sections": [
                        {{
                            "heading": "Section heading",
                            "purpose": "What this section achieves",
                            "key_points": ["Point 1", "Point 2"],
                            "citable_facts_needed": ["Specific fact to include"]
                        }}
                    ],
                    "ai_optimization_requirements": [
                        "Lead each section with citable statement",
                        "Include specific statistics"
                    ],
                    "schema_markup_type": "HowTo/FAQ/Article",
                    "authority_signals_needed": ["Credentials", "Sources"],
                    "content_to_beat": ["URL of competitor content"],
                    "how_we_beat_it": "What makes ours better",
                    "target_platform": "website/blog/etc",
                    "distribution_plan": "How to distribute",
                    "acceptance_criteria": [
                        "Citability score > 70",
                        "All sections complete"
                    ]
                }}
            ],
            "citation_targets": [
                {{
                    "platform": "Platform name",
                    "action": "What to do",
                    "content_needed": "What content to create"
                }}
            ],
            "timeline": "Estimated duration",
            "milestones": [
                {{
                    "name": "Milestone name",
                    "deliverables": ["Deliverable 1"],
                    "criteria": "Completion criteria"
                }}
            ],
            "success_metrics": ["Metric 1", "Metric 2"]
        }}
    ]
}}

Be specific and detailed. Every content piece should be ready for a writer to execute.
Respond ONLY with the JSON object."""

        try:
            response = self._call_llm(prompt, task_context, max_tokens=6144)

            import json
            import re

            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())

                initiatives = []
                for init_data in data.get("initiatives", []):
                    # Parse content pieces
                    content_pieces = [
                        ContentBlueprint(**cp)
                        for cp in init_data.get("content_pieces", [])
                    ]

                    # Parse citation targets
                    citation_targets = [
                        CitationTarget(**ct)
                        for ct in init_data.get("citation_targets", [])
                    ]

                    # Parse milestones
                    milestones = [
                        Milestone(**m) for m in init_data.get("milestones", [])
                    ]

                    initiatives.append(
                        Initiative(
                            name=init_data.get("name", ""),
                            objective=init_data.get("objective", ""),
                            content_pieces=content_pieces,
                            citation_targets=citation_targets,
                            timeline=init_data.get("timeline", ""),
                            milestones=milestones,
                            success_metrics=init_data.get("success_metrics", []),
                        )
                    )

                return initiatives

        except Exception as e:
            self._log.error("initiative_design_failed", error=str(e))

        # Fallback to basic initiative
        return [self._create_fallback_initiative(priority, profile)]

    def _create_fallback_initiative(
        self,
        priority: dict,
        profile: ClientIntelligenceProfile,
    ) -> Initiative:
        """Create basic initiative if LLM fails."""
        return Initiative(
            name=f"Address: {priority.get('priority', 'Strategic Priority')}",
            objective=priority.get("rationale", "Improve AEO performance"),
            content_pieces=[
                ContentBlueprint(
                    title=f"Guide to {profile.category}",
                    content_type="guide",
                    target_queries=[f"What is {profile.category}?"],
                    format_type="explainer",
                    target_length="2000-3000 words",
                    sections=[
                        {
                            "heading": "Introduction",
                            "purpose": "Establish context",
                            "key_points": ["Define topic", "Why it matters"],
                            "citable_facts_needed": ["Industry statistics"],
                        },
                        {
                            "heading": "Key Concepts",
                            "purpose": "Explain fundamentals",
                            "key_points": ["Core concepts"],
                            "citable_facts_needed": ["Definitions"],
                        },
                    ],
                    ai_optimization_requirements=[
                        "Lead with clear definition",
                        "Include specific examples",
                    ],
                    schema_markup_type="Article",
                    authority_signals_needed=["Industry expertise"],
                    content_to_beat=[],
                    how_we_beat_it="More comprehensive and current",
                    target_platform="website",
                    distribution_plan="Publish to blog, share on social",
                    acceptance_criteria=["Citability score > 70", "Complete content"],
                )
            ],
            citation_targets=[],
            timeline="2-4 weeks",
            milestones=[
                Milestone(
                    name="Content Creation",
                    deliverables=["Draft content"],
                    criteria="All sections written",
                )
            ],
            success_metrics=["Content published", "Citability score achieved"],
        )

    async def create_content_calendar(
        self,
        execution_plans: list[ExecutionPlan],
    ) -> list[dict]:
        """Create a content calendar from execution plans."""
        calendar = []

        for plan in execution_plans:
            for initiative in plan.initiatives:
                for i, content in enumerate(initiative.content_pieces):
                    calendar.append({
                        "initiative": initiative.name,
                        "content_title": content.title,
                        "content_type": content.content_type,
                        "target_queries": content.target_queries,
                        "priority": i + 1,
                        "estimated_effort": content.target_length,
                        "acceptance_criteria": content.acceptance_criteria,
                    })

        return calendar
