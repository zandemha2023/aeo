"""
The Strategist - Chief AEO Strategist

"Everyone else collects information. I make decisions. My job is to look at everything
we know—about the client, competitors, market, performance—and determine exactly what
we should do, in what order, and why. Strategy without action is philosophy. Action
without strategy is chaos."
"""

from datetime import datetime
from typing import Any

import structlog

from agents.base import Agent, AgentPersonality
from knowledge.schemas import (
    AEOPerformanceReport,
    ClientIntelligenceProfile,
    CompetitiveIntelligence,
    ContentAuthorityAnalysis,
    HealthGrade,
    Severity,
)

logger = structlog.get_logger()


class StrategicPriority:
    """A strategic priority with rationale."""

    def __init__(
        self,
        rank: int,
        priority: str,
        rationale: str,
        expected_impact: str,
        effort_required: str,
        timeline: str,
        success_metric: str,
        dependencies: list[str] | None = None,
    ):
        self.rank = rank
        self.priority = priority
        self.rationale = rationale
        self.expected_impact = expected_impact
        self.effort_required = effort_required
        self.timeline = timeline
        self.success_metric = success_metric
        self.dependencies = dependencies or []

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "priority": self.priority,
            "rationale": self.rationale,
            "expected_impact": self.expected_impact,
            "effort_required": self.effort_required,
            "timeline": self.timeline,
            "success_metric": self.success_metric,
            "dependencies": self.dependencies,
        }


class AssumptionChallenge:
    """A challenge to client assumptions."""

    def __init__(
        self,
        client_assumption: str,
        reality: str,
        evidence: list[str],
        recommended_pivot: str,
    ):
        self.client_assumption = client_assumption
        self.reality = reality
        self.evidence = evidence
        self.recommended_pivot = recommended_pivot

    def to_dict(self) -> dict:
        return {
            "client_assumption": self.client_assumption,
            "reality": self.reality,
            "evidence": self.evidence,
            "recommended_pivot": self.recommended_pivot,
        }


class AEOStrategy:
    """Complete AEO strategy output."""

    def __init__(
        self,
        executive_summary: str,
        current_state_assessment: dict,
        strategic_thesis: str,
        priorities: list[StrategicPriority],
        assumption_challenges: list[AssumptionChallenge] | None = None,
        explicitly_deprioritized: list[dict] | None = None,
        day_30_goals: list[str] | None = None,
        day_60_goals: list[str] | None = None,
        day_90_goals: list[str] | None = None,
        success_metrics: list[dict] | None = None,
    ):
        self.executive_summary = executive_summary
        self.current_state_assessment = current_state_assessment
        self.strategic_thesis = strategic_thesis
        self.priorities = priorities
        self.assumption_challenges = assumption_challenges or []
        self.explicitly_deprioritized = explicitly_deprioritized or []
        self.day_30_goals = day_30_goals or []
        self.day_60_goals = day_60_goals or []
        self.day_90_goals = day_90_goals or []
        self.success_metrics = success_metrics or []

    def to_dict(self) -> dict:
        return {
            "executive_summary": self.executive_summary,
            "current_state_assessment": self.current_state_assessment,
            "strategic_thesis": self.strategic_thesis,
            "priorities": [p.to_dict() for p in self.priorities],
            "assumption_challenges": [a.to_dict() for a in self.assumption_challenges],
            "explicitly_deprioritized": self.explicitly_deprioritized,
            "day_30_goals": self.day_30_goals,
            "day_60_goals": self.day_60_goals,
            "day_90_goals": self.day_90_goals,
            "success_metrics": self.success_metrics,
        }


