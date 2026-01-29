"""
Vote-related database models.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text, Integer, JSON
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.election import GUID


class VoteToken(Base):
    """
    One-time vote token model.
    Tokens are issued after voter authentication and can only be used once.
    """

    __tablename__ = "vote_tokens"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    election_id = Column(
        GUID(),
        ForeignKey("elections.id", ondelete="CASCADE"),
        nullable=False
    )

    # Token hash (actual token never stored, only hash)
    token_hash = Column(String(66), unique=True, nullable=False, index=True)

    # Token metadata
    issued_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    is_used = Column(Boolean, default=False, nullable=False)

    # For audit (encrypted voter reference, not directly identifiable)
    encrypted_voter_ref = Column(Text, nullable=True)

    # Relationships
    election = relationship("Election", back_populates="vote_tokens")

    def __repr__(self) -> str:
        return f"<VoteToken(id={self.id}, is_used={self.is_used})>"

    @property
    def is_valid(self) -> bool:
        """Check if the token is still valid."""
        if self.is_used:
            return False
        if datetime.utcnow() > self.expires_at:
            return False
        return True


class VoteReceipt(Base):
    """
    Vote receipt model for verification.
    Allows voters to verify their vote was cast as intended.
    """

    __tablename__ = "vote_receipts"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    election_id = Column(
        GUID(),
        ForeignKey("elections.id", ondelete="CASCADE"),
        nullable=False
    )

    # Human-readable verification code
    verification_code = Column(String(20), unique=True, nullable=False, index=True)

    # Voting period (for PERIODIC_RESET mode)
    voting_period = Column(Integer, default=0, nullable=False)

    # Candidate selections (JSON array of candidate IDs with vote counts)
    # Format: [{"candidate_id": "uuid", "votes": 1}, ...]
    candidate_selections = Column(JSON, nullable=True)

    # Cryptographic references
    encrypted_vote_hash = Column(String(66), nullable=False)
    nullifier_hash = Column(String(66), nullable=False, index=True)

    # Blockchain reference
    blockchain_tx_id = Column(String(66), nullable=True)
    block_number = Column(String(20), nullable=True)

    # ZKP references
    eligibility_proof_hash = Column(String(66), nullable=True)
    validity_proof_hash = Column(String(66), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    confirmed_at = Column(DateTime, nullable=True)

    # Relationships
    election = relationship("Election", back_populates="vote_receipts")

    def __repr__(self) -> str:
        return f"<VoteReceipt(id={self.id}, code='{self.verification_code}')>"


class VoterParticipation(Base):
    """
    Track voter participation per election and period.
    Used for PERIODIC_RESET mode to allow re-voting after reset.
    """

    __tablename__ = "voter_participations"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    election_id = Column(
        GUID(),
        ForeignKey("elections.id", ondelete="CASCADE"),
        nullable=False
    )

    # Voter identifier (hashed for privacy)
    voter_hash = Column(String(66), nullable=False, index=True)

    # Voting period number
    voting_period = Column(Integer, default=0, nullable=False)

    # Vote details for MULTI_LIMITED mode
    # Format: {"candidate_id": vote_count, ...}
    votes_by_candidate = Column(JSON, default={})

    # Total votes cast in this period
    total_votes_cast = Column(Integer, default=0, nullable=False)

    # Timestamps
    first_vote_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_vote_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<VoterParticipation(id={self.id}, period={self.voting_period}, votes={self.total_votes_cast})>"


class VoteAuditLog(Base):
    """
    Audit log for vote operations.
    Stores anonymized records of all voting activities.
    """

    __tablename__ = "vote_audit_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    election_id = Column(
        GUID(),
        ForeignKey("elections.id", ondelete="CASCADE"),
        nullable=False
    )

    # Action details
    action = Column(String(50), nullable=False)  # token_issued, vote_submitted, etc.
    action_hash = Column(String(66), nullable=False)  # Hash of action details

    # Anonymized metadata
    client_fingerprint = Column(String(66), nullable=True)
    ip_hash = Column(String(66), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<VoteAuditLog(id={self.id}, action='{self.action}')>"
