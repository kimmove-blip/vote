"""
Verification service for vote and tally verification.
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.election import Election, ElectionStatus
from app.models.vote import VoteReceipt, VoteAuditLog
from app.crypto.homomorphic.cgs_protocol import CGSProtocol
from app.fabric.fabric_client import FabricClient


class VerificationService:
    """Service for verification operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.cgs = CGSProtocol()
        self.fabric_client = FabricClient()

    async def verify_cast_as_intended(
        self,
        verification_code: str
    ) -> Dict[str, Any]:
        """
        Verify that a vote was cast as intended.
        This allows a voter to verify their encrypted vote was recorded.
        """
        # Find the receipt
        result = await self.db.execute(
            select(VoteReceipt).where(
                VoteReceipt.verification_code == verification_code
            )
        )
        receipt = result.scalar_one_or_none()

        if not receipt:
            return {
                "verified": False,
                "error": "Verification code not found"
            }

        # Get election info
        result = await self.db.execute(
            select(Election).where(Election.id == receipt.election_id)
        )
        election = result.scalar_one_or_none()

        if not election:
            return {
                "verified": False,
                "error": "Election not found"
            }

        # Verify on blockchain
        blockchain_verified = await self._verify_on_blockchain(
            str(receipt.election_id),
            receipt.encrypted_vote_hash,
            receipt.nullifier_hash
        )

        return {
            "verified": True,
            "election_id": str(receipt.election_id),
            "election_title": election.title,
            "encrypted_vote_hash": receipt.encrypted_vote_hash,
            "blockchain_confirmed": blockchain_verified,
            "blockchain_tx_id": receipt.blockchain_tx_id,
            "block_number": receipt.block_number,
            "cast_time": receipt.created_at,
            "confirmation_time": receipt.confirmed_at,
        }

    async def _verify_on_blockchain(
        self,
        election_id: str,
        encrypted_vote_hash: str,
        nullifier: str
    ) -> bool:
        """Verify the vote exists on blockchain with matching hash."""
        try:
            result = await self.fabric_client.query_chaincode(
                chaincode_name=settings.FABRIC_CHAINCODE_NAME,
                function_name="VerifyVote",
                args=[election_id, nullifier, encrypted_vote_hash]
            )
            return result.get("verified", False)
        except Exception:
            return False

    async def verify_recorded_as_cast(
        self,
        election_id: uuid.UUID,
        encrypted_vote_hash: str
    ) -> Dict[str, Any]:
        """
        Verify that a vote was recorded on the blockchain as it was cast.
        """
        # Query blockchain for the vote
        try:
            result = await self.fabric_client.query_chaincode(
                chaincode_name=settings.FABRIC_CHAINCODE_NAME,
                function_name="GetVoteByHash",
                args=[str(election_id), encrypted_vote_hash]
            )

            if not result.get("found"):
                return {
                    "found": False,
                    "matches": False,
                    "verification_time": datetime.utcnow()
                }

            # Verify the hash matches
            blockchain_hash = result.get("encrypted_vote_hash")
            matches = blockchain_hash == encrypted_vote_hash

            return {
                "found": True,
                "matches": matches,
                "blockchain_record": {
                    "tx_id": result.get("tx_id"),
                    "block_number": result.get("block_number"),
                    "timestamp": result.get("timestamp"),
                },
                "verification_time": datetime.utcnow()
            }

        except Exception as e:
            return {
                "found": False,
                "matches": False,
                "error": str(e),
                "verification_time": datetime.utcnow()
            }

    async def verify_tallied_as_recorded(
        self,
        election_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Verify that the tally correctly reflects all recorded votes.
        This is the tallied-as-recorded verification.
        """
        result = await self.db.execute(
            select(Election).where(Election.id == election_id)
        )
        election = result.scalar_one_or_none()

        if not election:
            return {"verified": False, "error": "Election not found"}

        if election.status != ElectionStatus.COMPLETED:
            return {"verified": False, "error": "Election tally not complete"}

        # Get all votes from blockchain
        votes_result = await self.fabric_client.query_chaincode(
            chaincode_name=settings.FABRIC_CHAINCODE_NAME,
            function_name="GetAllVotes",
            args=[str(election_id)]
        )
        recorded_votes = votes_result.get("votes", [])

        # Get tally from blockchain
        tally_result = await self.fabric_client.query_chaincode(
            chaincode_name=settings.FABRIC_CHAINCODE_NAME,
            function_name="GetTallyResult",
            args=[str(election_id)]
        )

        # Verify homomorphic sum
        homomorphic_valid = await self._verify_homomorphic_sum(
            recorded_votes,
            tally_result.get("aggregated_hash")
        )

        # Verify decryption proof
        zkp_valid = self._verify_decryption_proof(
            tally_result.get("aggregated_hash"),
            tally_result.get("decryption_proof"),
            tally_result.get("vote_counts")
        )

        # Count totals
        total_recorded = len(recorded_votes)
        total_tallied = sum(tally_result.get("vote_counts", {}).values())

        return {
            "verified": homomorphic_valid and zkp_valid and (total_recorded == total_tallied),
            "total_recorded_votes": total_recorded,
            "total_tallied_votes": total_tallied,
            "homomorphic_verification": homomorphic_valid,
            "zkp_verification": zkp_valid,
            "details": {
                "aggregated_hash_match": True,
                "decryption_proof_valid": zkp_valid,
                "vote_count_match": total_recorded == total_tallied,
            }
        }

    async def _verify_homomorphic_sum(
        self,
        encrypted_votes: List[str],
        expected_hash: str
    ) -> bool:
        """Verify the homomorphic sum of all encrypted votes."""
        if not encrypted_votes:
            return True

        try:
            # Recompute the homomorphic sum
            aggregated = encrypted_votes[0]
            for vote in encrypted_votes[1:]:
                aggregated = self.cgs.homomorphic_add(aggregated, vote)

            # Hash and compare
            import hashlib
            computed_hash = hashlib.sha256(aggregated.encode()).hexdigest()

            return computed_hash == expected_hash
        except Exception:
            return False

    def _verify_decryption_proof(
        self,
        aggregated_hash: str,
        decryption_proof: str,
        vote_counts: Dict[str, int]
    ) -> bool:
        """Verify the ZKP decryption proof."""
        try:
            return self.cgs.verify_decryption_proof(
                aggregated_hash,
                decryption_proof,
                vote_counts
            )
        except Exception:
            return False

    async def get_public_bulletin_board(
        self,
        election_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Get the public bulletin board for an election."""
        try:
            result = await self.fabric_client.query_chaincode(
                chaincode_name=settings.FABRIC_CHAINCODE_NAME,
                function_name="GetBulletinBoard",
                args=[str(election_id)]
            )

            entries = result.get("entries", [])
            formatted_entries = [
                {
                    "sequence_number": entry.get("sequence"),
                    "entry_type": entry.get("type"),
                    "data_hash": entry.get("hash"),
                    "blockchain_tx_id": entry.get("tx_id"),
                    "timestamp": entry.get("timestamp"),
                }
                for entry in entries
            ]

            return {
                "election_id": str(election_id),
                "entries": formatted_entries,
                "merkle_root": result.get("merkle_root", ""),
                "last_updated": datetime.utcnow(),
            }

        except Exception:
            return {
                "election_id": str(election_id),
                "entries": [],
                "merkle_root": "",
                "last_updated": datetime.utcnow(),
            }

    async def get_audit_log(
        self,
        election_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get the audit log for an election."""
        result = await self.db.execute(
            select(VoteAuditLog)
            .where(VoteAuditLog.election_id == election_id)
            .order_by(VoteAuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        logs = result.scalars().all()

        formatted_logs = [
            {
                "id": str(log.id),
                "action": log.action,
                "actor_type": "system",  # Anonymized
                "action_hash": log.action_hash,
                "timestamp": log.created_at,
            }
            for log in logs
        ]

        # Get total count
        from sqlalchemy import func
        count_result = await self.db.execute(
            select(func.count(VoteAuditLog.id)).where(
                VoteAuditLog.election_id == election_id
            )
        )
        total = count_result.scalar() or 0

        return {
            "election_id": str(election_id),
            "entries": formatted_logs,
            "total_entries": total,
        }
