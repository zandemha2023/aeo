"""
Analytics and reporting workflow using LangGraph.

Orchestrates data analysis, technical audits, and report generation.
"""

from typing import TypedDict
from uuid import UUID

import structlog
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from agents.execution.builder import BuilderAgent, TechnicalAudit
from agents.execution.engineer import EngineerAgent, SchemaAuditResult
from agents.execution.analyst import AnalystAgent, PerformanceAnalysis
from agents.execution.reporter import ReporterAgent, ClientReport
from db.queries import get_client, get_latest_intelligence, store_intelligence

logger = structlog.get_logger()


class AnalyticsState(TypedDict):
    """State for the analytics workflow."""

    client_id: str
    client_name: str
    domain: str
    report_type: str  # weekly, monthly, quarterly, technical

    # Input data
    performance_reports: list[dict]
    mentions: list[dict]
    competitor_data: list[dict]

    # Generated analysis
    performance_analysis: dict | None
    technical_audit: dict | None
    schema_audit: dict | None

    # Output
    client_report: dict | None

    # Workflow state
    errors: list[str]
    current_step: str


class AnalyticsWorkflow:
    """
    LangGraph workflow for analytics and reporting.

    Steps:
    1. Load performance data
    2. Run performance analysis
    3. Run technical audit (optional)
    4. Generate client report
    5. Store results
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.analyst = AnalystAgent()
        self.builder = BuilderAgent()
        self.engineer = EngineerAgent()
        self.reporter = ReporterAgent()
        self._log = logger.bind(workflow="analytics")

    def build_graph(self, include_technical: bool = False) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(AnalyticsState)

        # Add nodes
        workflow.add_node("load_data", self.load_data)
        workflow.add_node("analyze_performance", self.analyze_performance)
        workflow.add_node("generate_report", self.generate_report)
        workflow.add_node("store_results", self.store_results)

        if include_technical:
            workflow.add_node("run_technical_audit", self.run_technical_audit)
            workflow.add_node("run_schema_audit", self.run_schema_audit)

        # Define edges
        workflow.set_entry_point("load_data")
        workflow.add_edge("load_data", "analyze_performance")

        if include_technical:
            workflow.add_edge("analyze_performance", "run_technical_audit")
            workflow.add_edge("run_technical_audit", "run_schema_audit")
            workflow.add_edge("run_schema_audit", "generate_report")
        else:
            workflow.add_edge("analyze_performance", "generate_report")

        workflow.add_edge("generate_report", "store_results")
        workflow.add_edge("store_results", END)

        return workflow.compile()

    async def load_data(self, state: AnalyticsState) -> AnalyticsState:
        """Load performance data from database."""
        self._log.info("loading_data", client_id=state["client_id"])

        client_id = UUID(state["client_id"])

        # Load performance reports
        perf_intel = await get_latest_intelligence(
            self.session,
            client_id,
            "performance_report",
        )
        if perf_intel:
            state["performance_reports"] = [perf_intel.data]

        # Load mentions
        mentions_intel = await get_latest_intelligence(
            self.session,
            client_id,
            "brand_mentions",
        )
        if mentions_intel:
            state["mentions"] = mentions_intel.data.get("mentions", [])

        # Load competitor data
        competitor_intel = await get_latest_intelligence(
            self.session,
            client_id,
            "competitive_intelligence",
        )
        if competitor_intel:
            state["competitor_data"] = [competitor_intel.data]

        state["current_step"] = "load_data"
        self._log.info(
            "data_loaded",
            reports=len(state["performance_reports"]),
            mentions=len(state["mentions"]),
        )

        return state

    async def analyze_performance(self, state: AnalyticsState) -> AnalyticsState:
        """Run performance analysis."""
        self._log.info("analyzing_performance")

        try:
            analysis = await self.analyst.run(
                client_id=state["client_id"],
                performance_reports=state["performance_reports"],
                mentions=state["mentions"],
                competitor_data=state["competitor_data"],
                analysis_period=state["report_type"],
            )
            state["performance_analysis"] = analysis.to_dict()

        except Exception as e:
            self._log.error("analysis_failed", error=str(e))
            state["errors"].append(f"Performance analysis failed: {e}")

        state["current_step"] = "analyze_performance"
        return state

    async def run_technical_audit(self, state: AnalyticsState) -> AnalyticsState:
        """Run technical SEO audit."""
        self._log.info("running_technical_audit", domain=state["domain"])

        if not state["domain"]:
            state["errors"].append("No domain provided for technical audit")
            state["current_step"] = "run_technical_audit"
            return state

        try:
            audit = await self.builder.run(
                domain=state["domain"],
            )
            state["technical_audit"] = audit.to_dict()

        except Exception as e:
            self._log.error("technical_audit_failed", error=str(e))
            state["errors"].append(f"Technical audit failed: {e}")

        state["current_step"] = "run_technical_audit"
        return state

    async def run_schema_audit(self, state: AnalyticsState) -> AnalyticsState:
        """Run schema markup audit."""
        self._log.info("running_schema_audit", domain=state["domain"])

        if not state["domain"]:
            state["errors"].append("No domain provided for schema audit")
            state["current_step"] = "run_schema_audit"
            return state

        try:
            audit = await self.engineer.audit_schemas(
                url=f"https://{state['domain']}",
            )
            state["schema_audit"] = audit.to_dict()

        except Exception as e:
            self._log.error("schema_audit_failed", error=str(e))
            state["errors"].append(f"Schema audit failed: {e}")

        state["current_step"] = "run_schema_audit"
        return state

    async def generate_report(self, state: AnalyticsState) -> AnalyticsState:
        """Generate client report."""
        self._log.info("generating_report", report_type=state["report_type"])

        # Compile strategy data from audits if available
        strategy_data = {}
        if state.get("technical_audit"):
            strategy_data["technical_audit"] = state["technical_audit"]
        if state.get("schema_audit"):
            strategy_data["schema_audit"] = state["schema_audit"]

        try:
            report = await self.reporter.run(
                client_id=state["client_id"],
                client_name=state["client_name"],
                report_type=state["report_type"],
                period=state["report_type"],
                performance_data={
                    "reports": state["performance_reports"],
                    "mentions": state["mentions"][:20],
                },
                analysis_data=state.get("performance_analysis", {}),
                strategy_data=strategy_data if strategy_data else None,
            )
            state["client_report"] = report.to_dict()

        except Exception as e:
            self._log.error("report_generation_failed", error=str(e))
            state["errors"].append(f"Report generation failed: {e}")

        state["current_step"] = "generate_report"
        return state

    async def store_results(self, state: AnalyticsState) -> AnalyticsState:
        """Store analytics results."""
        self._log.info("storing_results")

        client_id = UUID(state["client_id"])

        # Store analysis
        if state.get("performance_analysis"):
            await store_intelligence(
                self.session,
                client_id,
                "performance_analysis",
                state["performance_analysis"],
            )

        # Store technical audit
        if state.get("technical_audit"):
            await store_intelligence(
                self.session,
                client_id,
                "technical_audit",
                state["technical_audit"],
            )

        # Store schema audit
        if state.get("schema_audit"):
            await store_intelligence(
                self.session,
                client_id,
                "schema_audit",
                state["schema_audit"],
            )

        # Store report
        if state.get("client_report"):
            await store_intelligence(
                self.session,
                client_id,
                f"client_report_{state['report_type']}",
                state["client_report"],
            )

        state["current_step"] = "store_results"
        return state


class TechnicalAuditState(TypedDict):
    """State for standalone technical audit workflow."""

    client_id: str
    domain: str
    robots_txt: str | None
    sitemap: str | None
    sample_urls: list[str]

    # Outputs
    technical_audit: dict | None
    schema_audit: dict | None
    combined_recommendations: list[dict]

    # Workflow state
    errors: list[str]
    current_step: str


class TechnicalAuditWorkflow:
    """
    LangGraph workflow for comprehensive technical audit.

    Steps:
    1. Run technical SEO audit
    2. Run schema audit
    3. Combine recommendations
    4. Store results
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.builder = BuilderAgent()
        self.engineer = EngineerAgent()
        self._log = logger.bind(workflow="technical_audit")

    def build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(TechnicalAuditState)

        workflow.add_node("technical_audit", self.run_technical_audit)
        workflow.add_node("schema_audit", self.run_schema_audit)
        workflow.add_node("combine_recommendations", self.combine_recommendations)
        workflow.add_node("store_results", self.store_results)

        workflow.set_entry_point("technical_audit")
        workflow.add_edge("technical_audit", "schema_audit")
        workflow.add_edge("schema_audit", "combine_recommendations")
        workflow.add_edge("combine_recommendations", "store_results")
        workflow.add_edge("store_results", END)

        return workflow.compile()

    async def run_technical_audit(self, state: TechnicalAuditState) -> TechnicalAuditState:
        """Run technical SEO audit."""
        self._log.info("running_technical_audit", domain=state["domain"])

        try:
            audit = await self.builder.run(
                domain=state["domain"],
                sample_urls=state.get("sample_urls"),
                robots_txt_content=state.get("robots_txt"),
                sitemap_content=state.get("sitemap"),
            )
            state["technical_audit"] = audit.to_dict()

        except Exception as e:
            self._log.error("technical_audit_failed", error=str(e))
            state["errors"].append(f"Technical audit failed: {e}")

        state["current_step"] = "technical_audit"
        return state

    async def run_schema_audit(self, state: TechnicalAuditState) -> TechnicalAuditState:
        """Run schema audit."""
        self._log.info("running_schema_audit")

        try:
            audit = await self.engineer.audit_schemas(
                url=f"https://{state['domain']}",
            )
            state["schema_audit"] = audit.to_dict()

        except Exception as e:
            self._log.error("schema_audit_failed", error=str(e))
            state["errors"].append(f"Schema audit failed: {e}")

        state["current_step"] = "schema_audit"
        return state

    async def combine_recommendations(self, state: TechnicalAuditState) -> TechnicalAuditState:
        """Combine recommendations from both audits."""
        self._log.info("combining_recommendations")

        recommendations = []

        # Add technical recommendations
        if state.get("technical_audit"):
            for fix in state["technical_audit"].get("priority_fixes", []):
                recommendations.append({
                    "source": "technical",
                    "priority": fix.get("priority", 99),
                    "recommendation": fix.get("fix", ""),
                    "impact": fix.get("impact", ""),
                    "effort": fix.get("effort", "medium"),
                })

        # Add schema recommendations
        if state.get("schema_audit"):
            for addition in state["schema_audit"].get("priority_additions", []):
                recommendations.append({
                    "source": "schema",
                    "priority": addition.get("priority", 99),
                    "recommendation": f"Add {addition.get('schema_type', '')} schema",
                    "impact": addition.get("reason", ""),
                    "effort": "low",
                })

        # Sort by priority
        recommendations.sort(key=lambda x: x.get("priority", 99))

        state["combined_recommendations"] = recommendations
        state["current_step"] = "combine_recommendations"
        return state

    async def store_results(self, state: TechnicalAuditState) -> TechnicalAuditState:
        """Store audit results."""
        self._log.info("storing_results")

        client_id = UUID(state["client_id"])

        await store_intelligence(
            self.session,
            client_id,
            "full_technical_audit",
            {
                "domain": state["domain"],
                "technical_audit": state.get("technical_audit"),
                "schema_audit": state.get("schema_audit"),
                "combined_recommendations": state["combined_recommendations"],
            },
        )

        state["current_step"] = "store_results"
        return state


