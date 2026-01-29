"""
Vote service handling vote submission and token management.
"""
import uuid
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.config import settings
from app.core.security import generate_vote_token, hash_vote_token, generate_verification_code
from app.models.election import Election, ElectionStatus, VotingMode
from app.models.vote import VoteToken, VoteReceipt, VoteAuditLog, VoterParticipation
from app.models.user import User
from app.crypto.zkp.zokrates_engine import ZokratesEngine
from app.fabric.fabric_client import FabricClient


class VoteService:
    """Service for vote operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.zkp_engine = ZokratesEngine()
        self.fabric_client = FabricClient()

    def _calculate_voting_period(self, election: Election) -> int:
        """Calculate current voting period for PERIODIC_RESET mode."""
        if not election.start_time or not election.reset_interval_hours:
            return 0
        elapsed = datetime.utcnow() - election.start_time
        hours_elapsed = elapsed.total_seconds() / 3600
        return int(hours_elapsed / election.reset_interval_hours)

    def _get_voter_hash(self, user_id: uuid.UUID, election_id: uuid.UUID) -> str:
        """Generate a hash for voter identification."""
        return hashlib.sha256(
            f"{user_id}:{election_id}".encode()
        ).hexdigest()

    async def _get_voter_participation(
        self,
        voter_hash: str,
        election_id: uuid.UUID,
        voting_period: int
    ) -> Optional[VoterParticipation]:
        """Get voter participation record for current period."""
        result = await self.db.execute(
            select(VoterParticipation).where(
                and_(
                    VoterParticipation.voter_hash == voter_hash,
                    VoterParticipation.election_id == election_id,
                    VoterParticipation.voting_period == voting_period
                )
            )
        )
        return result.scalar_one_or_none()

    async def _check_voting_eligibility(
        self,
        election: Election,
        voter_hash: str,
        candidate_selections: Optional[List[Dict]] = None
    ) -> Tuple[bool, Optional[str], int]:
        """
        Check if voter is eligible to vote based on voting mode.

        Returns:
            Tuple of (can_vote, error_message, current_period)
        """
        current_period = self._calculate_voting_period(election)

        if election.voting_mode == VotingMode.SINGLE:
            # 전통적 1인 1투표
            participation = await self._get_voter_participation(
                voter_hash, election.id, 0  # period 0 for single vote
            )
            if participation and participation.total_votes_cast > 0:
                return False, "이미 투표하셨습니다 (1인 1투표)", 0
            return True, None, 0

        elif election.voting_mode == VotingMode.MULTI_LIMITED:
            # 복수 후보 투표
            participation = await self._get_voter_participation(
                voter_hash, election.id, 0
            )

            if not participation:
                return True, None, 0

            # 총 투표 가능 수 계산
            max_total_votes = election.max_candidates_per_voter * election.max_votes_per_candidate

            if participation.total_votes_cast >= max_total_votes:
                return False, f"최대 투표 수({max_total_votes})에 도달했습니다", 0

            # 후보별 투표 수 확인
            if candidate_selections:
                votes_by_candidate = participation.votes_by_candidate or {}
                for selection in candidate_selections:
                    cand_id = str(selection.get("candidate_id"))
                    new_votes = selection.get("votes", 1)
                    current_votes = votes_by_candidate.get(cand_id, 0)

                    if current_votes + new_votes > election.max_votes_per_candidate:
                        return False, f"후보당 최대 {election.max_votes_per_candidate}표까지만 가능합니다", 0

            return True, None, 0

        elif election.voting_mode == VotingMode.PERIODIC_RESET:
            # 주기적 리셋 투표
            participation = await self._get_voter_participation(
                voter_hash, election.id, current_period
            )

            if participation and participation.total_votes_cast > 0:
                # 이번 기간에 이미 투표함
                next_period_start = election.start_time + timedelta(
                    hours=election.reset_interval_hours * (current_period + 1)
                )
                return False, f"이번 기간에 이미 투표하셨습니다. 다음 투표 가능: {next_period_start}", current_period

            return True, None, current_period

        return False, "알 수 없는 투표 방식입니다", 0

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
        client_signature: Optional[str] = None,
        candidate_selections: Optional[List[Dict]] = None,
        user_id: Optional[uuid.UUID] = None
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

        # Calculate voter hash for participation tracking
        voter_hash = self._get_voter_hash(user_id or uuid.uuid4(), election_id)

        # Check voting eligibility based on mode
        can_vote, error_msg, current_period = await self._check_voting_eligibility(
            election, voter_hash, candidate_selections
        )
        if not can_vote:
            return False, None, error_msg

        # For SINGLE mode, check nullifier for double-voting prevention
        if election.voting_mode == VotingMode.SINGLE:
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
            voting_period=current_period,
            candidate_selections=candidate_selections,
        )

        self.db.add(receipt)

        # Update voter participation
        participation = await self._get_voter_participation(
            voter_hash, election_id, current_period
        )

        votes_count = 1
        if candidate_selections:
            votes_count = sum(s.get("votes", 1) for s in candidate_selections)

        if participation:
            # Update existing participation
            participation.total_votes_cast += votes_count
            participation.last_vote_at = datetime.utcnow()

            if candidate_selections:
                votes_by_candidate = participation.votes_by_candidate or {}
                for selection in candidate_selections:
                    cand_id = str(selection.get("candidate_id"))
                    votes_by_candidate[cand_id] = votes_by_candidate.get(cand_id, 0) + selection.get("votes", 1)
                participation.votes_by_candidate = votes_by_candidate
        else:
            # Create new participation record
            votes_by_candidate = {}
            if candidate_selections:
                for selection in candidate_selections:
                    cand_id = str(selection.get("candidate_id"))
                    votes_by_candidate[cand_id] = selection.get("votes", 1)

            participation = VoterParticipation(
                election_id=election_id,
                voter_hash=voter_hash,
                voting_period=current_period,
                votes_by_candidate=votes_by_candidate,
                total_votes_cast=votes_count,
            )
            self.db.add(participation)

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
            "voting_period": current_period,
            "votes_cast": votes_count,
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
    ) -> Dict[str, Any]:
        """
        Check voter status for an election with voting mode details.

        Returns:
            Dict with voting status details
        """
        # Get election
        result = await self.db.execute(
            select(Election).where(Election.id == election_id)
        )
        election = result.scalar_one_or_none()

        if not election:
            return {
                "has_voted": False,
                "verification_code": None,
                "voting_mode": "unknown",
                "can_vote_again": False,
                "votes_cast_in_period": 0,
                "max_votes_allowed": 1,
            }

        voter_hash = self._get_voter_hash(user_id, election_id)
        current_period = self._calculate_voting_period(election)

        # Get participation for current period
        participation = await self._get_voter_participation(
            voter_hash, election_id, current_period
        )

        # Get latest receipt for this voter
        verification_code = None
        receipts_result = await self.db.execute(
            select(VoteReceipt).where(
                VoteReceipt.election_id == election_id,
                VoteReceipt.voting_period == current_period
            ).order_by(VoteReceipt.created_at.desc())
        )
        latest_receipt = receipts_result.scalars().first()
        if latest_receipt:
            verification_code = latest_receipt.verification_code

        # Calculate status based on voting mode
        has_voted = participation is not None and participation.total_votes_cast > 0
        can_vote_again = False
        votes_cast = participation.total_votes_cast if participation else 0
        max_votes = 1
        next_vote_available = None

        if election.voting_mode == VotingMode.SINGLE:
            max_votes = 1
            can_vote_again = False

        elif election.voting_mode == VotingMode.MULTI_LIMITED:
            max_votes = election.max_candidates_per_voter * election.max_votes_per_candidate
            can_vote_again = votes_cast < max_votes

        elif election.voting_mode == VotingMode.PERIODIC_RESET:
            max_votes = 1  # 1 vote per period
            can_vote_again = not has_voted
            if has_voted:
                next_vote_available = election.start_time + timedelta(
                    hours=election.reset_interval_hours * (current_period + 1)
                )

        return {
            "has_voted": has_voted,
            "verification_code": verification_code,
            "voting_mode": election.voting_mode.value,
            "current_period": current_period,
            "can_vote_again": can_vote_again,
            "votes_cast_in_period": votes_cast,
            "max_votes_allowed": max_votes,
            "next_vote_available_at": next_vote_available,
            "votes_by_candidate": participation.votes_by_candidate if participation else {},
        }
