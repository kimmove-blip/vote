"""
Tally-related Pydantic schemas.
"""
from typing import Optional, List, Dict
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class TallyStartRequest(BaseModel):
    """Request to start the tallying process."""

    election_id: UUID = Field(..., description="ID of the election to tally")
    key_shares: List[str] = Field(
        ...,
        min_length=3,
        max_length=5,
        description="Decryption key shares from authorized parties"
    )
    share_proofs: List[str] = Field(
        ...,
        description="Proofs of valid key share decryption"
    )


class TallyStatusResponse(BaseModel):
    """Response for tally status."""

    election_id: UUID = Field(..., description="Election ID")
    status: str = Field(
        ...,
        description="Tally status: pending, in_progress, completed, failed"
    )
    progress: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Progress percentage"
    )
    total_votes: Optional[int] = Field(None, description="Total votes counted")
    started_at: Optional[datetime] = Field(None, description="When tallying started")
    completed_at: Optional[datetime] = Field(None, description="When tallying completed")
    error: Optional[str] = Field(None, description="Error message if failed")


class CandidateResult(BaseModel):
    """Result for a single candidate."""

    candidate_id: UUID = Field(..., description="Candidate ID")
    name: str = Field(..., description="Candidate name")
    party: Optional[str] = Field(None, description="Party affiliation")
    symbol_number: int = Field(..., description="Ballot symbol number")
    vote_count: int = Field(..., description="Number of votes received")
    percentage: float = Field(..., description="Percentage of total votes")


class TallyResultResponse(BaseModel):
    """Complete tally results."""

    election_id: UUID = Field(..., description="Election ID")
    election_title: str = Field(..., description="Election title")
    status: str = Field(..., description="Tally status")

    # Vote counts
    total_votes: int = Field(..., description="Total valid votes")
    total_eligible_voters: int = Field(..., description="Total eligible voters")
    turnout_percentage: float = Field(..., description="Voter turnout percentage")

    # Results by candidate
    results: List[CandidateResult] = Field(..., description="Results by candidate")

    # Cryptographic verification
    aggregated_ciphertext_hash: str = Field(
        ...,
        description="Hash of the aggregated encrypted votes"
    )
    decryption_proof: str = Field(
        ...,
        description="Proof of correct decryption"
    )

    # Blockchain references
    tally_tx_id: Optional[str] = Field(
        None,
        description="Blockchain transaction ID for tally"
    )

    # Timestamps
    election_start_time: datetime = Field(..., description="Election start time")
    election_end_time: datetime = Field(..., description="Election end time")
    tally_completed_at: datetime = Field(..., description="Tally completion time")


class TallyVerificationRequest(BaseModel):
    """Request to verify tally results."""

    election_id: UUID = Field(..., description="Election ID")


class TallyVerificationResponse(BaseModel):
    """Response for tally verification."""

    is_valid: bool = Field(..., description="Whether the tally is valid")
    checks_performed: Dict[str, bool] = Field(
        ...,
        description="Individual verification checks"
    )
    blockchain_verified: bool = Field(
        ...,
        description="Whether blockchain records match"
    )
    decryption_proof_valid: bool = Field(
        ...,
        description="Whether decryption proof is valid"
    )
    homomorphic_sum_valid: bool = Field(
        ...,
        description="Whether homomorphic sum is correct"
    )
    verification_time: datetime = Field(..., description="Verification timestamp")


class PartialDecryption(BaseModel):
    """Partial decryption from a key holder."""

    party_id: str = Field(..., description="ID of the decrypting party")
    partial_decryption: str = Field(..., description="Partial decryption value")
    proof: str = Field(..., description="Proof of correct partial decryption")
