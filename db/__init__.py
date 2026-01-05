"""Database models and queries for AEO system."""

from db.models import Base, Client, ClientIntelligence, MonitoringQuery, MonitoringResult, Alert
from db.queries import (
    create_client,
    get_client,
    get_client_by_domain,
    store_intelligence,
    get_latest_intelligence,
    create_monitoring_query,
    get_monitoring_queries,
    store_monitoring_result,
    get_recent_monitoring_results,
    create_alert,
    get_active_alerts,
)

__all__ = [
    "Base",
    "Client",
    "ClientIntelligence",
    "MonitoringQuery",
    "MonitoringResult",
    "Alert",
    "create_client",
    "get_client",
    "get_client_by_domain",
    "store_intelligence",
    "get_latest_intelligence",
    "create_monitoring_query",
    "get_monitoring_queries",
    "store_monitoring_result",
    "get_recent_monitoring_results",
    "create_alert",
    "get_active_alerts",
]
