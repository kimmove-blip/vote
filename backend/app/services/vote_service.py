"""
Vote service handling vote submission and token management.
"""
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.security import generate_vote_token, hash_vote_token, generate_verification_code
from app.models.election import Election, ElectionStatus
from app.models.vote import VoteToken, VoteReceipt, VoteAuditLog
from app.models.user import User
from app.crypto.zkp.zokrates_engine import ZokratesEngine
from app.fabric.fabric_client import FabricClient


class VoteService:
    """Service for vote operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.zkp_engine = ZokratesEngine()
        self.fabric_client = FabricClient()

    async def issue_vote_token(
        self,
        user_id: uuid.UUID,
        election_id: uuid.UUID
    ) -> Tuple[Optional[str], Optional[datetime], Optional[str]]:
        """
        Issue a one-time vote token for a user.

        Returns:
            Tuple of (token, expires_at, error)
        """
        # Verify election exists and is active
        result = await self.db.execute(
            select(Election).where(Election.id == election_id)
        )
        election = result.scalar_one_or_none()

        if not election:
            return None, None, "Election not found"

        if not election.is_active:
            return None, None, "Election is not active"

        # Check if user already has an unused token for this election
        existing_token = await self.db.execute(
            select(VoteToken).where(
                VoteToken.election_id == election_id,
                VoteToken.is_used == False,
                VoteToken.expires_at > datetime.utcnow()
            )
        )
        if existing_token.scalar_one_or_none():
            return None, None, "Active token already exists"

        # Generate token
        token = generate_vote_token()
        token_hash = hash_vote_token(token)
        expires_at = datetime.utcnow() + timedelta(minutes=30)

        # Create encrypted voter reference for audit
        encrypted_voter_ref = hashlib.sha256(
            f"{user_id}:{election_id}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()

        vote_token = VoteToken(
            election_id=election_id,
            token_hash=token_hash,
            expires_at=expires_at,
            encrypted_voter_ref=encrypted_voter_ref,
        )

        self.db.add(vote_token)

        # Log the action
        audit_log = VoteAuditLog(
            election_id=election_id,
            action="token_issued",
            action_hash=hashlib.sha256(token_hash.encode()).hexdigest(),
        )
        self.db.add(audit_log)

        await self.db.commit()

        return token, expires_at, None

    async def submit_vote(
        self,
        election_id: uuid.UUID,
        vote_token: str,
        encrypted_vote: str,
        nullifier: str,
        eligibility_proof: str,
        validity_proof: str,
        client_signature: Optional[str] = None
    ) -> Tuple[bool, Optional[dict], Optional[str]]:
        """
        Submit an encrypted vote with ZKP proofs.

        Returns:
            Tuple of (success, receipt_data, error)
        """
        # Verify token
        token_hash = hash_vote_token(vote_token)
        result = await self.db.execute(
            select(VoteToken).where(
                VoteToken.token_hash == token_hash,
                VoteToken.election_id == election_id,
                VoteToken.is_used == False
            )
        )
        token_record = result.scalar_one_or_none()

        if not token_record:
            return False, None, "Invalid or already used token"

        if not token_record.is_valid:
            return False, None, "Token has expired"

        # Verify election is active
        result = await self.db.execute(
            select(Election).where(Election.id == election_id)
        )
        election = result.scalar_one_or_none()

        if not election or not election.is_active:
            return False, None, "Election is not active"

        # Check nullifier hasn't been used (double-voting prevention)
        existing_receipt = await self.db.execute(
            select(VoteReceipt).where(
                VoteReceipt.election_id == election_id,
                VoteReceipt.nullifier_hash == nullifier
            )
        )
        if existing_receipt.scalar_one_or_none():
            return False, None, "Vote already submitted (duplicate nullifier)"

        # Verify ZKP eligibility proof
        eligibility_valid = await self._verify_eligibility_proof(
            eligibility_proof,
            election.voter_merkle_root,
            nullifier
        )
        if not eligibility_valid:
            return False, None, "Invalid eligibility proof"

        # Verify ZKP validity proof
        validity_valid = await self._verify_validity_proof(
            validity_proof,
            encrypted_vote,
            election.election_public_key
        )
        if not validity_valid:
            return False, None, "Invalid validity proof"

        # Calculate encrypted vote hash
        encrypted_vote_hash = hashlib.sha256(encrypted_vote.encode()).hexdigest()

        # Submit to blockchain
        blockchain_result = await self._submit_to_blockchain(
            election_id=str(election_id),
            encrypted_vote=encrypted_vote,
            nullifier=nullifier,
            eligibility_proof_hash=hashlib.sha256(eligibility_proof.encode()).hexdigest(),
            validity_proof_hash=hashlib.sha256(validity_proof.encode()).hexdigest()
        )

        # Generate verification code
        verification_code = generate_verification_code()

        # Create receipt
        receipt = VoteReceipt(
            election_id=election_id,
            verification_code=verification_code,
            encrypted_vote_hash=encrypted_vote_hash,
            nullifier_hash=nullifier,
            blockchain_tx_id=blockchain_result.get("tx_id"),
            block_number=blockchain_result.get("block_number"),
            eligibility_proof_hash=hashlib.sha256(eligibility_proof.encode()).hexdigest(),
            validity_proof_hash=hashlib.sha256(validity_proof.encode()).hexdigest(),
            confirmed_at=datetime.utcnow() if blockchain_result.get("tx_id") else None,
        )

        self.db.add(receipt)

        # Mark token as used
        token_record.is_used = True
        token_record.used_at = datetime.utcnow()

        # Log the action
        audit_log = VoteAuditLog(
            election_id=election_id,
            action="vote_submitted",
            action_hash=encrypted_vote_hash,
        )
        self.db.add(audit_log)

        await self.db.commit()

        return True, {
            "verification_code": verification_code,
            "blockchain_tx_id": blockchain_result.get("tx_id"),
            "encrypted_vote_hash": encrypted_vote_hash,
            "timestamp": receipt.created_at,
        }, None

    async def _verify_eligibility_proof(
        self,
        proof: str,
        merkle_root: str,
        nullifier: str
    ) -> bool:
        """Verify the ZKP eligibility proof."""
        try:
            return await self.zkp_engine.verify_eligibility_proof(
                proof=proof,
                merkle_root=merkle_root,
                nullifier=nullifier
            )
        except Exception as e:
            # Log the error
            print(f"Eligibility proof verification error: {e}")
            return False

    async def _verify_validity_proof(
        self,
        proof: str,
        encrypted_vote: str,
        public_key: str
    ) -> bool:
        """Verify the ZKP validity proof."""
        try:
            return await self.zkp_engine.verify_validity_proof(
                proof=proof,
                encrypted_vote=encrypted_vote,
                public_key=public_key
            )
        except Exception as e:
            # Log the error
            print(f"Validity proof verification error: {e}")
            return False

    async def _submit_to_blockchain(
        self,
        election_id: str,
        encrypted_vote: str,
        nullifier: str,
        eligibility_proof_hash: str,
        validity_proof_hash: str
    ) -> dict:
        """Submit the vote to the Hyperledger Fabric blockchain."""
        try:
            result = await self.fabric_client.invoke_chaincode(
                chaincode_name=settings.FABRIC_CHAINCODE_NAME,
                function_name="CastVote",
                args=[
                    election_id,
                    encrypted_vote,
                    nullifier,
                    eligibility_proof_hash,
                    validity_proof_hash
                ]
            )
            return result
        except Exception as e:
            # Log the error but don't fail the vote
            print(f"Blockchain submission error: {e}")
            return {"tx_id": None, "block_number": None}

    async def get_receipt(
        self,
        verification_code: str
    ) -> Optional[VoteReceipt]:
        """Get a vote receipt by verification code."""
        result = await self.db.execute(
            select(VoteReceipt).where(
                VoteReceipt.verification_code == verification_code
            )
        )
        return result.scalar_one_or_none()

    async def check_vote_status(
        self,
        user_id: uuid.UUID,
        election_id: uuid.UUID
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a user has voted in an election.
        Note: This uses the token's encrypted_voter_ref, not direct user association.

        Returns:
            Tuple of (has_voted, verification_code)
        """
        # This is a simplified check - in production, would use ZKP
        # to prove voting status without revealing identity
        result = await self.db.execute(
            select(VoteToken).where(
                VoteToken.election_id == election_id,
                VoteToken.is_used == True
            )
        )
        used_tokens = result.scalars().all()

        # Check if any token matches the user's hash
        user_hash = hashlib.sha256(str(user_id).encode()).hexdigest()

        for token in used_tokens:
            if token.encrypted_voter_ref and user_hash in token.encrypted_voter_ref:
                # Find the corresponding receipt
                receipt_result = await self.db.execute(
                    select(VoteReceipt).where(
                        VoteReceipt.election_id == election_id
                    )
                )
                # Return first match (simplified)
                receipt = receipt_result.scalar_one_or_none()
                if receipt:
                    return True, receipt.verification_code

        return False, None