class StrategistAgent(Agent):
    """
    Chief AEO Strategist.

    Synthesizes all intelligence into actionable strategy. Determines what
    the client should do, challenges assumptions when wrong, and ensures
    every action serves business goals.
    """

    @property
    def personality(self) -> AgentPersonality:
        return AgentPersonality(
            name="The Strategist",
            title="Chief AEO Strategist",
            identity="""Everyone else collects information. I make decisions. My job is to
look at everything we know—about the client, competitors, market, performance—and
determine exactly what we should do, in what order, and why. Strategy without action
is philosophy. Action without strategy is chaos.""",
            personality_traits=[
                "Decisive—makes clear recommendations, not hedged suggestions",
                "Prioritization-obsessed—knows you can't do everything",
                "Contrarian when necessary—challenges assumptions",
                "Results-focused—only cares about outcomes, not activity",
            ],
            core_mission="""Synthesize all intelligence into actionable strategy. Determine
what the client should do, challenge their assumptions when wrong, and ensure every
action serves business goals.""",
            thinking_style="""When I receive a request like "improve our AEO," I don't just
start listing tactics. I ask: What's actually holding them back? Is it content gaps?
Authority problems? Technical issues? Competitor dominance?

Then I prioritize ruthlessly. What's the one thing that will have the biggest impact?
What's the sequence of actions that builds on itself? What should we explicitly NOT
do because it's a distraction?

I'd rather do three things excellently than ten things mediocrely. Every recommendation
I make has to earn its place.""",
        )

    async def run(
        self,
        client_profile: ClientIntelligenceProfile,
        performance_report: AEOPerformanceReport,
        competitive_intel: CompetitiveIntelligence | None = None,
        content_analysis: ContentAuthorityAnalysis | None = None,
        client_constraints: dict | None = None,
    ) -> AEOStrategy:
        """
        Generate comprehensive AEO strategy.

        Args:
            client_profile: Client intelligence from Cartographer
            performance_report: Performance data from Auditor
            competitive_intel: Competitive intelligence from Scout
            content_analysis: Content analysis from Librarian
            client_constraints: Budget, timeline, resource constraints

        Returns:
            Complete AEOStrategy
        """
        self._log_task_start(
            "generate_strategy",
            health_score=performance_report.overall_health_score,
        )

        # Assess current state
        state_assessment = self._assess_current_state(
            client_profile,
            performance_report,
            competitive_intel,
            content_analysis,
        )

        # Generate strategic thesis
        thesis = self._generate_thesis(
            state_assessment,
            client_profile,
            performance_report,
        )

        # Generate priorities using LLM
        strategy = await self._generate_full_strategy(
            client_profile,
            performance_report,
            competitive_intel,
            content_analysis,
            state_assessment,
            thesis,
            client_constraints,
        )

        self._log_task_complete(
            "generate_strategy",
            priorities=len(strategy.priorities),
        )

        return strategy

    def _assess_current_state(
        self,
        client_profile: ClientIntelligenceProfile,
        performance: AEOPerformanceReport,
        competitive: CompetitiveIntelligence | None,
        content: ContentAuthorityAnalysis | None,
    ) -> dict:
        """Assess the current AEO state."""

        # Determine biggest strength
        strength = self._identify_biggest_strength(performance, content)

        # Determine biggest weakness
        weakness = self._identify_biggest_weakness(performance, content)

        # Determine biggest opportunity
        opportunity = self._identify_biggest_opportunity(competitive, content)

        # Determine biggest threat
        threat = self._identify_biggest_threat(performance, competitive)

        return {
            "health_summary": self._summarize_health(performance),
            "biggest_strength": strength,
            "biggest_weakness": weakness,
            "biggest_opportunity": opportunity,
            "biggest_threat": threat,
        }

    def _summarize_health(self, performance: AEOPerformanceReport) -> str:
        """Summarize overall health status."""
        score = performance.overall_health_score
        grade = performance.health_grade

        if grade == HealthGrade.A:
            return f"Excellent AEO health (score: {score}/100). Strong position to maintain and expand."
        elif grade == HealthGrade.B:
            return f"Good AEO health (score: {score}/100). Some areas for improvement but solid foundation."
        elif grade == HealthGrade.C:
            return f"Average AEO health (score: {score}/100). Significant room for improvement."
        elif grade == HealthGrade.D:
            return f"Below average AEO health (score: {score}/100). Needs focused attention."
        else:
            return f"Poor AEO health (score: {score}/100). Critical issues require immediate action."

    def _identify_biggest_strength(
        self,
        performance: AEOPerformanceReport,
        content: ContentAuthorityAnalysis | None,
    ) -> str:
        """Identify the biggest strength."""
        strengths = []

        if performance.metrics.mention_rate > performance.metrics.mention_rate_benchmark:
            strengths.append("Above-benchmark mention rate")

        if performance.metrics.accuracy_rate > 0.95:
            strengths.append("High accuracy in AI responses")

        if performance.metrics.recommendation_rate > 0.4:
            strengths.append("Strong recommendation rate")

        if content and content.total_content_pieces > 50:
            strengths.append("Substantial content library")

        high_citability = [c for c in (content.ai_citable_content if content else []) if c.citability_score > 0.7]
        if len(high_citability) > 5:
            strengths.append(f"{len(high_citability)} highly citable content pieces")

        return strengths[0] if strengths else "No significant strengths identified"

    def _identify_biggest_weakness(
        self,
        performance: AEOPerformanceReport,
        content: ContentAuthorityAnalysis | None,
    ) -> str:
        """Identify the biggest weakness."""
        # Check for critical issues first
        critical = [i for i in performance.issues if i.severity == Severity.CRITICAL]
        if critical:
            return critical[0].issue

        warnings = [i for i in performance.issues if i.severity == Severity.WARNING]
        if warnings:
            return warnings[0].issue

        if performance.metrics.mention_rate < 0.3:
            return "Low overall AI visibility"

        if content and len(content.content_gaps) > 5:
            return "Significant content gaps"

        return "No critical weaknesses identified"

    def _identify_biggest_opportunity(
        self,
        competitive: CompetitiveIntelligence | None,
        content: ContentAuthorityAnalysis | None,
    ) -> str:
        """Identify the biggest opportunity."""
        if competitive and competitive.market_opportunities:
            return competitive.market_opportunities[0].opportunity

        if content and content.citation_opportunities:
            return f"Build presence on {content.citation_opportunities[0].platform}"

        if content and content.content_gaps:
            top_gap = content.content_gaps[0]
            return f"Create content for: {top_gap.topic}"

        return "Expand into adjacent query categories"

    def _identify_biggest_threat(
        self,
        performance: AEOPerformanceReport,
        competitive: CompetitiveIntelligence | None,
    ) -> str:
        """Identify the biggest threat."""
        if competitive and competitive.competitive_alerts:
            urgent = [a for a in competitive.competitive_alerts if a.threat_level == "urgent"]
            if urgent:
                return f"{urgent[0].competitor}: {urgent[0].event}"

        if performance.metrics.misinformation_count > 0:
            return "Active misinformation in AI responses"

        if performance.metrics.mention_rate_trend.value == "declining":
            return "Declining visibility trend"

        if competitive:
            high_share = [c for c in competitive.competitors if c.ai_mention_rate > 0.6]
            if high_share:
                return f"Strong competitor: {high_share[0].name} ({high_share[0].ai_mention_rate:.0%} mention rate)"

        return "No immediate threats identified"

    def _generate_thesis(
        self,
        state: dict,
        profile: ClientIntelligenceProfile,
        performance: AEOPerformanceReport,
    ) -> str:
        """Generate the core strategic thesis."""
        # Determine primary strategic direction based on state

        if performance.overall_health_score < 50:
            return f"Foundation building: {profile.company_essence.split('.')[0]} needs to establish baseline AI visibility through systematic content creation and authority building before optimizing."

        if state["biggest_weakness"].startswith("Low"):
            return f"Visibility expansion: Focus on increasing mention rate from {performance.metrics.mention_rate:.0%} through targeted content addressing high-value query categories."

        if "competitor" in state["biggest_threat"].lower():
            return f"Competitive response: Counter {state['biggest_threat'].split(':')[0]}'s dominance through differentiated positioning and content that highlights unique strengths."

        if performance.overall_health_score > 70:
            return f"Authority consolidation: Build on strong foundation ({performance.overall_health_score:.0f}/100) by deepening presence in core categories and expanding to adjacent opportunities."

        return f"Balanced improvement: Address {state['biggest_weakness']} while leveraging {state['biggest_strength']} to capture {state['biggest_opportunity']}."

    async def _generate_full_strategy(
        self,
        client_profile: ClientIntelligenceProfile,
        performance: AEOPerformanceReport,
        competitive: CompetitiveIntelligence | None,
        content: ContentAuthorityAnalysis | None,
        state_assessment: dict,
        thesis: str,
        constraints: dict | None,
    ) -> AEOStrategy:
        """Use LLM to generate complete strategy."""

        task_context = """You are The Strategist generating a comprehensive AEO strategy.
Be decisive and specific. Every recommendation must have clear rationale and expected impact.
Prioritize ruthlessly—better to do 3 things well than 10 things poorly."""

        # Build context summary
        context = f"""
CLIENT: {client_profile.company_essence}
CATEGORY: {client_profile.category}
MARKET POSITION: {client_profile.market_position.value}

PERFORMANCE:
- Health Score: {performance.overall_health_score}/100 (Grade: {performance.health_grade.value})
- Mention Rate: {performance.metrics.mention_rate:.1%} (benchmark: {performance.metrics.mention_rate_benchmark:.1%})
- Recommendation Rate: {performance.metrics.recommendation_rate:.1%}
- Accuracy Rate: {performance.metrics.accuracy_rate:.1%}
- Issues: {len(performance.issues)} ({len([i for i in performance.issues if i.severity == Severity.CRITICAL])} critical)

STATE ASSESSMENT:
- Biggest Strength: {state_assessment['biggest_strength']}
- Biggest Weakness: {state_assessment['biggest_weakness']}
- Biggest Opportunity: {state_assessment['biggest_opportunity']}
- Biggest Threat: {state_assessment['biggest_threat']}

STRATEGIC THESIS: {thesis}
"""

        if competitive:
            context += f"""
COMPETITIVE LANDSCAPE:
- {len(competitive.competitors)} competitors analyzed
- Top competitor mention rates: {', '.join(f'{c.name}: {c.ai_mention_rate:.0%}' for c in competitive.competitors[:3])}
- Market opportunities: {len(competitive.market_opportunities)}
"""

        if content:
            context += f"""
CONTENT ANALYSIS:
- Total content pieces: {content.total_content_pieces}
- Content gaps identified: {len(content.content_gaps)}
- Citation opportunities: {len(content.citation_opportunities)}
"""

        if constraints:
            context += f"""
CONSTRAINTS:
{chr(10).join(f'- {k}: {v}' for k, v in constraints.items())}
"""

        prompt = f"""{context}

Generate a comprehensive AEO strategy as JSON:
{{
    "executive_summary": "2-3 sentence summary of the strategy",
    "priorities": [
        {{
            "rank": 1,
            "priority": "Specific action to take",
            "rationale": "Why this is important",
            "expected_impact": "What improvement we expect",
            "effort_required": "low/medium/high",
            "timeline": "When to complete",
            "success_metric": "How to measure success",
            "dependencies": ["Any dependencies"]
        }}
    ],
    "assumption_challenges": [
        {{
            "client_assumption": "What client might assume",
            "reality": "What the data shows",
            "evidence": ["Supporting evidence"],
            "recommended_pivot": "What to do instead"
        }}
    ],
    "explicitly_deprioritized": [
        {{
            "action": "What NOT to do",
            "why_not_now": "Why deprioritizing",
            "when_to_reconsider": "When it might become relevant"
        }}
    ],
    "day_30_goals": ["Goal 1", "Goal 2"],
    "day_60_goals": ["Goal 1", "Goal 2"],
    "day_90_goals": ["Goal 1", "Goal 2"],
    "success_metrics": [
        {{
            "metric": "Metric name",
            "current_value": "Current",
            "target_value": "Target",
            "timeline": "By when",
            "measurement_method": "How to measure"
        }}
    ]
}}

Include 3-5 priorities, ranked by impact. Be specific and actionable.
Respond ONLY with the JSON object."""

        try:
            response = self._call_llm(prompt, task_context, max_tokens=4096)

            import json
            import re

            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())

                priorities = [
                    StrategicPriority(**p) for p in data.get("priorities", [])
                ]

                challenges = [
                    AssumptionChallenge(**c) for c in data.get("assumption_challenges", [])
                ]

                return AEOStrategy(
                    executive_summary=data.get("executive_summary", ""),
                    current_state_assessment=state_assessment,
                    strategic_thesis=thesis,
                    priorities=priorities,
                    assumption_challenges=challenges,
                    explicitly_deprioritized=data.get("explicitly_deprioritized", []),
                    day_30_goals=data.get("day_30_goals", []),
                    day_60_goals=data.get("day_60_goals", []),
                    day_90_goals=data.get("day_90_goals", []),
                    success_metrics=data.get("success_metrics", []),
                )

        except Exception as e:
            self._log.error("strategy_generation_failed", error=str(e))

        # Fallback to basic strategy
        return self._generate_fallback_strategy(
            state_assessment,
            thesis,
            performance,
        )

    def _generate_fallback_strategy(
        self,
        state: dict,
        thesis: str,
        performance: AEOPerformanceReport,
    ) -> AEOStrategy:
        """Generate basic strategy if LLM fails."""
        priorities = [
            StrategicPriority(
                rank=1,
                priority=f"Address: {state['biggest_weakness']}",
                rationale="Fixing the biggest weakness will have the most impact",
                expected_impact="10-20% improvement in health score",
                effort_required="medium",
                timeline="30 days",
                success_metric="Reduction in identified issues",
            ),
            StrategicPriority(
                rank=2,
                priority=f"Pursue: {state['biggest_opportunity']}",
                rationale="Opportunity to gain competitive advantage",
                expected_impact="Expanded visibility in new areas",
                effort_required="medium",
                timeline="60 days",
                success_metric="Mention rate increase in target areas",
            ),
        ]

        return AEOStrategy(
            executive_summary=f"Focus on addressing {state['biggest_weakness']} while pursuing {state['biggest_opportunity']}.",
            current_state_assessment=state,
            strategic_thesis=thesis,
            priorities=priorities,
            day_30_goals=["Address critical issues", "Begin content creation"],
            day_60_goals=["Expand content coverage", "Build authority"],
            day_90_goals=["Achieve target mention rate", "Establish competitive position"],
        )
