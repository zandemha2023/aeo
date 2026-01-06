"""
Integration tests for client management API endpoints.

Tests:
- List clients endpoint
- Get client endpoint
- Authentication requirements
"""

import pytest
from uuid import uuid4

from db.models import Client


@pytest.mark.integration
class TestClientsAPI:
    """Tests for /api/clients endpoints."""

    async def test_list_clients_requires_auth(self, async_client):
        """List clients requires authentication."""
        response = await async_client.get("/api/clients/")
        assert response.status_code == 401

    async def test_list_clients_empty(
        self,
        async_client,
        auth_headers,
        test_org,
    ):
        """List clients returns empty list when no clients exist."""
        response = await async_client.get("/api/clients/", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_clients_with_data(
        self,
        async_client,
        auth_headers,
        test_org,
        client_factory,
    ):
        """List clients returns existing clients."""
        # Create some test clients
        client1 = await client_factory(test_org, name="Client 1", domain="client1.com")
        client2 = await client_factory(test_org, name="Client 2", domain="client2.com")

        response = await async_client.get("/api/clients/", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 2

        domains = {c["domain"] for c in data}
        assert "client1.com" in domains
        assert "client2.com" in domains

    async def test_get_client_by_id(
        self,
        async_client,
        auth_headers,
        test_org,
        client_factory,
    ):
        """Get specific client by ID."""
        client = await client_factory(test_org, name="Test Client", domain="test.com")

        response = await async_client.get(
            f"/api/clients/{client.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == str(client.id)
        assert data["name"] == "Test Client"
        assert data["domain"] == "test.com"

    async def test_get_client_not_found(
        self,
        async_client,
        auth_headers,
    ):
        """Get non-existent client returns 404."""
        fake_id = uuid4()
        response = await async_client.get(
            f"/api/clients/{fake_id}",
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_clients_are_org_scoped(
        self,
        async_client,
        auth_headers,
        test_org,
        organization_factory,
        client_factory,
        db_session,
    ):
        """Clients from other organizations are not visible."""
        # Create client in test_org
        await client_factory(test_org, name="My Client", domain="myorg.com")

        # Create another org with a client
        other_org = await organization_factory(name="Other Org", slug="other-org")
        other_client = await client_factory(
            other_org,
            name="Other Client",
            domain="other.com",
        )

        # List should only show our client
        response = await async_client.get("/api/clients/", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        assert data[0]["domain"] == "myorg.com"

        # Cannot access other org's client directly
        response = await async_client.get(
            f"/api/clients/{other_client.id}",
            headers=auth_headers,
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestClientsAPIWithAPIKey:
    """Tests for client API using API key auth."""

    async def test_list_clients_with_api_key(
        self,
        async_client,
        api_key_headers,
        test_org,
        client_factory,
    ):
        """Can list clients using API key authentication."""
        await client_factory(test_org, name="API Client", domain="api.com")

        response = await async_client.get("/api/clients/", headers=api_key_headers)
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        assert data[0]["domain"] == "api.com"
