"""
The Auditor - AEO Performance Monitor

"Numbers don't lie, but they don't speak clearly either. My job is to measure
what matters, track it over time, and translate raw data into actionable truth.
I'm the one who tells you if you're actually making progress or just feeling busy."
"""

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

from agents.base import Agent, AgentPersonality
from calibration import calculate_health_grade, calculate_health_score
from calibration.benchmarks import ABSOLUTE_BENCHMARKS, get_benchmark_for_industry
from knowledge.schemas import (
    AEOMetrics,
    AEOPerformanceReport,
    BrandMention,
    EngineScore,
    HealthGrade,
    PerformanceComparison,
    PerformanceIssue,
    PerformanceTrend,
    Severity,
    TrendDirection,
)

logger = structlog.get_logger()


class AuditorAgent(Agent):
    """
    AEO Performance Monitor.

    Continuously monitors the client's AI visibility, tracks performance over time,
    detects meaningful changes, and provides accurate assessment of AEO health.
    """

    @property
    def personality(self) -> AgentPersonality:
        return AgentPersonality(
            name="The Auditor",
            title="AEO Performance Monitor",
            identity="""Numbers don't lie, but they don't speak clearly either.
My job is to measure what matters, track it over time, and translate raw data
into actionable truth. I'm the one who tells you if you're actually making
progress or just feeling busy.""",
            personality_traits=[
                "Rigorous—obsessed with measurement accuracy",
                "Honest—delivers hard truths when necessary",
                "Longitudinal thinker—cares about trends, not snapshots",
                "Context-aware—knows a metric without context is meaningless",
            ],
            core_mission="""Continuously monitor the client's AI visibility, track
performance over time, detect meaningful changes, and provide accurate assessment
of AEO health.""",
            thinking_style="""When I see a mention rate of 40%, I don't just report "40%."
I ask: Is that good for this industry? How does it compare to last month?
Which engines are we strong on vs. weak? What types of queries are we winning
vs. losing? Is the trend improving or declining?

A single metric is noise. Metrics with context, compared to benchmarks,
tracked over time—that's signal.""",
        )

    async def run(
        self,
        mentions: list[BrandMention],
        industry: str = "",
        previous_metrics: AEOMetrics | None = None,
    ) -> AEOPerformanceReport:
        """
        Analyze brand mentions and produce a performance report.

        Args:
            mentions: List of brand mentions from AI engine queries
            industry: Client's industry for benchmark comparison
            previous_metrics: Previous period metrics for trend analysis

        Returns:
            Complete AEOPerformanceReport with metrics, trends, and issues
        """
        self._log_task_start(
            "analyze_performance",
            mention_count=len(mentions),
            industry=industry,
        )

        # Calculate current metrics
        metrics = self._calculate_metrics(mentions, industry)

        # Calculate health score
        health_score = calculate_health_score(metrics)
        health_grade = calculate_health_grade(health_score)

        # Analyze trends if we have historical data
        trends = []
        vs_previous = None
        if previous_metrics:
            trends = self._analyze_trends(metrics, previous_metrics)
            vs_previous = self._compare_periods(metrics, previous_metrics, "previous period")

        # Detect issues
        issues = self._detect_issues(metrics, mentions)

        report = AEOPerformanceReport(
            overall_health_score=health_score,
            health_grade=health_grade,
            metrics=metrics,
            trends=trends,
            vs_last_week=vs_previous,  # Caller can pass appropriate period
            vs_last_month=None,
            vs_competitors={},
            issues=issues,
            last_updated=datetime.utcnow(),
        )

        self._log_task_complete(
            "analyze_performance",
            health_score=health_score,
            health_grade=health_grade.value,
            issues_found=len(issues),
        )

        return report

    def _calculate_metrics(
        self,
        mentions: list[BrandMention],
        industry: str,
    ) -> AEOMetrics:
        """Calculate AEO metrics from brand mentions."""

        if not mentions:
            return self._empty_metrics(industry)

        total_queries = len(mentions)
        mentioned_count = sum(1 for m in mentions if m.mentioned)
        recommended_count = sum(1 for m in mentions if m.recommended)
        first_position_count = sum(1 for m in mentions if m.position == 1)
        cited_count = sum(1 for m in mentions if m.sources_cited)

        # Accuracy
        accurate_count = sum(
            1 for m in mentions if m.accuracy == "accurate" and m.mentioned
        )
        mentioned_for_accuracy = sum(1 for m in mentions if m.mentioned and m.accuracy)

        # Sentiment
        sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
        for m in mentions:
            if m.sentiment and m.mentioned:
                sentiment_counts[m.sentiment] += 1
        sentiment_total = sum(sentiment_counts.values())

        # Calculate rates
        mention_rate = mentioned_count / total_queries if total_queries > 0 else 0
        recommendation_rate = recommended_count / mentioned_count if mentioned_count > 0 else 0
        first_position_rate = first_position_count / mentioned_count if mentioned_count > 0 else 0
        citation_rate = cited_count / mentioned_count if mentioned_count > 0 else 0
        accuracy_rate = (
            accurate_count / mentioned_for_accuracy if mentioned_for_accuracy > 0 else 1.0
        )

        # Sentiment breakdown
        sentiment_breakdown = {
            k: v / sentiment_total if sentiment_total > 0 else 0
            for k, v in sentiment_counts.items()
        }

        # Get industry benchmark
        benchmark = get_benchmark_for_industry(industry)
        benchmark_rate = benchmark.average_mention_rate if benchmark else 0.40

        # Calculate by engine
        engine_mentions: dict[str, list[BrandMention]] = {}
        for m in mentions:
            if m.engine not in engine_mentions:
                engine_mentions[m.engine] = []
            engine_mentions[m.engine].append(m)

        engine_scores = {}
        for engine, engine_mentions_list in engine_mentions.items():
            engine_total = len(engine_mentions_list)
            engine_mentioned = sum(1 for m in engine_mentions_list if m.mentioned)
            engine_recommended = sum(1 for m in engine_mentions_list if m.recommended)

            engine_scores[engine] = EngineScore(
                engine=engine,
                mention_rate=engine_mentioned / engine_total if engine_total > 0 else 0,
                recommendation_rate=(
                    engine_recommended / engine_mentioned if engine_mentioned > 0 else 0
                ),
                trend=TrendDirection.STABLE,  # Will be updated with historical data
                notes="",
            )

        # Count misinformation
        misinformation_count = sum(
            1 for m in mentions if m.accuracy == "inaccurate" and m.mentioned
        )

        return AEOMetrics(
            mention_rate=mention_rate,
            mention_rate_benchmark=benchmark_rate,
            mention_rate_trend=TrendDirection.STABLE,  # Updated with historical
            recommendation_rate=recommendation_rate,
            first_position_rate=first_position_rate,
            citation_rate=citation_rate,
            accuracy_rate=accuracy_rate,
            sentiment_breakdown=sentiment_breakdown,
            misinformation_count=misinformation_count,
            engine_scores=engine_scores,
        )

    def _empty_metrics(self, industry: str) -> AEOMetrics:
        """Return empty metrics when no mentions exist."""
        benchmark = get_benchmark_for_industry(industry)
        benchmark_rate = benchmark.average_mention_rate if benchmark else 0.40

        return AEOMetrics(
            mention_rate=0,
            mention_rate_benchmark=benchmark_rate,
            mention_rate_trend=TrendDirection.STABLE,
            recommendation_rate=0,
            first_position_rate=0,
            citation_rate=0,
            accuracy_rate=1.0,  # No inaccuracies if no mentions
            sentiment_breakdown={"positive": 0, "neutral": 0, "negative": 0},
            misinformation_count=0,
            engine_scores={},
        )

    def _analyze_trends(
        self,
        current: AEOMetrics,
        previous: AEOMetrics,
    ) -> list[PerformanceTrend]:
        """Analyze trends between current and previous metrics."""
        trends = []

        # Mention rate trend
        mention_change = current.mention_rate - previous.mention_rate
        if abs(mention_change) > 0.05:
            trends.append(
                PerformanceTrend(
                    metric="mention_rate",
                    direction=(
                        TrendDirection.IMPROVING
                        if mention_change > 0
                        else TrendDirection.DECLINING
                    ),
                    magnitude=f"{abs(mention_change) * 100:.1f}%",
                    significance="high" if abs(mention_change) > 0.10 else "moderate",
                    explanation=self._explain_trend("mention rate", mention_change),
                )
            )

        # Recommendation rate trend
        rec_change = current.recommendation_rate - previous.recommendation_rate
        if abs(rec_change) > 0.05:
            trends.append(
                PerformanceTrend(
                    metric="recommendation_rate",
                    direction=(
                        TrendDirection.IMPROVING if rec_change > 0 else TrendDirection.DECLINING
                    ),
                    magnitude=f"{abs(rec_change) * 100:.1f}%",
                    significance="high" if abs(rec_change) > 0.10 else "moderate",
                    explanation=self._explain_trend("recommendation rate", rec_change),
                )
            )

        # Accuracy trend (critical)
        accuracy_change = current.accuracy_rate - previous.accuracy_rate
        if accuracy_change < -0.02:  # Any decline in accuracy is concerning
            trends.append(
                PerformanceTrend(
                    metric="accuracy_rate",
                    direction=TrendDirection.DECLINING,
                    magnitude=f"{abs(accuracy_change) * 100:.1f}%",
                    significance="critical",
                    explanation="Accuracy is declining - investigate for misinformation",
                )
            )

        return trends

    def _explain_trend(self, metric: str, change: float) -> str:
        """Generate explanation for a trend."""
        direction = "increased" if change > 0 else "decreased"
        magnitude = abs(change) * 100

        if magnitude > 20:
            impact = "This is a significant change requiring investigation."
        elif magnitude > 10:
            impact = "This is a notable change worth monitoring."
        else:
            impact = "This is a moderate change."

        return f"{metric.replace('_', ' ').title()} {direction} by {magnitude:.1f}%. {impact}"

    def _compare_periods(
        self,
        current: AEOMetrics,
        previous: AEOMetrics,
        period_name: str,
    ) -> PerformanceComparison:
        """Compare current metrics to a previous period."""
        mention_change = current.mention_rate - previous.mention_rate
        rec_change = current.recommendation_rate - previous.recommendation_rate

        # Overall assessment
        if mention_change > 0.05 and rec_change > 0.05:
            assessment = "Strong improvement across key metrics"
        elif mention_change > 0.05 or rec_change > 0.05:
            assessment = "Positive movement in some metrics"
        elif mention_change < -0.05 or rec_change < -0.05:
            assessment = "Some metrics are declining - needs attention"
        else:
            assessment = "Performance is stable"

        return PerformanceComparison(
            period=period_name,
            mention_rate_change=mention_change,
            recommendation_rate_change=rec_change,
            overall_assessment=assessment,
        )

    def _detect_issues(
        self,
        metrics: AEOMetrics,
        mentions: list[BrandMention],
    ) -> list[PerformanceIssue]:
        """Detect performance issues from metrics and mentions."""
        issues = []
        b = ABSOLUTE_BENCHMARKS

        # Critical: Misinformation
        if metrics.misinformation_count > 0:
            inaccurate_mentions = [
                m for m in mentions if m.accuracy == "inaccurate" and m.mentioned
            ]
            issues.append(
                PerformanceIssue(
                    severity=Severity.CRITICAL,
                    issue=f"Found {metrics.misinformation_count} instances of misinformation",
                    evidence=[
                        f"Query: '{m.query}' on {m.engine}: {m.context[:100]}..."
                        for m in inaccurate_mentions[:3]
                    ],
                    recommended_action="Immediately address misinformation through content correction and AI engine feedback",
                )
            )

        # Critical: Very low mention rate
        if metrics.mention_rate < b.mention_rate_poor:
            issues.append(
                PerformanceIssue(
                    severity=Severity.CRITICAL,
                    issue=f"Mention rate ({metrics.mention_rate:.1%}) is critically low",
                    evidence=[
                        f"Below poor threshold of {b.mention_rate_poor:.0%}",
                        f"Industry benchmark is {metrics.mention_rate_benchmark:.0%}",
                    ],
                    recommended_action="Prioritize content creation and authority building",
                )
            )

        # Warning: Low accuracy
        if metrics.accuracy_rate < b.accuracy_rate_acceptable:
            issues.append(
                PerformanceIssue(
                    severity=Severity.WARNING,
                    issue=f"Accuracy rate ({metrics.accuracy_rate:.1%}) below acceptable threshold",
                    evidence=[
                        f"Threshold is {b.accuracy_rate_acceptable:.0%}",
                    ],
                    recommended_action="Review and correct inaccurate information in AI responses",
                )
            )

        # Warning: High negative sentiment
        negative_rate = metrics.sentiment_breakdown.get("negative", 0)
        if negative_rate > b.sentiment_negative_max:
            issues.append(
                PerformanceIssue(
                    severity=Severity.WARNING,
                    issue=f"Negative sentiment ({negative_rate:.1%}) exceeds threshold",
                    evidence=[
                        f"Maximum acceptable is {b.sentiment_negative_max:.0%}",
                    ],
                    recommended_action="Investigate causes of negative sentiment and address",
                )
            )

        # Info: Below benchmark
        if metrics.mention_rate < metrics.mention_rate_benchmark:
            gap = metrics.mention_rate_benchmark - metrics.mention_rate
            issues.append(
                PerformanceIssue(
                    severity=Severity.INFO,
                    issue=f"Mention rate {gap:.1%} below industry benchmark",
                    evidence=[
                        f"Current: {metrics.mention_rate:.1%}",
                        f"Benchmark: {metrics.mention_rate_benchmark:.1%}",
                    ],
                    recommended_action="Focus on content gaps and authority building to close gap",
                )
            )

        # Warning: Engine-specific weaknesses
        for engine, score in metrics.engine_scores.items():
            if score.mention_rate < 0.20:
                issues.append(
                    PerformanceIssue(
                        severity=Severity.WARNING,
                        issue=f"Very low visibility on {engine} ({score.mention_rate:.1%})",
                        evidence=[f"Recommendation rate: {score.recommendation_rate:.1%}"],
                        recommended_action=f"Investigate {engine}-specific content and citation opportunities",
                    )
                )

        return issues

    async def generate_executive_summary(
        self,
        report: AEOPerformanceReport,
        client_name: str,
    ) -> str:
        """Generate an executive summary of the performance report using LLM."""

        task_context = """Generate a concise executive summary of AEO performance.
Be direct and actionable. Focus on what matters most: wins, concerns, and next steps."""

        prompt = f"""Create an executive summary for {client_name}'s AEO performance:

Health Score: {report.overall_health_score}/100 (Grade: {report.health_grade.value})

Key Metrics:
- Mention Rate: {report.metrics.mention_rate:.1%} (benchmark: {report.metrics.mention_rate_benchmark:.1%})
- Recommendation Rate: {report.metrics.recommendation_rate:.1%}
- Citation Rate: {report.metrics.citation_rate:.1%}
- Accuracy Rate: {report.metrics.accuracy_rate:.1%}

Issues Found: {len(report.issues)}
Critical Issues: {len([i for i in report.issues if i.severity == Severity.CRITICAL])}

Trends: {len(report.trends)} significant trends identified

Write a 2-3 paragraph executive summary covering:
1. Overall health assessment
2. Key wins and concerns
3. Priority actions"""

        summary = self._call_llm(
            user_prompt=prompt,
            task_context=task_context,
            max_tokens=1024,
        )

        return summary
