"""
Strategy workflow using LangGraph.

Orchestrates the full intelligence gathering and strategy generation pipeline.
"""

import asyncio
from typing import TypedDict
from uuid import UUID

import structlog
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from agents.intelligence.cartographer import CartographerAgent
from agents.intelligence.scout import ScoutAgent
from agents.intelligence.librarian import LibrarianAgent
from agents.intelligence.auditor import AuditorAgent
from agents.strategic.strategist import StrategistAgent, AEOStrategy
from agents.strategic.architect import ArchitectAgent, ExecutionPlan
from db.queries import get_client, store_intelligence
from knowledge.client_kb import ClientKnowledgeBase
from knowledge.schemas import (
    ClientIntelligenceProfile,
    CompetitiveIntelligence,
    ContentAuthorityAnalysis,
    AEOPerformanceReport,
)

logger = structlog.get_logger()


class StrategyState(TypedDict):
    """State for the strategy workflow."""

    organization_id: str
    client_id: str
    domain: str
    company_name: str

    # Intelligence outputs
    client_profile: ClientIntelligenceProfile | None
    competitive_intel: CompetitiveIntelligence | None
    content_analysis: ContentAuthorityAnalysis | None
    performance_report: AEOPerformanceReport | None

    # Strategy outputs
    strategy: AEOStrategy | None
    execution_plans: list[ExecutionPlan]

    # Workflow state
    errors: list[str]
    current_step: str


