"""
Integration tests for health and system endpoints.

Tests:
- Health check endpoints
- Metrics endpoint
- System status endpoints
"""

import pytest


@pytest.mark.integration
class TestHealthEndpoints:
    """Tests for health check endpoints."""

    async def test_root_endpoint(self, async_client):
        """Root endpoint returns healthy status."""
        response = await async_client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "AEO Orchestrator"

    async def test_health_endpoint(self, async_client):
        """Health endpoint returns component status."""
        response = await async_client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "components" in data

    async def test_ready_endpoint(self, async_client):
        """Ready endpoint returns readiness status."""
        response = await async_client.get("/ready")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ready"


@pytest.mark.integration
class TestMetricsEndpoint:
    """Tests for Prometheus metrics endpoint."""

    async def test_metrics_returns_prometheus_format(self, async_client):
        """Metrics endpoint returns Prometheus-formatted data."""
        response = await async_client.get("/metrics")
        assert response.status_code == 200

        # Check content type
        content_type = response.headers.get("content-type", "")
        assert "text/plain" in content_type or "text/openmetrics" in content_type

        # Check that it contains some metrics
        content = response.text
        assert "http_requests" in content or "python" in content


@pytest.mark.integration
class TestSystemEndpoints:
    """Tests for system monitoring endpoints."""

    async def test_circuit_breaker_status(self, async_client):
        """Circuit breaker status endpoint works."""
        response = await async_client.get("/api/system/circuit-breakers")
        assert response.status_code == 200

        data = response.json()
        assert "circuit_breakers" in data
