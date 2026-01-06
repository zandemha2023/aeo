"""
Content creation workflow using LangGraph.

Orchestrates content creation from blueprints with quality gates.
"""

import asyncio
from typing import TypedDict
from uuid import UUID

import structlog
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from agents.execution.writer import WriterAgent, GeneratedContent
from agents.execution.optimizer import OptimizerAgent, ContentOptimization
from actions.quality_gates import (
    run_content_quality_gates,
    run_optimization_quality_gates,
    QualityGateReport,
)
from db.queries import get_client, get_latest_intelligence, store_intelligence
from knowledge.client_kb import ClientKnowledgeBase
from knowledge.schemas import ClientIntelligenceProfile

logger = structlog.get_logger()


class ContentState(TypedDict):
    """State for the content workflow."""

    client_id: str
    blueprints: list[dict]
    client_profile: ClientIntelligenceProfile | None

    # Outputs
    generated_content: list[dict]
    quality_reports: list[dict]
    failed_content: list[dict]

    # Workflow state
    current_blueprint_index: int
    errors: list[str]
    current_step: str


class ContentWorkflow:
    """
    LangGraph workflow for content creation.

    Steps:
    1. Load client profile and blueprints
    2. Generate content for each blueprint
    3. Run quality gates
    4. Store approved content
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.writer = WriterAgent()
        self._log = logger.bind(workflow="content")

    def build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(ContentState)

        # Add nodes
        workflow.add_node("load_context", self.load_context)
        workflow.add_node("generate_content", self.generate_content)
        workflow.add_node("run_quality_gates", self.run_quality_gates)
        workflow.add_node("store_results", self.store_results)

        # Define edges
        workflow.set_entry_point("load_context")
        workflow.add_edge("load_context", "generate_content")
        workflow.add_edge("generate_content", "run_quality_gates")
        workflow.add_edge("run_quality_gates", "store_results")
        workflow.add_edge("store_results", END)

        return workflow.compile()

    async def load_context(self, state: ContentState) -> ContentState:
        """Load client profile and blueprints."""
        self._log.info("loading_context", client_id=state["client_id"])

        client_id = UUID(state["client_id"])
        kb = ClientKnowledgeBase(self.session, client_id)

        # Load client profile
        profile = await kb.get_client_profile()
        state["client_profile"] = profile

        # Load blueprints from architect output if not provided
        if not state["blueprints"]:
            architect_intel = await get_latest_intelligence(
                self.session,
                client_id,
                "architect",
            )
            if architect_intel:
                plans = architect_intel.data.get("plans", [])
                blueprints = []
                for plan in plans:
                    for initiative in plan.get("initiatives", []):
                        blueprints.extend(initiative.get("content_pieces", []))
                state["blueprints"] = blueprints

        state["current_step"] = "load_context"
        self._log.info(
            "context_loaded",
            has_profile=profile is not None,
            blueprints=len(state["blueprints"]),
        )

        return state

    async def generate_content(self, state: ContentState) -> ContentState:
        """Generate content for each blueprint."""
        self._log.info("generating_content", count=len(state["blueprints"]))

        if not state["client_profile"]:
            state["errors"].append("No client profile available")
            state["current_step"] = "generate_content"
            return state

        generated = []
        errors = []

        for i, blueprint in enumerate(state["blueprints"]):
            self._log.info(
                "generating_piece",
                index=i,
                title=blueprint.get("title", ""),
            )

            try:
                content = await self.writer.run(
                    blueprint=blueprint,
                    client_profile=state["client_profile"],
                )
                generated.append({
                    "blueprint": blueprint,
                    "content": content.to_dict(),
                    "status": "generated",
                })

            except Exception as e:
                self._log.error(
                    "content_generation_failed",
                    index=i,
                    error=str(e),
                )
                errors.append(f"Blueprint {i} failed: {e}")
                generated.append({
                    "blueprint": blueprint,
                    "content": None,
                    "status": "failed",
                    "error": str(e),
                })

        state["generated_content"] = generated
        state["errors"].extend(errors)
        state["current_step"] = "generate_content"

        self._log.info(
            "content_generation_complete",
            generated=len([g for g in generated if g["status"] == "generated"]),
            failed=len([g for g in generated if g["status"] == "failed"]),
        )

        return state

    async def run_quality_gates(self, state: ContentState) -> ContentState:
        """Run quality gates on generated content."""
        self._log.info("running_quality_gates")

        quality_reports = []
        failed_content = []

        for item in state["generated_content"]:
            if item["status"] != "generated" or not item["content"]:
                failed_content.append(item)
                continue

            report = run_content_quality_gates(
                content=item["content"],
                blueprint=item["blueprint"],
                client_profile=state["client_profile"],
            )

            quality_reports.append({
                "title": item["content"].get("title", ""),
                "report": report.to_dict(),
            })

            if not report.overall_passed:
                failed_content.append({
                    **item,
                    "status": "failed_quality_gates",
                    "quality_report": report.to_dict(),
                })

        state["quality_reports"] = quality_reports
        state["failed_content"] = failed_content
        state["current_step"] = "run_quality_gates"

        passed = len([r for r in quality_reports if r["report"]["overall_passed"]])
        self._log.info(
            "quality_gates_complete",
            total=len(quality_reports),
            passed=passed,
            failed=len(failed_content),
        )

        return state

    async def store_results(self, state: ContentState) -> ContentState:
        """Store generated content and reports."""
        self._log.info("storing_results")

        client_id = UUID(state["client_id"])

        # Prepare approved content (passed quality gates)
        approved_content = []
        for item in state["generated_content"]:
            if item["status"] == "generated":
                # Check if it passed quality gates
                report = next(
                    (r for r in state["quality_reports"]
                     if r["title"] == item["content"].get("title")),
                    None,
                )
                if report and report["report"]["overall_passed"]:
                    approved_content.append(item["content"])

        # Store in database
        await store_intelligence(
            self.session,
            client_id,
            "content_generated",
            {
                "approved_content": approved_content,
                "all_content": [
                    item["content"] for item in state["generated_content"]
                    if item["content"]
                ],
                "quality_reports": state["quality_reports"],
                "failed": [
                    {
                        "title": item["blueprint"].get("title"),
                        "status": item["status"],
                        "error": item.get("error"),
                    }
                    for item in state["failed_content"]
                ],
            },
        )

        state["current_step"] = "store_results"
        self._log.info(
            "results_stored",
            approved=len(approved_content),
        )

        return state


class OptimizationState(TypedDict):
    """State for the optimization workflow."""

    client_id: str
    content_items: list[dict]  # url, title, content, score

    # Outputs
    optimizations: list[dict]
    quality_reports: list[dict]

    # Workflow state
    errors: list[str]
    current_step: str


class OptimizationWorkflow:
    """
    LangGraph workflow for content optimization.

    Steps:
    1. Load content to optimize
    2. Optimize each piece
    3. Run quality gates
    4. Store results
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.optimizer = OptimizerAgent()
        self._log = logger.bind(workflow="optimization")

    def build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(OptimizationState)

        workflow.add_node("optimize_content", self.optimize_content)
        workflow.add_node("run_quality_gates", self.run_quality_gates)
        workflow.add_node("store_results", self.store_results)

        workflow.set_entry_point("optimize_content")
        workflow.add_edge("optimize_content", "run_quality_gates")
        workflow.add_edge("run_quality_gates", "store_results")
        workflow.add_edge("store_results", END)

        return workflow.compile()

    async def optimize_content(self, state: OptimizationState) -> OptimizationState:
        """Optimize content items."""
        self._log.info("optimizing_content", count=len(state["content_items"]))

        optimizations = []

        for item in state["content_items"]:
            try:
                optimization = await self.optimizer.run(
                    content_url=item.get("url", ""),
                    content_title=item.get("title", ""),
                    content_text=item.get("content", ""),
                    original_citability_score=item.get("score", 0.5),
                    target_queries=item.get("target_queries"),
                )
                optimizations.append(optimization.to_dict())

            except Exception as e:
                self._log.error(
                    "optimization_failed",
                    url=item.get("url"),
                    error=str(e),
                )
                state["errors"].append(f"Optimization failed for {item.get('url')}: {e}")

        state["optimizations"] = optimizations
        state["current_step"] = "optimize_content"

        self._log.info(
            "optimization_complete",
            optimized=len(optimizations),
        )

        return state

    async def run_quality_gates(self, state: OptimizationState) -> OptimizationState:
        """Run quality gates on optimizations."""
        self._log.info("running_quality_gates")

        quality_reports = []

        for optimization in state["optimizations"]:
            report = run_optimization_quality_gates(optimization)
            quality_reports.append({
                "url": optimization.get("original_url"),
                "report": report.to_dict(),
            })

        state["quality_reports"] = quality_reports
        state["current_step"] = "run_quality_gates"

        return state

    async def store_results(self, state: OptimizationState) -> OptimizationState:
        """Store optimization results."""
        self._log.info("storing_results")

        client_id = UUID(state["client_id"])

        await store_intelligence(
            self.session,
            client_id,
            "content_optimizations",
            {
                "optimizations": state["optimizations"],
                "quality_reports": state["quality_reports"],
            },
        )

        state["current_step"] = "store_results"
        return state


