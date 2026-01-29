"""
Tests for election endpoints.
"""
import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta

from app.models.election import ElectionStatus


class TestElectionEndpoints:
    """Test cases for election API endpoints."""

    @pytest.mark.asyncio
    async def test_list_elections(
        self,
        client: AsyncClient,
        test_election,
    ):
        """Test listing elections."""
        response = await client.get("/api/v1/elections")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_list_active_elections(
        self,
        client: AsyncClient,
        test_election,
    ):
        """Test listing active elections."""
        response = await client.get("/api/v1/elections/active")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Test election should be active
        assert any(e["id"] == str(test_election.id) for e in data)

    @pytest.mark.asyncio
    async def test_get_election(
        self,
        client: AsyncClient,
        test_election,
    ):
        """Test getting a single election."""
        response = await client.get(f"/api/v1/elections/{test_election.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_election.id)
        assert data["title"] == "Test Election 2024"
        assert len(data["candidates"]) == 3

    @pytest.mark.asyncio
    async def test_get_nonexistent_election(
        self,
        client: AsyncClient,
    ):
        """Test getting a nonexistent election."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(f"/api/v1/elections/{fake_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_election_as_admin(
        self,
        client: AsyncClient,
        admin_auth_headers: dict,
    ):
        """Test creating an election as admin."""
        election_data = {
            "title": "New Test Election",
            "description": "A new election for testing",
            "start_time": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            "end_time": (datetime.utcnow() + timedelta(days=2)).isoformat(),
            "candidates": [
                {"name": "Candidate X", "party": "Party X", "symbol_number": 1},
                {"name": "Candidate Y", "party": "Party Y", "symbol_number": 2},
            ],
        }

        response = await client.post(
            "/api/v1/elections",
            json=election_data,
            headers=admin_auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "New Test Election"
        assert data["status"] == "draft"
        assert len(data["candidates"]) == 2

    @pytest.mark.asyncio
    async def test_create_election_as_voter_forbidden(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test that voters cannot create elections."""
        election_data = {
            "title": "Unauthorized Election",
            "start_time": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            "end_time": (datetime.utcnow() + timedelta(days=2)).isoformat(),
            "candidates": [
                {"name": "Candidate X", "symbol_number": 1},
                {"name": "Candidate Y", "symbol_number": 2},
            ],
        }

        response = await client.post(
            "/api/v1/elections",
            json=election_data,
            headers=auth_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_election_without_auth(
        self,
        client: AsyncClient,
    ):
        """Test that unauthenticated users cannot create elections."""
        election_data = {
            "title": "Unauthorized Election",
            "start_time": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            "end_time": (datetime.utcnow() + timedelta(days=2)).isoformat(),
            "candidates": [
                {"name": "Candidate X", "symbol_number": 1},
                {"name": "Candidate Y", "symbol_number": 2},
            ],
        }

        response = await client.post(
            "/api/v1/elections",
            json=election_data,
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_election_validation(
        self,
        client: AsyncClient,
        admin_auth_headers: dict,
    ):
        """Test election creation validation."""
        # End time before start time
        election_data = {
            "title": "Invalid Election",
            "start_time": (datetime.utcnow() + timedelta(days=2)).isoformat(),
            "end_time": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            "candidates": [
                {"name": "Candidate X", "symbol_number": 1},
                {"name": "Candidate Y", "symbol_number": 2},
            ],
        }

        response = await client.post(
            "/api/v1/elections",
            json=election_data,
            headers=admin_auth_headers,
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_create_election_minimum_candidates(
        self,
        client: AsyncClient,
        admin_auth_headers: dict,
    ):
        """Test that elections need at least 2 candidates."""
        election_data = {
            "title": "Single Candidate Election",
            "start_time": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            "end_time": (datetime.utcnow() + timedelta(days=2)).isoformat(),
            "candidates": [
                {"name": "Only Candidate", "symbol_number": 1},
            ],
        }

        response = await client.post(
            "/api/v1/elections",
            json=election_data,
            headers=admin_auth_headers,
        )

        assert response.status_code == 422  # Validation error
