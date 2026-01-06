"""
The Reporter - Client Communications Specialist

"I turn our complex work into clear client communication. Executives don't want to see
LangGraph workflows or citability scores—they want to know if their investment is paying off.
I translate technical AEO work into business outcomes they understand and care about."
"""

from datetime import datetime
from typing import Any

import structlog

from agents.base import Agent, AgentPersonality

logger = structlog.get_logger()


class ReportSection:
    """A section of a client report."""

    def __init__(
        self,
        title: str,
        content: str,
        data_highlights: list[dict],
        visualization_type: str | None = None,  # chart, table, metric_card, etc.
        visualization_data: dict | None = None,
    ):
        self.title = title
        self.content = content
        self.data_highlights = data_highlights
        self.visualization_type = visualization_type
        self.visualization_data = visualization_data

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "content": self.content,
            "data_highlights": self.data_highlights,
            "visualization_type": self.visualization_type,
            "visualization_data": self.visualization_data,
        }


class ClientReport:
    """Complete client report."""

    def __init__(
        self,
        client_id: str,
        client_name: str,
        report_type: str,  # weekly, monthly, quarterly, ad-hoc
        period: str,
        executive_summary: str,
        key_metrics: dict[str, Any],
        sections: list[ReportSection],
        wins: list[str],
        challenges: list[str],
        next_steps: list[dict],
        appendix: dict | None = None,
    ):
        self.client_id = client_id
        self.client_name = client_name
        self.report_type = report_type
        self.period = period
        self.executive_summary = executive_summary
        self.key_metrics = key_metrics
        self.sections = sections
        self.wins = wins
        self.challenges = challenges
        self.next_steps = next_steps
        self.appendix = appendix
        self.created_at = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "client_id": self.client_id,
            "client_name": self.client_name,
            "report_type": self.report_type,
            "period": self.period,
            "executive_summary": self.executive_summary,
            "key_metrics": self.key_metrics,
            "sections": [s.to_dict() for s in self.sections],
            "wins": self.wins,
            "challenges": self.challenges,
            "next_steps": self.next_steps,
            "appendix": self.appendix,
            "created_at": self.created_at.isoformat(),
        }

    def to_markdown(self) -> str:
        """Convert report to markdown format."""
        lines = [
            f"# {self.client_name} - AEO Performance Report",
            f"**Report Type:** {self.report_type.title()}",
            f"**Period:** {self.period}",
            f"**Generated:** {self.created_at.strftime('%Y-%m-%d')}",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
            self.executive_summary,
            "",
            "---",
            "",
            "## Key Metrics",
            "",
        ]

        # Add key metrics as a table
        for metric, value in self.key_metrics.items():
            formatted_metric = metric.replace("_", " ").title()
            if isinstance(value, float):
                if value <= 1:
                    lines.append(f"- **{formatted_metric}:** {value:.1%}")
                else:
                    lines.append(f"- **{formatted_metric}:** {value:.1f}")
            else:
                lines.append(f"- **{formatted_metric}:** {value}")

        lines.append("")

        # Add wins
        if self.wins:
            lines.extend([
                "## 🎯 Wins This Period",
                "",
            ])
            for win in self.wins:
                lines.append(f"- {win}")
            lines.append("")

        # Add challenges
        if self.challenges:
            lines.extend([
                "## ⚠️ Challenges & Focus Areas",
                "",
            ])
            for challenge in self.challenges:
                lines.append(f"- {challenge}")
            lines.append("")

        # Add sections
        for section in self.sections:
            lines.extend([
                f"## {section.title}",
                "",
                section.content,
                "",
            ])

            if section.data_highlights:
                for highlight in section.data_highlights:
                    lines.append(f"- **{highlight.get('label', '')}:** {highlight.get('value', '')}")
                lines.append("")

        # Add next steps
        if self.next_steps:
            lines.extend([
                "## Next Steps",
                "",
            ])
            for i, step in enumerate(self.next_steps, 1):
                priority = step.get("priority", "")
                action = step.get("action", "")
                owner = step.get("owner", "")
                lines.append(f"{i}. [{priority}] {action}")
                if owner:
                    lines.append(f"   - Owner: {owner}")
            lines.append("")

        return "\n".join(lines)

    def to_html(self) -> str:
        """Convert report to HTML format."""
        # Convert markdown to basic HTML
        md = self.to_markdown()
        lines = md.split("\n")
        html_lines = []

        for line in lines:
            if line.startswith("# "):
                html_lines.append(f"<h1>{line[2:]}</h1>")
            elif line.startswith("## "):
                html_lines.append(f"<h2>{line[3:]}</h2>")
            elif line.startswith("### "):
                html_lines.append(f"<h3>{line[4:]}</h3>")
            elif line.startswith("- "):
                html_lines.append(f"<li>{line[2:]}</li>")
            elif line.startswith("---"):
                html_lines.append("<hr>")
            elif line.startswith("**") and ":**" in line:
                # Key-value pair
                html_lines.append(f"<p>{line}</p>")
            elif line.strip():
                html_lines.append(f"<p>{line}</p>")

        return "\n".join(html_lines)