class StrategyWorkflow:
    """
    LangGraph workflow for full strategy generation.

    Steps:
    1. Gather intelligence (parallel: Cartographer, Scout, Librarian, Auditor)
    2. Synthesize strategy (Strategist)
    3. Create execution plans (Architect)
    """

    def __init__(self, session: AsyncSession, organization_id: UUID):
        self.session = session
        self.organization_id = organization_id
        self.cartographer = CartographerAgent()
        self.scout = ScoutAgent()
        self.librarian = LibrarianAgent()
        self.auditor = AuditorAgent()
        self.strategist = StrategistAgent()
        self.architect = ArchitectAgent()
        self._log = logger.bind(
            workflow="strategy",
            organization_id=str(organization_id),
        )

    def build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(StrategyState)

        # Add nodes
        workflow.add_node("gather_intelligence", self.gather_intelligence)
        workflow.add_node("synthesize_strategy", self.synthesize_strategy)
        workflow.add_node("create_execution_plans", self.create_execution_plans)
        workflow.add_node("store_results", self.store_results)

        # Define edges
        workflow.set_entry_point("gather_intelligence")
        workflow.add_edge("gather_intelligence", "synthesize_strategy")
        workflow.add_edge("synthesize_strategy", "create_execution_plans")
        workflow.add_edge("create_execution_plans", "store_results")
        workflow.add_edge("store_results", END)

        return workflow.compile()

    async def gather_intelligence(self, state: StrategyState) -> StrategyState:
        """
        Gather all intelligence in parallel.

        Runs Cartographer, Scout, Librarian, and basic Auditor analysis.
        """
        self._log.info("gathering_intelligence", domain=state["domain"])

        # Get existing data if available
        client_id = UUID(state["client_id"])
        kb = ClientKnowledgeBase(self.session, self.organization_id, client_id)

        # Check for existing profile (may have been created during onboarding)
        existing_profile = await kb.get_client_profile()

        # Run intelligence gathering in parallel
        tasks = []

        # Cartographer (skip if profile exists)
        if existing_profile:
            state["client_profile"] = existing_profile
        else:
            tasks.append(("cartographer", self._run_cartographer(state)))

        # Get competitors from profile for Scout
        competitors = []
        if existing_profile:
            # Generate competitor list from category
            competitors = [
                {"name": f"{existing_profile.category} Competitor 1", "domain": "example.com"},
            ]

        # Scout
        tasks.append(("scout", self._run_scout(state, competitors)))

        # Librarian
        tasks.append(("librarian", self._run_librarian(state)))

        # Run parallel tasks
        if tasks:
            results = await asyncio.gather(
                *[t[1] for t in tasks],
                return_exceptions=True,
            )

            for i, (name, _) in enumerate(tasks):
                result = results[i]
                if isinstance(result, Exception):
                    state["errors"].append(f"{name} failed: {result}")
                    self._log.error(f"{name}_failed", error=str(result))
                else:
                    if name == "cartographer":
                        state["client_profile"] = result
                    elif name == "scout":
                        state["competitive_intel"] = result
                    elif name == "librarian":
                        state["content_analysis"] = result

        # Run Auditor (needs existing data)
        try:
            mentions = await kb.get_recent_mentions(hours=168)  # Last week
            performance = await self.auditor.run(
                mentions=mentions,
                industry=state["client_profile"].category if state["client_profile"] else "",
            )
            state["performance_report"] = performance
        except Exception as e:
            state["errors"].append(f"auditor failed: {e}")
            self._log.error("auditor_failed", error=str(e))

        state["current_step"] = "gather_intelligence"
        self._log.info(
            "intelligence_gathered",
            has_profile=state["client_profile"] is not None,
            has_competitive=state["competitive_intel"] is not None,
            has_content=state["content_analysis"] is not None,
            has_performance=state["performance_report"] is not None,
        )

        return state

    async def _run_cartographer(self, state: StrategyState) -> ClientIntelligenceProfile:
        """Run Cartographer agent."""
        return await self.cartographer.run(
            domain=state["domain"],
            company_name=state["company_name"],
        )

    async def _run_scout(
        self,
        state: StrategyState,
        competitors: list[dict],
    ) -> CompetitiveIntelligence:
        """Run Scout agent."""
        # Generate category queries
        category_queries = [
            f"Best {state['company_name']} alternatives",
            f"What is {state['company_name']}?",
        ]

        return await self.scout.run(
            client_name=state["company_name"],
            client_domain=state["domain"],
            competitors=competitors,
            category_queries=category_queries,
        )

    async def _run_librarian(self, state: StrategyState) -> ContentAuthorityAnalysis:
        """Run Librarian agent."""
        topics = []
        if state.get("client_profile"):
            topics = state["client_profile"].topics_of_authority

        return await self.librarian.run(
            domain=state["domain"],
            company_name=state["company_name"],
            topics_of_authority=topics,
            target_queries=[],
        )

    async def synthesize_strategy(self, state: StrategyState) -> StrategyState:
        """Synthesize strategy from all intelligence."""
        self._log.info("synthesizing_strategy")

        if not state["client_profile"] or not state["performance_report"]:
            state["errors"].append("Missing required intelligence for strategy")
            state["current_step"] = "synthesize_strategy"
            return state

        try:
            strategy = await self.strategist.run(
                client_profile=state["client_profile"],
                performance_report=state["performance_report"],
                competitive_intel=state["competitive_intel"],
                content_analysis=state["content_analysis"],
            )
            state["strategy"] = strategy

            self._log.info(
                "strategy_synthesized",
                priorities=len(strategy.priorities),
            )

        except Exception as e:
            state["errors"].append(f"strategy synthesis failed: {e}")
            self._log.error("strategy_synthesis_failed", error=str(e))

        state["current_step"] = "synthesize_strategy"
        return state

    async def create_execution_plans(self, state: StrategyState) -> StrategyState:
        """Create execution plans for top priorities."""
        self._log.info("creating_execution_plans")

        if not state["strategy"] or not state["client_profile"]:
            state["errors"].append("Missing strategy or profile for execution planning")
            state["current_step"] = "create_execution_plans"
            return state

        execution_plans = []
        content_gaps = state["content_analysis"].content_gaps if state["content_analysis"] else []

        # Create plan for top 3 priorities
        for priority in state["strategy"].priorities[:3]:
            try:
                plan = await self.architect.run(
                    strategic_priority=priority.to_dict(),
                    client_profile=state["client_profile"],
                    content_gaps=content_gaps,
                )
                execution_plans.append(plan)

            except Exception as e:
                state["errors"].append(f"execution plan failed: {e}")
                self._log.error("execution_plan_failed", priority=priority.priority, error=str(e))

        state["execution_plans"] = execution_plans
        state["current_step"] = "create_execution_plans"

        self._log.info(
            "execution_plans_created",
            plans=len(execution_plans),
        )

        return state

    async def store_results(self, state: StrategyState) -> StrategyState:
        """Store all results in the database."""
        self._log.info("storing_results")

        client_id = UUID(state["client_id"])

        # Store intelligence
        if state["client_profile"]:
            await store_intelligence(
                self.session,
                self.organization_id,
                client_id,
                "cartographer",
                state["client_profile"].model_dump(mode="json"),
            )

        if state["competitive_intel"]:
            await store_intelligence(
                self.session,
                self.organization_id,
                client_id,
                "scout",
                state["competitive_intel"].model_dump(mode="json"),
            )

        if state["content_analysis"]:
            await store_intelligence(
                self.session,
                self.organization_id,
                client_id,
                "librarian",
                state["content_analysis"].model_dump(mode="json"),
            )

        if state["performance_report"]:
            await store_intelligence(
                self.session,
                self.organization_id,
                client_id,
                "auditor",
                state["performance_report"].model_dump(mode="json"),
            )

        # Store strategy
        if state["strategy"]:
            await store_intelligence(
                self.session,
                self.organization_id,
                client_id,
                "strategist",
                state["strategy"].to_dict(),
            )

        # Store execution plans
        if state["execution_plans"]:
            await store_intelligence(
                self.session,
                self.organization_id,
                client_id,
                "architect",
                {"plans": [p.to_dict() for p in state["execution_plans"]]},
            )

        state["current_step"] = "store_results"
        self._log.info("results_stored")

        return state


async def run_strategy_workflow(
    session: AsyncSession,
    organization_id: UUID,
    client_id: UUID,
) -> StrategyState:
    """
    Run the full strategy workflow for a client.

    Args:
        session: Database session
        organization_id: Organization UUID (tenant)
        client_id: Client UUID

    Returns:
        Final workflow state with strategy and execution plans
    """
    logger.info(
        "starting_strategy_workflow",
        organization_id=str(organization_id),
        client_id=str(client_id),
    )

    # Get client info
    client = await get_client(session, organization_id, client_id)
    if not client:
        raise ValueError(f"Client not found: {client_id}")

    workflow = StrategyWorkflow(session, organization_id)
    graph = workflow.build_graph()

    initial_state: StrategyState = {
        "organization_id": str(organization_id),
        "client_id": str(client_id),
        "domain": client.domain,
        "company_name": client.name,
        "client_profile": None,
        "competitive_intel": None,
        "content_analysis": None,
        "performance_report": None,
        "strategy": None,
        "execution_plans": [],
        "errors": [],
        "current_step": "initial",
    }

    # Run the workflow
    final_state = await graph.ainvoke(initial_state)

    logger.info(
        "strategy_workflow_complete",
        client_id=str(client_id),
        has_strategy=final_state["strategy"] is not None,
        execution_plans=len(final_state["execution_plans"]),
        errors=len(final_state["errors"]),
    )

    return final_state
