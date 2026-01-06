"""
The Analyst - Data & Performance Analyst

"Numbers don't lie, but they don't explain themselves either. I translate raw performance
data into strategic insights. What's actually driving citation? What's declining and why?
What patterns predict future performance? I find the signal in the noise."
"""

from datetime import datetime
from typing import Any

import structlog

from agents.base import Agent, AgentPersonality
from knowledge.schemas import AEOPerformanceReport, BrandMention

logger = structlog.get_logger()


class PerformanceTrend:
    """A trend identified in performance data."""

    def __init__(
        self,
        metric: str,
        direction: str,  # up, down, stable
        change_percentage: float,
        period: str,
        significance: str,  # high, medium, low
        explanation: str,
        implications: list[str],
    ):
        self.metric = metric
        self.direction = direction
        self.change_percentage = change_percentage
        self.period = period
        self.significance = significance
        self.explanation = explanation
        self.implications = implications

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "direction": self.direction,
            "change_percentage": self.change_percentage,
            "period": self.period,
            "significance": self.significance,
            "explanation": self.explanation,
            "implications": self.implications,
        }


class CompetitorComparison:
    """Comparison analysis against competitors."""

    def __init__(
        self,
        competitor: str,
        metrics_comparison: dict[str, dict],  # metric -> {us, them, delta}
        areas_ahead: list[str],
        areas_behind: list[str],
        recommendations: list[str],
    ):
        self.competitor = competitor
        self.metrics_comparison = metrics_comparison
        self.areas_ahead = areas_ahead
        self.areas_behind = areas_behind
        self.recommendations = recommendations

    def to_dict(self) -> dict:
        return {
            "competitor": self.competitor,
            "metrics_comparison": self.metrics_comparison,
            "areas_ahead": self.areas_ahead,
            "areas_behind": self.areas_behind,
            "recommendations": self.recommendations,
        }


class QueryAnalysis:
    """Analysis of query performance."""

    def __init__(
        self,
        query_category: str,
        total_queries: int,
        citation_rate: float,
        sentiment_breakdown: dict[str, float],
        top_performing_queries: list[dict],
        underperforming_queries: list[dict],
        opportunities: list[str],
    ):
        self.query_category = query_category
        self.total_queries = total_queries
        self.citation_rate = citation_rate
        self.sentiment_breakdown = sentiment_breakdown
        self.top_performing_queries = top_performing_queries
        self.underperforming_queries = underperforming_queries
        self.opportunities = opportunities

    def to_dict(self) -> dict:
        return {
            "query_category": self.query_category,
            "total_queries": self.total_queries,
            "citation_rate": self.citation_rate,
            "sentiment_breakdown": self.sentiment_breakdown,
            "top_performing_queries": self.top_performing_queries,
            "underperforming_queries": self.underperforming_queries,
            "opportunities": self.opportunities,
        }


class PerformanceAnalysis:
    """Complete performance analysis."""

    def __init__(
        self,
        client_id: str,
        analysis_period: str,
        overall_health_score: float,
        health_change: float,
        key_metrics: dict[str, Any],
        trends: list[PerformanceTrend],
        query_analysis: list[QueryAnalysis],
        competitor_comparisons: list[CompetitorComparison],
        key_insights: list[str],
        recommendations: list[dict],
        forecast: dict[str, Any],
    ):
        self.client_id = client_id
        self.analysis_period = analysis_period
        self.overall_health_score = overall_health_score
        self.health_change = health_change
        self.key_metrics = key_metrics
        self.trends = trends
        self.query_analysis = query_analysis
        self.competitor_comparisons = competitor_comparisons
        self.key_insights = key_insights
        self.recommendations = recommendations
        self.forecast = forecast
        self.created_at = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "client_id": self.client_id,
            "analysis_period": self.analysis_period,
            "overall_health_score": self.overall_health_score,
            "health_change": self.health_change,
            "key_metrics": self.key_metrics,
            "trends": [t.to_dict() for t in self.trends],
            "query_analysis": [q.to_dict() for q in self.query_analysis],
            "competitor_comparisons": [c.to_dict() for c in self.competitor_comparisons],
            "key_insights": self.key_insights,
            "recommendations": self.recommendations,
            "forecast": self.forecast,
            "created_at": self.created_at.isoformat(),
        }


