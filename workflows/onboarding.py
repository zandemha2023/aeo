"""
Client onboarding workflow using LangGraph.

Orchestrates the initial intelligence gathering for a new client.
"""

from typing import TypedDict
from uuid import UUID

import structlog
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from agents.intelligence.cartographer import CartographerAgent
from db.queries import create_client, get_client_by_domain, create_monitoring_query
from knowledge.client_kb import ClientKnowledgeBase
from knowledge.schemas import ClientIntelligenceProfile

logger = structlog.get_logger()


class OnboardingState(TypedDict):
    """State for the onboarding workflow."""

    domain: str
    company_name: str
    additional_context: str
    client_id: str | None
    profile: ClientIntelligenceProfile | None
    queries_created: int
    errors: list[str]
    current_step: str


class OnboardingWorkflow:
    """
    LangGraph workflow for client onboarding.

    Steps:
    1. Create client record
    2. Run Cartographer to gather intelligence
    3. Generate monitoring queries
    4. Store results
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.cartographer = CartographerAgent()
        self._log = logger.bind(workflow="onboarding")

    def build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(OnboardingState)

        # Add nodes
        workflow.add_node("create_client", self.create_client)
        workflow.add_node("gather_intelligence", self.gather_intelligence)
        workflow.add_node("generate_queries", self.generate_queries)
        workflow.add_node("finalize", self.finalize)

        # Define edges
        workflow.set_entry_point("create_client")
        workflow.add_edge("create_client", "gather_intelligence")
        workflow.add_edge("gather_intelligence", "generate_queries")
        workflow.add_edge("generate_queries", "finalize")
        workflow.add_edge("finalize", END)

        return workflow.compile()

    async def create_client(self, state: OnboardingState) -> OnboardingState:
        """Create the client record in the database."""
        self._log.info("creating_client", domain=state["domain"])

        # Check if client already exists
        existing = await get_client_by_domain(self.session, state["domain"])

        if existing:
            self._log.info("client_exists", client_id=str(existing.id))
            state["client_id"] = str(existing.id)
        else:
            client = await create_client(
                self.session,
                state["company_name"],
                state["domain"],
            )
            state["client_id"] = str(client.id)
            self._log.info("client_created", client_id=str(client.id))

        state["current_step"] = "create_client"
        return state

    async def gather_intelligence(self, state: OnboardingState) -> OnboardingState:
        """Run the Cartographer agent to gather client intelligence."""
        self._log.info("gathering_intelligence", domain=state["domain"])

        try:
            profile = await self.cartographer.run(
                domain=state["domain"],
                company_name=state["company_name"],
                additional_context=state["additional_context"],
            )

            state["profile"] = profile

            # Store in knowledge base
            client_id = UUID(state["client_id"])
            kb = ClientKnowledgeBase(self.session, client_id)
            await kb.store_client_profile(profile)

            self._log.info(
                "intelligence_gathered",
                offerings=len(profile.offerings),
                audiences=len(profile.primary_audiences),
            )

        except Exception as e:
            error_msg = f"Intelligence gathering failed: {e}"
            state["errors"].append(error_msg)
            self._log.error("intelligence_failed", error=str(e))

        state["current_step"] = "gather_intelligence"
        return state

    async def generate_queries(self, state: OnboardingState) -> OnboardingState:
        """Generate monitoring queries based on the client profile."""
        self._log.info("generating_queries")

        if not state["profile"]:
            state["errors"].append("Cannot generate queries without profile")
            state["current_step"] = "generate_queries"
            return state

        client_id = UUID(state["client_id"])
        profile = state["profile"]
        queries_created = 0

        # Generate brand-related queries
        brand_queries = [
            (f"What is {state['company_name']}?", "brand"),
            (f"{state['company_name']} reviews", "review"),
            (f"Is {state['company_name']} good?", "brand"),
        ]

        # Generate product/service queries
        for offering in profile.offerings[:5]:  # Limit to top 5
            brand_queries.append(
                (f"Best {offering.name.lower()} tools", "category")
            )
            brand_queries.append(
                (f"What is {offering.name}?", "product")
            )

        # Generate category queries
        brand_queries.append(
            (f"Best {profile.category.lower()} software", "category")
        )

        # Generate comparison queries (placeholders for competitors)
        brand_queries.append(
            (f"{state['company_name']} alternatives", "comparison")
        )

        # Store queries
        for query_text, query_type in brand_queries:
            try:
                await create_monitoring_query(
                    self.session,
                    client_id,
                    query_text,
                    query_type,
                    priority=70 if query_type == "brand" else 50,
                )
                queries_created += 1
            except Exception as e:
                self._log.warning("query_creation_failed", query=query_text, error=str(e))

        state["queries_created"] = queries_created
        state["current_step"] = "generate_queries"

        self._log.info("queries_generated", count=queries_created)
        return state

    async def finalize(self, state: OnboardingState) -> OnboardingState:
        """Finalize the onboarding process."""
        self._log.info("finalizing_onboarding")

        state["current_step"] = "complete"

        self._log.info(
            "onboarding_complete",
            client_id=state["client_id"],
            queries_created=state["queries_created"],
            errors=len(state["errors"]),
        )

        return state


async def run_onboarding_workflow(
    session: AsyncSession,
    domain: str,
    company_name: str,
    additional_context: str = "",
) -> OnboardingState:
    """
    Run the onboarding workflow for a new client.

    Args:
        session: Database session
        domain: Client website domain
        company_name: Client company name
        additional_context: Optional additional context

    Returns:
        Final workflow state with results
    """
    logger.info("starting_onboarding_workflow", domain=domain)

    workflow = OnboardingWorkflow(session)
    graph = workflow.build_graph()

    initial_state: OnboardingState = {
        "domain": domain,
        "company_name": company_name,
        "additional_context": additional_context,
        "client_id": None,
        "profile": None,
        "queries_created": 0,
        "errors": [],
        "current_step": "initial",
    }

    # Run the workflow
    final_state = await graph.ainvoke(initial_state)

    logger.info(
        "onboarding_workflow_complete",
        domain=domain,
        client_id=final_state["client_id"],
    )

    return final_state
