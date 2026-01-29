"""
Election-related Pydantic schemas.
"""
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum
from pydantic import BaseModel, Field, validator


class VotingModeEnum(str, Enum):
    """Voting mode enumeration for API."""
    SINGLE = "single"  # 전통적인 1인 1투표
    MULTI_LIMITED = "multi_limited"  # 복수 후보 투표 (제한 있음)
    PERIODIC_RESET = "periodic_reset"  # 주기적 투표권 리셋


class VotingModeConfig(BaseModel):
    """Configuration for voting mode."""
    mode: VotingModeEnum = Field(
        default=VotingModeEnum.SINGLE,
        description="투표 방식: single(1인1표), multi_limited(복수투표), periodic_reset(주기적리셋)"
    )
    # MULTI_LIMITED 모드 설정
    max_candidates_per_voter: int = Field(
        default=1,
        ge=1,
        description="투표할 수 있는 최대 후보 수 (MULTI_LIMITED 모드)"
    )
    max_votes_per_candidate: int = Field(
        default=1,
        ge=1,
        description="후보당 최대 중복 투표 수 (MULTI_LIMITED 모드)"
    )
    # PERIODIC_RESET 모드 설정
    reset_interval_hours: int = Field(
        default=24,
        ge=1,
        description="투표권 리셋 주기 (시간 단위, PERIODIC_RESET 모드)"
    )


class CandidateCreate(BaseModel):
    """Schema for creating a candidate."""

    name: str = Field(..., min_length=1, max_length=100, description="Candidate name")
    party: Optional[str] = Field(None, max_length=100, description="Party affiliation")
    description: Optional[str] = Field(None, description="Candidate description")
    symbol_number: int = Field(..., ge=1, description="Ballot symbol number")
    photo_url: Optional[str] = Field(None, description="URL to candidate photo")
    display_order: int = Field(default=0, description="Display order on ballot")


class CandidateResponse(BaseModel):
    """Schema for candidate response."""

    id: UUID
    election_id: UUID
    name: str
    party: Optional[str]
    description: Optional[str]
    symbol_number: int
    photo_url: Optional[str]
    display_order: int
    created_at: datetime

    class Config:
        from_attributes = True


class ElectionCreate(BaseModel):
    """Schema for creating an election."""

    title: str = Field(..., min_length=1, max_length=200, description="Election title")
    description: Optional[str] = Field(None, description="Election description")
    start_time: datetime = Field(..., description="Election start time")
    end_time: datetime = Field(..., description="Election end time")
    candidates: List[CandidateCreate] = Field(
        ...,
        min_length=2,
        description="List of candidates"
    )
    # 투표 방식 설정
    voting_config: Optional[VotingModeConfig] = Field(
        default_factory=VotingModeConfig,
        description="투표 방식 설정"
    )

    @validator("end_time")
    def end_time_after_start_time(cls, v, values):
        if "start_time" in values and v <= values["start_time"]:
            raise ValueError("end_time must be after start_time")
        return v

    @validator("voting_config")
    def validate_voting_config(cls, v, values):
        if v and v.mode == VotingModeEnum.MULTI_LIMITED:
            candidates = values.get("candidates", [])
            if candidates and v.max_candidates_per_voter > len(candidates):
                raise ValueError("max_candidates_per_voter cannot exceed total candidates")
        return v


class ElectionUpdate(BaseModel):
    """Schema for updating an election."""

    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[str] = None


class ElectionResponse(BaseModel):
    """Schema for election response."""

    id: UUID
    title: str
    description: Optional[str]
    status: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    voter_merkle_root: Optional[str]
    blockchain_election_id: Optional[str]
    candidates: List[CandidateResponse]
    total_candidates: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    # 투표 방식
    voting_mode: str = Field(default="single", description="투표 방식")
    max_candidates_per_voter: int = Field(default=1)
    max_votes_per_candidate: int = Field(default=1)
    reset_interval_hours: Optional[int] = Field(default=None)
    # 현재 투표 기간 (PERIODIC_RESET 모드)
    current_voting_period: Optional[int] = Field(default=None)

    class Config:
        from_attributes = True


class ElectionListResponse(BaseModel):
    """Schema for election list response."""

    id: UUID
    title: str
    status: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    total_candidates: int
    is_active: bool

    class Config:
        from_attributes = True


class ElectionStatusUpdate(BaseModel):
    """Schema for updating election status."""

    status: str = Field(
        ...,
        description="New status: pending, active, closed, tallying, completed, cancelled"
    )


class ElectionKeySetup(BaseModel):
    """Schema for setting up election encryption keys."""

    public_key: str = Field(..., description="Election public key")
    key_shares: List[str] = Field(
        ...,
        min_length=5,
        max_length=5,
        description="Encrypted key shares for threshold decryption"
    )


class VoterEligibilitySetup(BaseModel):
    """Schema for setting up voter eligibility."""

    merkle_root: str = Field(
        ...,
        min_length=64,
        max_length=66,
        description="Merkle root of eligible voter list"
    )
    total_eligible_voters: int = Field(..., ge=1, description="Total eligible voters")