async def run_content_workflow(
    session: AsyncSession,
    client_id: UUID,
    blueprints: list[dict] | None = None,
) -> ContentState:
    """
    Run the content creation workflow.

    Args:
        session: Database session
        client_id: Client UUID
        blueprints: Optional list of content blueprints (loaded from architect if not provided)

    Returns:
        Final workflow state
    """
    logger.info("starting_content_workflow", client_id=str(client_id))

    workflow = ContentWorkflow(session)
    graph = workflow.build_graph()

    initial_state: ContentState = {
        "client_id": str(client_id),
        "blueprints": blueprints or [],
        "client_profile": None,
        "generated_content": [],
        "quality_reports": [],
        "failed_content": [],
        "current_blueprint_index": 0,
        "errors": [],
        "current_step": "initial",
    }

    final_state = await graph.ainvoke(initial_state)

    logger.info(
        "content_workflow_complete",
        client_id=str(client_id),
        generated=len(final_state["generated_content"]),
        passed_quality=len([
            r for r in final_state["quality_reports"]
            if r["report"]["overall_passed"]
        ]),
    )

    return final_state


async def run_optimization_workflow(
    session: AsyncSession,
    client_id: UUID,
    content_items: list[dict],
) -> OptimizationState:
    """
    Run the content optimization workflow.

    Args:
        session: Database session
        client_id: Client UUID
        content_items: List of content items to optimize

    Returns:
        Final workflow state
    """
    logger.info("starting_optimization_workflow", client_id=str(client_id))

    workflow = OptimizationWorkflow(session)
    graph = workflow.build_graph()

    initial_state: OptimizationState = {
        "client_id": str(client_id),
        "content_items": content_items,
        "optimizations": [],
        "quality_reports": [],
        "errors": [],
        "current_step": "initial",
    }

    final_state = await graph.ainvoke(initial_state)

    logger.info(
        "optimization_workflow_complete",
        client_id=str(client_id),
        optimized=len(final_state["optimizations"]),
    )

    return final_state
