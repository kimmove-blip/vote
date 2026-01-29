"""
Tests for voting endpoints.
"""
import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock


class TestVoteEndpoints:
    """Test cases for voting API endpoints."""

    @pytest.mark.asyncio
    async def test_request_vote_token(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_election,
    ):
        """Test requesting a vote token."""
        response = await client.post(
            "/api/v1/votes/token",
            json={"election_id": str(test_election.id)},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "expires_at" in data
        assert "election_public_key" in data

    @pytest.mark.asyncio
    async def test_request_vote_token_inactive_election(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_db,
        test_admin,
    ):
        """Test requesting token for inactive election."""
        from datetime import datetime, timedelta
        from app.models.election import Election, Candidate, ElectionStatus

        # Create an inactive election
        election = Election(
            title="Inactive Election",
            status=ElectionStatus.DRAFT,
            start_time=datetime.utcnow() + timedelta(days=10),
            end_time=datetime.utcnow() + timedelta(days=11),
            created_by=test_admin.id,
        )
        test_db.add(election)
        await test_db.commit()
        await test_db.refresh(election)

        response = await client.post(
            "/api/v1/votes/token",
            json={"election_id": str(election.id)},
            headers=auth_headers,
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_request_vote_token_unauthenticated(
        self,
        client: AsyncClient,
        test_election,
    ):
        """Test that unauthenticated users cannot get vote tokens."""
        response = await client.post(
            "/api/v1/votes/token",
            json={"election_id": str(test_election.id)},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    @patch("app.services.vote_service.VoteService._verify_eligibility_proof")
    @patch("app.services.vote_service.VoteService._verify_validity_proof")
    @patch("app.services.vote_service.VoteService._submit_to_blockchain")
    async def test_submit_vote(
        self,
        mock_blockchain,
        mock_validity,
        mock_eligibility,
        client: AsyncClient,
        auth_headers: dict,
        test_election,
    ):
        """Test submitting a vote."""
        mock_eligibility.return_value = True
        mock_validity.return_value = True
        mock_blockchain.return_value = {
            "tx_id": "test_tx_123",
            "block_number": "456",
        }

        # First get a token
        token_response = await client.post(
            "/api/v1/votes/token",
            json={"election_id": str(test_election.id)},
            headers=auth_headers,
        )
        token = token_response.json()["token"]

        # Submit vote
        vote_data = {
            "election_id": str(test_election.id),
            "vote_token": token,
            "encrypted_vote": '{"ciphertexts": []}',
            "nullifier": "0x" + "a" * 64,
            "eligibility_proof": '{"a": [], "b": [], "c": []}',
            "validity_proof": '{"a": [], "b": [], "c": []}',
        }

        response = await client.post(
            "/api/v1/votes/submit",
            json=vote_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "verification_code" in data
        assert "encrypted_vote_hash" in data

    @pytest.mark.asyncio
    async def test_submit_vote_invalid_token(
        self,
        client: AsyncClient,
        test_election,
    ):
        """Test submitting vote with invalid token."""
        vote_data = {
            "election_id": str(test_election.id),
            "vote_token": "invalid_token",
            "encrypted_vote": '{"ciphertexts": []}',
            "nullifier": "0x" + "b" * 64,
            "eligibility_proof": '{"a": [], "b": [], "c": []}',
            "validity_proof": '{"a": [], "b": [], "c": []}',
        }

        response = await client.post(
            "/api/v1/votes/submit",
            json=vote_data,
        )

        assert response.status_code == 400
        assert "Invalid" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_ballot(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_election,
    ):
        """Test getting ballot information."""
        response = await client.get(
            f"/api/v1/votes/ballot/{test_election.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["election_id"] == str(test_election.id)
        assert "candidates" in data
        assert "election_public_key" in data

    @pytest.mark.asyncio
    async def test_check_vote_status(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_election,
    ):
        """Test checking vote status."""
        response = await client.get(
            f"/api/v1/votes/status/{test_election.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "has_voted" in data


class TestVoteReceipt:
    """Test cases for vote receipt endpoints."""

    @pytest.mark.asyncio
    async def test_get_receipt_not_found(
        self,
        client: AsyncClient,
    ):
        """Test getting nonexistent receipt."""
        response = await client.get("/api/v1/votes/receipt/INVALID_CODE")

        assert response.status_code == 404
