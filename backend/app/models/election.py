"""
Election and Candidate database models.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.core.database import Base


class ElectionStatus(str, enum.Enum):
    """Election status enumeration."""
    DRAFT = "draft"
    PENDING = "pending"
    ACTIVE = "active"
    CLOSED = "closed"
    TALLYING = "tallying"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Election(Base):
    """Election model representing a voting event."""

    __tablename__ = "elections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        Enum(ElectionStatus),
        default=ElectionStatus.DRAFT,
        nullable=False
    )

    # Timing
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)

    # Cryptographic parameters
    voter_merkle_root = Column(String(66), nullable=True)
    election_public_key = Column(Text, nullable=True)
    election_private_key_shares = Column(Text, nullable=True)  # Encrypted, threshold shares

    # Blockchain reference
    blockchain_election_id = Column(String(66), nullable=True)

    # Audit trail
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), nullable=True)

    # Relationships
    candidates = relationship("Candidate", back_populates="election", cascade="all, delete-orphan")
    vote_tokens = relationship("VoteToken", back_populates="election", cascade="all, delete-orphan")
    vote_receipts = relationship("VoteReceipt", back_populates="election", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Election(id={self.id}, title='{self.title}', status={self.status})>"

    @property
    def is_active(self) -> bool:
        """Check if the election is currently active."""
        if self.status != ElectionStatus.ACTIVE:
            return False
        now = datetime.utcnow()
        if self.start_time and now < self.start_time:
            return False
        if self.end_time and now > self.end_time:
            return False
        return True

    @property
    def total_candidates(self) -> int:
        """Get total number of candidates."""
        return len(self.candidates) if self.candidates else 0


class Candidate(Base):
    """Candidate model representing a voting option."""

    __tablename__ = "candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    election_id = Column(
        UUID(as_uuid=True),
        ForeignKey("elections.id", ondelete="CASCADE"),
        nullable=False
    )

    name = Column(String(100), nullable=False)
    party = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    symbol_number = Column(Integer, nullable=False)
    photo_url = Column(String(500), nullable=True)

    # Ordering
    display_order = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    election = relationship("Election", back_populates="candidates")

    def __repr__(self) -> str:
        return f"<Candidate(id={self.id}, name='{self.name}', symbol={self.symbol_number})>"
