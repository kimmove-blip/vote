"""
Election and Candidate database models.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey, Enum, TypeDecorator, CHAR
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class GUID(TypeDecorator):
    """Platform-independent GUID type for SQLite and PostgreSQL."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import UUID
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if isinstance(value, uuid.UUID):
                return str(value)
            else:
                return str(uuid.UUID(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(value)
        return value


class ElectionStatus(str, enum.Enum):
    """Election status enumeration."""
    DRAFT = "draft"
    PENDING = "pending"
    ACTIVE = "active"
    CLOSED = "closed"
    TALLYING = "tallying"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class VotingMode(str, enum.Enum):
    """Voting mode enumeration."""
    # 전통적인 1인 1투표
    SINGLE = "single"
    # 복수 후보 투표 (n명까지, 후보당 m번까지 중복 허용)
    MULTI_LIMITED = "multi_limited"
    # 일정 시간마다 투표권 리셋 (기존 투표는 유효)
    PERIODIC_RESET = "periodic_reset"


class Election(Base):
    """Election model representing a voting event."""

    __tablename__ = "elections"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
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

    # Voting mode configuration
    voting_mode = Column(
        Enum(VotingMode),
        default=VotingMode.SINGLE,
        nullable=False
    )
    # MULTI_LIMITED: 투표할 수 있는 최대 후보 수
    max_candidates_per_voter = Column(Integer, default=1, nullable=False)
    # MULTI_LIMITED: 후보당 최대 중복 투표 수
    max_votes_per_candidate = Column(Integer, default=1, nullable=False)
    # PERIODIC_RESET: 투표권 리셋 주기 (시간 단위)
    reset_interval_hours = Column(Integer, default=24, nullable=True)

    # Cryptographic parameters
    voter_merkle_root = Column(String(66), nullable=True)
    election_public_key = Column(Text, nullable=True)
    election_private_key_shares = Column(Text, nullable=True)  # Encrypted, threshold shares

    # Blockchain reference
    blockchain_election_id = Column(String(66), nullable=True)

    # Audit trail
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(GUID(), nullable=True)

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

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    election_id = Column(
        GUID(),
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