async def run_analytics_workflow(
    session: AsyncSession,
    client_id: UUID,
    client_name: str,
    domain: str,
    report_type: str = "monthly",
    include_technical: bool = False,
) -> AnalyticsState:
    """
    Run the analytics and reporting workflow.

    Args:
        session: Database session
        client_id: Client UUID
        client_name: Client name
        domain: Client domain
        report_type: Type of report to generate
        include_technical: Whether to include technical audits

    Returns:
        Final workflow state
    """
    logger.info(
        "starting_analytics_workflow",
        client_id=str(client_id),
        report_type=report_type,
    )

    workflow = AnalyticsWorkflow(session)
    graph = workflow.build_graph(include_technical=include_technical)

    initial_state: AnalyticsState = {
        "client_id": str(client_id),
        "client_name": client_name,
        "domain": domain,
        "report_type": report_type,
        "performance_reports": [],
        "mentions": [],
        "competitor_data": [],
        "performance_analysis": None,
        "technical_audit": None,
        "schema_audit": None,
        "client_report": None,
        "errors": [],
        "current_step": "initial",
    }

    final_state = await graph.ainvoke(initial_state)

    logger.info(
        "analytics_workflow_complete",
        client_id=str(client_id),
        has_report=final_state.get("client_report") is not None,
    )

    return final_state


async def run_technical_audit_workflow(
    session: AsyncSession,
    client_id: UUID,
    domain: str,
    robots_txt: str | None = None,
    sitemap: str | None = None,
    sample_urls: list[str] | None = None,
) -> TechnicalAuditState:
    """
    Run the technical audit workflow.

    Args:
        session: Database session
        client_id: Client UUID
        domain: Domain to audit
        robots_txt: robots.txt content if available
        sitemap: Sitemap content if available
        sample_urls: Sample URLs to analyze

    Returns:
        Final workflow state
    """
    logger.info("starting_technical_audit_workflow", domain=domain)

    workflow = TechnicalAuditWorkflow(session)
    graph = workflow.build_graph()

    initial_state: TechnicalAuditState = {
        "client_id": str(client_id),
        "domain": domain,
        "robots_txt": robots_txt,
        "sitemap": sitemap,
        "sample_urls": sample_urls or [],
        "technical_audit": None,
        "schema_audit": None,
        "combined_recommendations": [],
        "errors": [],
        "current_step": "initial",
    }

    final_state = await graph.ainvoke(initial_state)

    logger.info(
        "technical_audit_workflow_complete",
        domain=domain,
        recommendations=len(final_state["combined_recommendations"]),
    )

    return final_state
