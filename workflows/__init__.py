"""LangGraph workflows for AEO orchestration."""

from workflows.monitoring import MonitoringWorkflow, run_monitoring_workflow
from workflows.onboarding import OnboardingWorkflow, run_onboarding_workflow
from workflows.strategy import StrategyWorkflow, run_strategy_workflow
from workflows.content import (
    ContentWorkflow,
    OptimizationWorkflow,
    run_content_workflow,
    run_optimization_workflow,
)
from workflows.analytics import (
    AnalyticsWorkflow,
    TechnicalAuditWorkflow,
    run_analytics_workflow,
    run_technical_audit_workflow,
)

__all__ = [
    # Monitoring
    "MonitoringWorkflow",
    "run_monitoring_workflow",
    # Onboarding
    "OnboardingWorkflow",
    "run_onboarding_workflow",
    # Strategy
    "StrategyWorkflow",
    "run_strategy_workflow",
    # Content
    "ContentWorkflow",
    "OptimizationWorkflow",
    "run_content_workflow",
    "run_optimization_workflow",
    # Analytics & Reporting
    "AnalyticsWorkflow",
    "TechnicalAuditWorkflow",
    "run_analytics_workflow",
    "run_technical_audit_workflow",
]
