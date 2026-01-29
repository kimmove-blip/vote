"""
Tally service for vote counting using homomorphic encryption.
"""
import uuid
import hashlib
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.config import settings
from app.models.election import Election, Candidate, ElectionStatus
from app.models.vote import VoteReceipt
from app.crypto.homomorphic.cgs_protocol import CGSProtocol
from app.fabric.fabric_client import FabricClient


class TallyService:
    """Service for vote tallying operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.cgs = CGSProtocol()
        self.fabric_client = FabricClient()

    async def start_tally(
        self,
        election_id: uuid.UUID,
        key_shares: List[str],
        share_proofs: List[str]
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Start the tallying process for an election.

        Returns:
            Tuple of (success, tally_id, error)
        """
        # Verify election exists and is closed
        result = await self.db.execute(
            select(Election).where(Election.id == election_id)
        )
        election = result.scalar_one_or_none()

        if not election:
            return False, None, "Election not found"

        if election.status != ElectionStatus.CLOSED:
            return False, None, f"Election must be closed to tally. Current status: {election.status}"

        # Verify we have enough key shares (threshold: 3 of 5)
        if len(key_shares) < settings.ELECTION_KEY_THRESHOLD:
            return False, None, f"Need at least {settings.ELECTION_KEY_THRESHOLD} key shares"

        # Verify key share proofs
        for i, (share, proof) in enumerate(zip(key_shares, share_proofs)):
            is_valid = await self._verify_key_share_proof(share, proof)
            if not is_valid:
                return False, None, f"Invalid proof for key share {i + 1}"

        # Update election status to tallying
        election.status = ElectionStatus.TALLYING
        await self.db.commit()

        # Generate tally ID
        tally_id = hashlib.sha256(
            f"{election_id}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]

        # Start async tallying process
        # In production, this would be a background task
        await self._perform_tally(election_id, key_shares)

        return True, tally_id, None

    async def _verify_key_share_proof(
        self,
        key_share: str,
        proof: str
    ) -> bool:
        """Verify that a key share proof is valid."""
        try:
            # Verify the ZKP that the key share is a valid share
            # This would use Shamir's secret sharing verification
            return self.cgs.verify_key_share_proof(key_share, proof)
        except Exception:
            return False

    async def _perform_tally(
        self,
        election_id: uuid.UUID,
        key_shares: List[str]
    ) -> None:
        """Perform the actual tally using homomorphic aggregation."""
        # Get all votes from blockchain
        votes = await self._get_all_votes(election_id)

        if not votes:
            return

        # Aggregate encrypted votes homomorphically
        aggregated_ciphertext = self._aggregate_votes(votes)

        # Combine key shares and decrypt
        combined_key = self.cgs.combine_key_shares(key_shares)
        decrypted_tally = self.cgs.decrypt(aggregated_ciphertext, combined_key)

        # Parse the decrypted tally
        candidate_counts = self._parse_tally(decrypted_tally)

        # Store results on blockchain
        await self._store_tally_results(election_id, candidate_counts, aggregated_ciphertext)

        # Update election status
        result = await self.db.execute(
            select(Election).where(Election.id == election_id)
        )
        election = result.scalar_one_or_none()
        if election:
            election.status = ElectionStatus.COMPLETED
            await self.db.commit()

    async def _get_all_votes(self, election_id: uuid.UUID) -> List[str]:
        """Get all encrypted votes for an election from blockchain."""
        try:
            result = await self.fabric_client.query_chaincode(
                chaincode_name=settings.FABRIC_CHAINCODE_NAME,
                function_name="GetAllVotes",
                args=[str(election_id)]
            )
            return result.get("votes", [])
        except Exception as e:
            print(f"Error fetching votes: {e}")
            return []

    def _aggregate_votes(self, encrypted_votes: List[str]) -> str:
        """Aggregate encrypted votes using homomorphic addition."""
        if not encrypted_votes:
            return ""

        aggregated = encrypted_votes[0]
        for vote in encrypted_votes[1:]:
            aggregated = self.cgs.homomorphic_add(aggregated, vote)

        return aggregated

    def _parse_tally(self, decrypted_tally: str) -> Dict[int, int]:
        """Parse the decrypted tally into candidate vote counts."""
        # The decrypted tally is a vector where each position
        # represents a candidate's vote count
        try:
            counts = [int(x) for x in decrypted_tally.split(",")]
            return {i: count for i, count in enumerate(counts)}
        except Exception:
            return {}

    async def _store_tally_results(
        self,
        election_id: uuid.UUID,
        candidate_counts: Dict[int, int],
        aggregated_ciphertext: str
    ) -> None:
        """Store tally results on blockchain."""
        try:
            # Generate decryption proof
            decryption_proof = self.cgs.generate_decryption_proof(
                aggregated_ciphertext,
                candidate_counts
            )

            await self.fabric_client.invoke_chaincode(
                chaincode_name=settings.FABRIC_CHAINCODE_NAME,
                function_name="StoreTallyResult",
                args=[
                    str(election_id),
                    str(candidate_counts),
                    hashlib.sha256(aggregated_ciphertext.encode()).hexdigest(),
                    decryption_proof
                ]
            )
        except Exception as e:
            print(f"Error storing tally results: {e}")

    async def get_tally_status(
        self,
        election_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Get the current tally status."""
        result = await self.db.execute(
            select(Election).where(Election.id == election_id)
        )
        election = result.scalar_one_or_none()

        if not election:
            return {"status": "not_found"}

        # Get vote count
        vote_count = await self.db.execute(
            select(func.count(VoteReceipt.id)).where(
                VoteReceipt.election_id == election_id
            )
        )
        total_votes = vote_count.scalar() or 0

        status_map = {
            ElectionStatus.ACTIVE: "pending",
            ElectionStatus.CLOSED: "pending",
            ElectionStatus.TALLYING: "in_progress",
            ElectionStatus.COMPLETED: "completed",
        }

        return {
            "election_id": str(election_id),
            "status": status_map.get(election.status, "unknown"),
            "total_votes": total_votes,
            "started_at": election.end_time,
            "completed_at": election.updated_at if election.status == ElectionStatus.COMPLETED else None,
        }

    async def get_tally_results(
        self,
        election_id: uuid.UUID
    ) -> Optional[Dict[str, Any]]:
        """Get the final tally results."""
        result = await self.db.execute(
            select(Election).where(Election.id == election_id)
        )
        election = result.scalar_one_or_none()

        if not election or election.status != ElectionStatus.COMPLETED:
            return None

        # Get results from blockchain
        try:
            blockchain_result = await self.fabric_client.query_chaincode(
                chaincode_name=settings.FABRIC_CHAINCODE_NAME,
                function_name="GetTallyResult",
                args=[str(election_id)]
            )
        except Exception:
            blockchain_result = {}

        # Get candidates
        result = await self.db.execute(
            select(Candidate).where(Candidate.election_id == election_id)
        )
        candidates = result.scalars().all()

        # Get vote count
        vote_count = await self.db.execute(
            select(func.count(VoteReceipt.id)).where(
                VoteReceipt.election_id == election_id
            )
        )
        total_votes = vote_count.scalar() or 0

        # Build results
        candidate_results = []
        vote_counts = blockchain_result.get("vote_counts", {})

        for candidate in candidates:
            count = vote_counts.get(str(candidate.symbol_number), 0)
            percentage = (count / total_votes * 100) if total_votes > 0 else 0

            candidate_results.append({
                "candidate_id": str(candidate.id),
                "name": candidate.name,
                "party": candidate.party,
                "symbol_number": candidate.symbol_number,
                "vote_count": count,
                "percentage": round(percentage, 2),
            })

        # Sort by vote count descending
        candidate_results.sort(key=lambda x: x["vote_count"], reverse=True)

        return {
            "election_id": str(election_id),
            "election_title": election.title,
            "status": "completed",
            "total_votes": total_votes,
            "total_eligible_voters": 0,  # Would come from merkle tree
            "turnout_percentage": 0,
            "results": candidate_results,
            "aggregated_ciphertext_hash": blockchain_result.get("aggregated_hash", ""),
            "decryption_proof": blockchain_result.get("decryption_proof", ""),
            "tally_tx_id": blockchain_result.get("tx_id"),
            "election_start_time": election.start_time,
            "election_end_time": election.end_time,
            "tally_completed_at": election.updated_at,
        }
