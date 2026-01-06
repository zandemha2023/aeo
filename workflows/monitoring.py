"""
Monitoring workflow using LangGraph.

Orchestrates the continuous monitoring of brand mentions across AI engines.
"""

import asyncio
from datetime import datetime
from typing import Any, TypedDict
from uuid import UUID

import structlog
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from agents.intelligence.auditor import AuditorAgent
from db.queries import (
    get_client,
    get_monitoring_queries,
    store_monitoring_result,
    create_alert,
    store_performance_snapshot,
)
from engine.query import query_all_engines
from engine.parse import parse_response, calculate_mention_quality_score
from knowledge.client_kb import ClientKnowledgeBase
from knowledge.schemas import (
    AIQuery,
    AIResponse,
    AEOPerformanceReport,
    BrandMention,
    Severity,
)

logger = structlog.get_logger()


class MonitoringState(TypedDict):
    """State for the monitoring workflow."""

    organization_id: str
    client_id: str
    queries: list[AIQuery]
    responses: list[AIResponse]
    mentions: list[BrandMention]
    report: AEOPerformanceReport | None
    alerts_created: list[str]
    errors: list[str]
    current_step: str


class MonitoringWorkflow:
    """
    LangGraph workflow for AEO monitoring.

    Steps:
    1. Load monitoring queries for client
    2. Query all AI engines in parallel
    3. Parse responses and extract mentions
    4. Analyze with Auditor agent
    5. Store results and create alerts
    """

    def __init__(self, session: AsyncSession, organization_id: UUID):
        self.session = session
        self.organization_id = organization_id
        self.auditor = AuditorAgent()
        self._log = logger.bind(
            workflow="monitoring",
            organization_id=str(organization_id),
        )

    def build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(MonitoringState)

        # Add nodes
        workflow.add_node("load_queries", self.load_queries)
        workflow.add_node("query_engines", self.query_engines)
        workflow.add_node("parse_responses", self.parse_responses)
        workflow.add_node("analyze_performance", self.analyze_performance)
        workflow.add_node("store_results", self.store_results)
        workflow.add_node("create_alerts", self.create_alerts)

        # Define edges
        workflow.set_entry_point("load_queries")
        workflow.add_edge("load_queries", "query_engines")
        workflow.add_edge("query_engines", "parse_responses")
        workflow.add_edge("parse_responses", "analyze_performance")
        workflow.add_edge("analyze_performance", "store_results")
        workflow.add_edge("store_results", "create_alerts")
        workflow.add_edge("create_alerts", END)

        return workflow.compile()

    async def load_queries(self, state: MonitoringState) -> MonitoringState:
        """Load monitoring queries for the client."""
        self._log.info("loading_queries", client_id=state["client_id"])

        client_id = UUID(state["client_id"])
        kb = ClientKnowledgeBase(self.session, self.organization_id, client_id)

        queries = await kb.get_monitoring_queries()

        state["queries"] = queries
        state["current_step"] = "load_queries"

        self._log.info("queries_loaded", count=len(queries))
        return state

    async def query_engines(self, state: MonitoringState) -> MonitoringState:
        """Query all AI engines with the monitoring queries."""
        self._log.info("querying_engines", query_count=len(state["queries"]))

        all_responses = []
        errors = []

        # Query engines in parallel for each query
        for query in state["queries"]:
            try:
                responses = await query_all_engines(query)
                all_responses.extend(responses)
            except Exception as e:
                errors.append(f"Query '{query.query_text[:50]}...' failed: {e}")
                self._log.error("query_failed", query=query.query_text[:50], error=str(e))

        state["responses"] = all_responses
        state["errors"].extend(errors)
        state["current_step"] = "query_engines"

        self._log.info(
            "engines_queried",
            responses=len(all_responses),
            errors=len(errors),
        )
        return state

    async def parse_responses(self, state: MonitoringState) -> MonitoringState:
        """Parse responses and extract brand mentions."""
        self._log.info("parsing_responses", response_count=len(state["responses"]))

        mentions = []

        # Get query for each response (responses are in order of queries * engines)
        queries = state["queries"]
        engines = ["chatgpt", "claude", "perplexity", "gemini"]

        for i, response in enumerate(state["responses"]):
            if response.error:
                continue

            # Find the corresponding query
            query_idx = i // len(engines)
            if query_idx < len(queries):
                query = queries[query_idx]

                # Parse the response using LLM analysis
                mention = await parse_response(response, query)
                mentions.append(mention)

        state["mentions"] = mentions
        state["current_step"] = "parse_responses"

        self._log.info(
            "responses_parsed",
            mentions_found=sum(1 for m in mentions if m.mentioned),
        )
        return state

    async def analyze_performance(self, state: MonitoringState) -> MonitoringState:
        """Analyze performance with the Auditor agent."""
        self._log.info("analyzing_performance")

        client_id = UUID(state["client_id"])
        client = await get_client(self.session, self.organization_id, client_id)
        industry = client.industry if client else ""

        # Get previous metrics for trend analysis
        kb = ClientKnowledgeBase(self.session, self.organization_id, client_id)
        previous_report = await kb.get_performance_report()
        previous_metrics = previous_report.metrics if previous_report else None

        # Run auditor analysis
        report = await self.auditor.run(
            mentions=state["mentions"],
            industry=industry,
            previous_metrics=previous_metrics,
        )

        state["report"] = report
        state["current_step"] = "analyze_performance"

        self._log.info(
            "performance_analyzed",
            health_score=report.overall_health_score,
            grade=report.health_grade.value,
        )
        return state

    async def store_results(self, state: MonitoringState) -> MonitoringState:
        """Store monitoring results in the database."""
        self._log.info("storing_results")

        client_id = UUID(state["client_id"])
        kb = ClientKnowledgeBase(self.session, self.organization_id, client_id)

        # Store the performance report
        if state["report"]:
            await kb.store_performance_report(state["report"])

            # Also store a snapshot for historical tracking
            await store_performance_snapshot(
                self.session,
                self.organization_id,
                client_id,
                state["report"].metrics.model_dump(),
                {"timestamp": datetime.utcnow().isoformat()},
            )

        # Store individual mention results
        queries = await get_monitoring_queries(
            self.session, self.organization_id, client_id
        )
        query_map = {q.query: q.id for q in queries}

        for mention in state["mentions"]:
            query_id = query_map.get(mention.query)
            if query_id:
                await store_monitoring_result(
                    self.session,
                    self.organization_id,
                    client_id,
                    query_id,
                    mention.engine,
                    mention.response_text,
                    mention.mentioned,
                    mention.position,
                    mention.recommended,
                    mention.sentiment,
                    mention.accuracy,
                    mention.sources_cited,
                    mention.competitors_mentioned,
                    calculate_mention_quality_score(mention),
                )

        state["current_step"] = "store_results"
        self._log.info("results_stored")
        return state

    async def create_alerts(self, state: MonitoringState) -> MonitoringState:
        """Create alerts for significant issues."""
        self._log.info("creating_alerts")

        client_id = UUID(state["client_id"])
        alerts_created = []

        if state["report"]:
            for issue in state["report"].issues:
                if issue.severity in [Severity.CRITICAL, Severity.WARNING]:
                    alert = await create_alert(
                        self.session,
                        self.organization_id,
                        client_id,
                        issue.severity.value,
                        "performance_issue",
                        issue.issue,
                        {
                            "evidence": issue.evidence,
                            "recommended_action": issue.recommended_action,
                        },
                    )
                    alerts_created.append(str(alert.id))
                    self._log.info(
                        "alert_created",
                        severity=issue.severity.value,
                        issue=issue.issue,
                    )

        state["alerts_created"] = alerts_created
        state["current_step"] = "create_alerts"

        self._log.info("alerts_created", count=len(alerts_created))
        return state


async def run_monitoring_workflow(
    session: AsyncSession,
    organization_id: UUID,
    client_id: UUID,
) -> MonitoringState:
    """
    Run the monitoring workflow for a client.

    Args:
        session: Database session
        organization_id: Organization UUID (tenant)
        client_id: Client UUID

    Returns:
        Final workflow state with results
    """
    logger.info(
        "starting_monitoring_workflow",
        organization_id=str(organization_id),
        client_id=str(client_id),
    )

    workflow = MonitoringWorkflow(session, organization_id)
    graph = workflow.build_graph()

    initial_state: MonitoringState = {
        "organization_id": str(organization_id),
        "client_id": str(client_id),
        "queries": [],
        "responses": [],
        "mentions": [],
        "report": None,
        "alerts_created": [],
        "errors": [],
        "current_step": "initial",
    }

    # Run the workflow
    final_state = await graph.ainvoke(initial_state)

    logger.info(
        "monitoring_workflow_complete",
        client_id=str(client_id),
        mentions=len(final_state["mentions"]),
        alerts=len(final_state["alerts_created"]),
    )

    return final_state