class AnalystAgent(Agent):
    """
    Data & Performance Analyst.

    Analyzes performance data to find insights and patterns.
    """

    @property
    def personality(self) -> AgentPersonality:
        return AgentPersonality(
            name="The Analyst",
            title="Data & Performance Analyst",
            identity="""Numbers don't lie, but they don't explain themselves either. I translate
raw performance data into strategic insights. What's actually driving citation? What's
declining and why? What patterns predict future performance? I find the signal in the noise.""",
            personality_traits=[
                "Data-driven—lets numbers guide conclusions",
                "Skeptical—questions assumptions and validates findings",
                "Clear—explains complex data simply",
                "Forward-looking—identifies leading indicators",
            ],
            core_mission="""Transform raw AEO performance data into actionable strategic insights.""",
            thinking_style="""When I look at data, I'm looking for patterns and anomalies.
Is this trend statistically significant or just noise? What's the underlying cause?
How does this compare to benchmarks?

I never report numbers without context. A 5% drop in citations means nothing without
knowing if that's normal variance, seasonal, or the start of a concerning trend.
Every metric I report comes with interpretation and recommended action.""",
        )

    async def run(
        self,
        client_id: str,
        performance_reports: list[dict],
        mentions: list[dict],
        competitor_data: list[dict] | None = None,
        analysis_period: str = "last_30_days",
    ) -> PerformanceAnalysis:
        """
        Analyze performance data.

        Args:
            client_id: Client ID
            performance_reports: List of performance report dicts
            mentions: List of brand mention dicts
            competitor_data: Optional competitor performance data
            analysis_period: Period being analyzed

        Returns:
            Complete PerformanceAnalysis
        """
        self._log_task_start(
            "analyze_performance",
            client_id=client_id,
            reports=len(performance_reports),
            mentions=len(mentions),
        )

        analysis = await self._analyze_data(
            client_id,
            performance_reports,
            mentions,
            competitor_data or [],
            analysis_period,
        )

        self._log_task_complete(
            "analyze_performance",
            health_score=analysis.overall_health_score,
            insights=len(analysis.key_insights),
        )

        return analysis

    async def _analyze_data(
        self,
        client_id: str,
        reports: list[dict],
        mentions: list[dict],
        competitor_data: list[dict],
        period: str,
    ) -> PerformanceAnalysis:
        """Analyze data using LLM."""

        task_context = """You are The Analyst examining AEO performance data.

ANALYSIS FRAMEWORK:
1. Overall Health - Aggregate health score and trend
2. Key Metrics - Citation rate, sentiment, visibility across engines
3. Trend Analysis - What's changing and why
4. Query Performance - Which queries perform best/worst
5. Competitor Position - How we compare
6. Forecasting - Where metrics are heading

INSIGHT PRIORITIES:
- Actionable findings over interesting observations
- Significant changes over normal variance
- Leading indicators over lagging metrics
- Opportunities over just problems

Always provide context for numbers and clear recommendations for action."""

        # Summarize data for the prompt
        reports_summary = str(reports[:5])[:2000] if reports else "No reports"
        mentions_summary = str(mentions[:10])[:2000] if mentions else "No mentions"
        competitor_summary = str(competitor_data[:3])[:1000] if competitor_data else "No competitor data"

        prompt = f"""Analyze this AEO performance data:

CLIENT ID: {client_id}
ANALYSIS PERIOD: {period}

PERFORMANCE REPORTS (sample):
{reports_summary}

BRAND MENTIONS (sample):
{mentions_summary}

COMPETITOR DATA:
{competitor_summary}

Provide comprehensive analysis as JSON:
{{
    "overall_health_score": 0-100,
    "health_change": -100 to +100 (percentage change),
    "key_metrics": {{
        "citation_rate": 0-100,
        "average_sentiment": -1 to 1,
        "visibility_score": 0-100,
        "mention_volume": number,
        "positive_mention_rate": 0-100
    }},
    "trends": [
        {{
            "metric": "metric name",
            "direction": "up/down/stable",
            "change_percentage": number,
            "period": "time period",
            "significance": "high/medium/low",
            "explanation": "Why this is happening",
            "implications": ["What this means for strategy"]
        }}
    ],
    "query_analysis": [
        {{
            "query_category": "Category name",
            "total_queries": number,
            "citation_rate": 0-100,
            "sentiment_breakdown": {{"positive": 0.x, "neutral": 0.x, "negative": 0.x}},
            "top_performing_queries": [{{"query": "", "citation_rate": 0.x}}],
            "underperforming_queries": [{{"query": "", "citation_rate": 0.x, "issue": ""}}],
            "opportunities": ["Opportunity descriptions"]
        }}
    ],
    "competitor_comparisons": [
        {{
            "competitor": "name",
            "metrics_comparison": {{
                "citation_rate": {{"us": 0.x, "them": 0.x, "delta": 0.x}},
                "sentiment": {{"us": 0.x, "them": 0.x, "delta": 0.x}}
            }},
            "areas_ahead": ["areas where we win"],
            "areas_behind": ["areas where they win"],
            "recommendations": ["how to close gaps"]
        }}
    ],
    "key_insights": [
        "Insight 1: Clear, actionable finding",
        "Insight 2: Another key finding"
    ],
    "recommendations": [
        {{
            "priority": 1,
            "recommendation": "What to do",
            "rationale": "Why this matters",
            "expected_impact": "Expected improvement",
            "effort": "low/medium/high"
        }}
    ],
    "forecast": {{
        "30_day_projection": {{
            "health_score": number,
            "citation_rate": number,
            "confidence": "high/medium/low"
        }},
        "risks": ["Potential risks to monitor"],
        "opportunities": ["Upcoming opportunities"]
    }}
}}

Be specific, actionable, and data-driven. Include confidence levels where appropriate.

Respond ONLY with the JSON object."""

        try:
            response = self._call_llm(prompt, task_context, max_tokens=4096)

            import json
            import re

            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())

                trends = [
                    PerformanceTrend(
                        metric=t.get("metric", ""),
                        direction=t.get("direction", "stable"),
                        change_percentage=t.get("change_percentage", 0),
                        period=t.get("period", ""),
                        significance=t.get("significance", "medium"),
                        explanation=t.get("explanation", ""),
                        implications=t.get("implications", []),
                    )
                    for t in data.get("trends", [])
                ]

                query_analysis = [
                    QueryAnalysis(
                        query_category=q.get("query_category", ""),
                        total_queries=q.get("total_queries", 0),
                        citation_rate=q.get("citation_rate", 0) / 100,
                        sentiment_breakdown=q.get("sentiment_breakdown", {}),
                        top_performing_queries=q.get("top_performing_queries", []),
                        underperforming_queries=q.get("underperforming_queries", []),
                        opportunities=q.get("opportunities", []),
                    )
                    for q in data.get("query_analysis", [])
                ]

                competitor_comparisons = [
                    CompetitorComparison(
                        competitor=c.get("competitor", ""),
                        metrics_comparison=c.get("metrics_comparison", {}),
                        areas_ahead=c.get("areas_ahead", []),
                        areas_behind=c.get("areas_behind", []),
                        recommendations=c.get("recommendations", []),
                    )
                    for c in data.get("competitor_comparisons", [])
                ]

                return PerformanceAnalysis(
                    client_id=client_id,
                    analysis_period=period,
                    overall_health_score=data.get("overall_health_score", 50) / 100,
                    health_change=data.get("health_change", 0) / 100,
                    key_metrics=data.get("key_metrics", {}),
                    trends=trends,
                    query_analysis=query_analysis,
                    competitor_comparisons=competitor_comparisons,
                    key_insights=data.get("key_insights", []),
                    recommendations=data.get("recommendations", []),
                    forecast=data.get("forecast", {}),
                )

        except Exception as e:
            self._log.error("analysis_failed", error=str(e))

        # Return minimal analysis on failure
        return PerformanceAnalysis(
            client_id=client_id,
            analysis_period=period,
            overall_health_score=0.5,
            health_change=0,
            key_metrics={},
            trends=[],
            query_analysis=[],
            competitor_comparisons=[],
            key_insights=["Analysis failed - insufficient data"],
            recommendations=[],
            forecast={},
        )

    def calculate_health_score(
        self,
        citation_rate: float,
        sentiment_score: float,
        visibility_score: float,
        trend_direction: float,  # -1 to 1
    ) -> float:
        """
        Calculate overall health score from component metrics.

        Args:
            citation_rate: 0-1 citation rate
            sentiment_score: -1 to 1 sentiment
            visibility_score: 0-1 visibility
            trend_direction: -1 to 1 recent trend

        Returns:
            Health score 0-1
        """
        # Normalize sentiment to 0-1
        normalized_sentiment = (sentiment_score + 1) / 2

        # Weights for each component
        weights = {
            "citation": 0.35,
            "sentiment": 0.25,
            "visibility": 0.25,
            "trend": 0.15,
        }

        # Normalize trend to 0-1
        normalized_trend = (trend_direction + 1) / 2

        score = (
            citation_rate * weights["citation"]
            + normalized_sentiment * weights["sentiment"]
            + visibility_score * weights["visibility"]
            + normalized_trend * weights["trend"]
        )

        return round(min(1.0, max(0.0, score)), 2)

    def identify_anomalies(
        self,
        data_points: list[dict],
        metric: str,
        threshold_std: float = 2.0,
    ) -> list[dict]:
        """
        Identify anomalous data points.

        Args:
            data_points: List of data point dicts with the metric
            metric: Metric key to analyze
            threshold_std: Standard deviations for anomaly threshold

        Returns:
            List of anomalous data points
        """
        values = [d.get(metric, 0) for d in data_points if metric in d]

        if len(values) < 3:
            return []

        # Calculate mean and std
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std = variance ** 0.5

        if std == 0:
            return []

        # Find anomalies
        anomalies = []
        for i, dp in enumerate(data_points):
            if metric in dp:
                z_score = abs(dp[metric] - mean) / std
                if z_score > threshold_std:
                    anomalies.append({
                        **dp,
                        "z_score": z_score,
                        "deviation": dp[metric] - mean,
                    })

        return anomalies

    def calculate_trend(
        self,
        data_points: list[float],
    ) -> dict:
        """
        Calculate trend from data points.

        Args:
            data_points: List of values in chronological order

        Returns:
            Trend analysis dict
        """
        if len(data_points) < 2:
            return {"direction": "stable", "change": 0, "confidence": "low"}

        # Simple linear trend
        first_half = data_points[:len(data_points)//2]
        second_half = data_points[len(data_points)//2:]

        first_avg = sum(first_half) / len(first_half) if first_half else 0
        second_avg = sum(second_half) / len(second_half) if second_half else 0

        if first_avg == 0:
            change = 0
        else:
            change = (second_avg - first_avg) / first_avg

        # Determine direction
        if abs(change) < 0.05:
            direction = "stable"
        elif change > 0:
            direction = "up"
        else:
            direction = "down"

        # Confidence based on data consistency
        if len(data_points) >= 10:
            confidence = "high"
        elif len(data_points) >= 5:
            confidence = "medium"
        else:
            confidence = "low"

        return {
            "direction": direction,
            "change": round(change * 100, 1),
            "confidence": confidence,
        }