class AlertNotification:
    """An alert notification for clients."""

    def __init__(
        self,
        client_id: str,
        alert_type: str,  # positive, negative, informational
        severity: str,  # critical, high, medium, low
        title: str,
        message: str,
        data: dict,
        recommended_action: str | None = None,
    ):
        self.client_id = client_id
        self.alert_type = alert_type
        self.severity = severity
        self.title = title
        self.message = message
        self.data = data
        self.recommended_action = recommended_action
        self.created_at = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "client_id": self.client_id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "data": self.data,
            "recommended_action": self.recommended_action,
            "created_at": self.created_at.isoformat(),
        }


class ReporterAgent(Agent):
    """
    Client Communications Specialist.

    Creates clear, actionable reports for clients.
    """

    @property
    def personality(self) -> AgentPersonality:
        return AgentPersonality(
            name="The Reporter",
            title="Client Communications Specialist",
            identity="""I turn our complex work into clear client communication. Executives don't
want to see LangGraph workflows or citability scores—they want to know if their
investment is paying off. I translate technical AEO work into business outcomes
they understand and care about.""",
            personality_traits=[
                "Clear—no jargon, no confusion",
                "Business-focused—connects to ROI and outcomes",
                "Balanced—honest about challenges, not just wins",
                "Action-oriented—every report leads to next steps",
            ],
            core_mission="""Translate complex AEO work into clear, actionable client
communications that demonstrate value.""",
            thinking_style="""When I write a report, I'm thinking about who's reading it.
The marketing manager wants different details than the CEO.

I never report metrics without business context. 'Citations increased 40%' is nice,
but 'Citations increased 40%, which correlates with the 25% increase in organic
demo requests' tells the story they need to hear.

Every report should answer: Is this working? What's next? Why should I care?""",
        )

    async def run(
        self,
        client_id: str,
        client_name: str,
        report_type: str,
        period: str,
        performance_data: dict,
        analysis_data: dict,
        strategy_data: dict | None = None,
    ) -> ClientReport:
        """
        Generate a client report.

        Args:
            client_id: Client ID
            client_name: Client name for personalization
            report_type: Type of report (weekly, monthly, quarterly)
            period: Period covered
            performance_data: Performance metrics and data
            analysis_data: Analysis insights
            strategy_data: Optional strategy context

        Returns:
            Complete ClientReport
        """
        self._log_task_start(
            "generate_report",
            client_id=client_id,
            report_type=report_type,
        )

        report = await self._generate_report(
            client_id,
            client_name,
            report_type,
            period,
            performance_data,
            analysis_data,
            strategy_data or {},
        )

        self._log_task_complete(
            "generate_report",
            sections=len(report.sections),
        )

        return report

    async def generate_alert(
        self,
        client_id: str,
        alert_data: dict,
        context: dict,
    ) -> AlertNotification:
        """
        Generate an alert notification.

        Args:
            client_id: Client ID
            alert_data: Data triggering the alert
            context: Additional context

        Returns:
            AlertNotification
        """
        self._log_task_start("generate_alert", client_id=client_id)

        alert = await self._generate_alert(client_id, alert_data, context)

        self._log_task_complete("generate_alert", severity=alert.severity)

        return alert

    async def _generate_report(
        self,
        client_id: str,
        client_name: str,
        report_type: str,
        period: str,
        performance: dict,
        analysis: dict,
        strategy: dict,
    ) -> ClientReport:
        """Generate report using LLM."""

        task_context = f"""You are The Reporter creating a {report_type} AEO report.

REPORT PRINCIPLES:
1. Lead with outcomes - Business results first, technical details second
2. Be specific - Use actual numbers, not vague improvements
3. Be balanced - Acknowledge challenges alongside wins
4. Be actionable - Every section should inform decisions
5. Be concise - Executives don't read walls of text

AUDIENCE CONTEXT:
- This is for {client_name}'s marketing/executive team
- They care about: Brand visibility, competitive position, ROI
- They don't care about: Technical implementation details, algorithm explanations

FORMAT:
- Executive summary should be 2-3 sentences max
- Each section should have clear takeaways
- Include specific next steps with priorities"""

        performance_str = str(performance)[:2500]
        analysis_str = str(analysis)[:2500]
        strategy_str = str(strategy)[:1000] if strategy else "No strategy data"

        prompt = f"""Generate a {report_type} AEO performance report:

CLIENT: {client_name}
PERIOD: {period}

PERFORMANCE DATA:
{performance_str}

ANALYSIS DATA:
{analysis_str}

STRATEGY CONTEXT:
{strategy_str}

Create the report as JSON:
{{
    "executive_summary": "2-3 sentence summary of performance and key takeaway",
    "key_metrics": {{
        "health_score": 0.0-1.0,
        "citation_rate": 0.0-1.0,
        "sentiment_score": -1.0 to 1.0,
        "visibility_score": 0.0-1.0,
        "month_over_month_change": percentage
    }},
    "wins": [
        "Specific win with data",
        "Another concrete achievement"
    ],
    "challenges": [
        "Challenge with context",
        "Another area needing attention"
    ],
    "sections": [
        {{
            "title": "Section Title",
            "content": "Section content explaining performance in business terms",
            "data_highlights": [
                {{"label": "Metric Name", "value": "Value with context"}}
            ],
            "visualization_type": "metric_card/chart/table/null",
            "visualization_data": {{}} or null
        }}
    ],
    "next_steps": [
        {{
            "priority": "high/medium/low",
            "action": "Specific action to take",
            "owner": "Team or person",
            "expected_impact": "What this will achieve"
        }}
    ]
}}

SECTION GUIDELINES:
1. AI Visibility Overview - How visible is the brand across AI engines
2. Citation Performance - Where and how often is the brand being cited
3. Sentiment Analysis - How is the brand being portrayed
4. Competitive Position - How does performance compare to competitors
5. Content Performance - Which content is driving results

Use business language, not technical jargon. Focus on what matters to executives.

Respond ONLY with the JSON object."""

        try:
            response = self._call_llm(prompt, task_context, max_tokens=4096)

            import json
            import re

            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())

                sections = [
                    ReportSection(
                        title=s.get("title", ""),
                        content=s.get("content", ""),
                        data_highlights=s.get("data_highlights", []),
                        visualization_type=s.get("visualization_type"),
                        visualization_data=s.get("visualization_data"),
                    )
                    for s in data.get("sections", [])
                ]

                return ClientReport(
                    client_id=client_id,
                    client_name=client_name,
                    report_type=report_type,
                    period=period,
                    executive_summary=data.get("executive_summary", ""),
                    key_metrics=data.get("key_metrics", {}),
                    sections=sections,
                    wins=data.get("wins", []),
                    challenges=data.get("challenges", []),
                    next_steps=data.get("next_steps", []),
                )

        except Exception as e:
            self._log.error("report_generation_failed", error=str(e))

        # Return minimal report on failure
        return ClientReport(
            client_id=client_id,
            client_name=client_name,
            report_type=report_type,
            period=period,
            executive_summary="Report generation encountered an error. Please contact support.",
            key_metrics={},
            sections=[],
            wins=[],
            challenges=["Report generation failed"],
            next_steps=[{"priority": "high", "action": "Contact support", "owner": "AEO Team"}],
        )

    async def _generate_alert(
        self,
        client_id: str,
        alert_data: dict,
        context: dict,
    ) -> AlertNotification:
        """Generate alert using LLM."""

        task_context = """You are The Reporter creating an alert notification.

ALERT PRINCIPLES:
1. Clear subject - What happened
2. Business impact - Why it matters
3. Recommended action - What to do about it
4. Appropriate urgency - Don't cry wolf"""

        prompt = f"""Generate an alert notification:

ALERT DATA:
{str(alert_data)[:1500]}

CONTEXT:
{str(context)[:500]}

Create the alert as JSON:
{{
    "alert_type": "positive/negative/informational",
    "severity": "critical/high/medium/low",
    "title": "Clear, concise title",
    "message": "2-3 sentence explanation of what happened and why it matters",
    "recommended_action": "What to do about it (null if informational)"
}}

Respond ONLY with the JSON object."""

        try:
            response = self._call_llm(prompt, task_context, max_tokens=1024)

            import json
            import re

            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())

                return AlertNotification(
                    client_id=client_id,
                    alert_type=data.get("alert_type", "informational"),
                    severity=data.get("severity", "medium"),
                    title=data.get("title", "Alert"),
                    message=data.get("message", ""),
                    data=alert_data,
                    recommended_action=data.get("recommended_action"),
                )

        except Exception as e:
            self._log.error("alert_generation_failed", error=str(e))

        return AlertNotification(
            client_id=client_id,
            alert_type="informational",
            severity="low",
            title="Alert",
            message="An event occurred that may require attention.",
            data=alert_data,
        )

    def format_metric_for_display(
        self,
        metric_name: str,
        value: float | int,
        previous_value: float | int | None = None,
    ) -> dict:
        """
        Format a metric for display with change indicator.

        Args:
            metric_name: Name of the metric
            value: Current value
            previous_value: Optional previous value for comparison

        Returns:
            Formatted metric dict
        """
        # Format value
        if isinstance(value, float) and value <= 1:
            formatted_value = f"{value:.1%}"
        elif isinstance(value, float):
            formatted_value = f"{value:.1f}"
        else:
            formatted_value = str(value)

        result = {
            "name": metric_name.replace("_", " ").title(),
            "value": formatted_value,
            "raw_value": value,
        }

        # Add change if previous value provided
        if previous_value is not None and previous_value != 0:
            change = ((value - previous_value) / previous_value) * 100
            result["change"] = round(change, 1)
            result["change_direction"] = "up" if change > 0 else "down" if change < 0 else "stable"
            result["change_formatted"] = f"{'+' if change > 0 else ''}{change:.1f}%"

        return result

    def generate_summary_stats(
        self,
        metrics: dict[str, float],
    ) -> list[dict]:
        """
        Generate summary statistics for dashboard display.

        Args:
            metrics: Dict of metric name to value

        Returns:
            List of formatted stats for display
        """
        stats = []

        priority_metrics = [
            ("health_score", "Overall Health"),
            ("citation_rate", "Citation Rate"),
            ("sentiment_score", "Sentiment"),
            ("visibility_score", "AI Visibility"),
        ]

        for key, label in priority_metrics:
            if key in metrics:
                value = metrics[key]
                if key == "sentiment_score":
                    # Convert -1 to 1 to display format
                    if value >= 0.3:
                        status = "positive"
                    elif value <= -0.3:
                        status = "negative"
                    else:
                        status = "neutral"
                    formatted = f"{value:+.2f}"
                else:
                    status = "good" if value >= 0.7 else "warning" if value >= 0.4 else "critical"
                    formatted = f"{value:.0%}"

                stats.append({
                    "label": label,
                    "value": formatted,
                    "status": status,
                })

        return stats
