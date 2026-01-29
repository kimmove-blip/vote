"""
Election-related Pydantic schemas.
"""
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, validator


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

    @validator("end_time")
    def end_time_after_start_time(cls, v, values):
        if "start_time" in values and v <= values["start_time"]:
            raise ValueError("end_time must be after start_time")
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
