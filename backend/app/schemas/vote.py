"""
Vote-related Pydantic schemas.
"""
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, validator


class VoteTokenRequest(BaseModel):
    """Request for a one-time vote token."""

    election_id: UUID = Field(..., description="ID of the election to vote in")


class VoteTokenResponse(BaseModel):
    """Response with a one-time vote token."""

    token: str = Field(..., description="One-time vote token")
    expires_at: datetime = Field(..., description="Token expiration time")
    election_id: UUID = Field(..., description="Election ID")
    election_public_key: str = Field(..., description="Election public key for encryption")
    # 투표 방식 정보
    voting_mode: str = Field(..., description="투표 방식")
    max_candidates_per_voter: int = Field(default=1, description="투표 가능한 최대 후보 수")
    max_votes_per_candidate: int = Field(default=1, description="후보당 최대 중복 투표 수")
    current_voting_period: Optional[int] = Field(None, description="현재 투표 기간 (PERIODIC_RESET)")
    remaining_votes: Optional[int] = Field(None, description="남은 투표 수")


class CandidateVoteSelection(BaseModel):
    """Single candidate vote selection."""
    candidate_id: UUID = Field(..., description="후보 ID")
    votes: int = Field(default=1, ge=1, description="해당 후보에게 투표할 수 (중복 투표 시)")


class VoteSubmitRequest(BaseModel):
    """
    Request to submit an encrypted vote.
    This is the core voting request with cryptographic proofs.
    """

    election_id: UUID = Field(..., description="ID of the election")
    vote_token: str = Field(..., description="One-time vote token")

    # Encrypted vote (CGS homomorphic encryption)
    encrypted_vote: str = Field(
        ...,
        description="CGS-encrypted vote ciphertext"
    )

    # 후보 선택 (MULTI_LIMITED 모드용)
    candidate_selections: Optional[List[CandidateVoteSelection]] = Field(
        None,
        description="후보 선택 목록 (MULTI_LIMITED 모드)"
    )

    # Nullifier for double-voting prevention
    nullifier: str = Field(
        ...,
        min_length=64,
        max_length=66,
        description="Nullifier hash for double-voting prevention"
    )

    # Zero-Knowledge Proofs
    eligibility_proof: str = Field(
        ...,
        description="ZKP proving voter eligibility without revealing identity"
    )
    validity_proof: str = Field(
        ...,
        description="ZKP proving vote is valid (one of the valid choices)"
    )

    # Client signature for non-repudiation
    client_signature: Optional[str] = Field(
        None,
        description="Client signature on the vote data"
    )


class VoteSubmitResponse(BaseModel):
    """Response after vote submission."""

    success: bool = Field(..., description="Whether the vote was recorded")
    verification_code: str = Field(
        ...,
        description="Code to verify the vote was cast as intended"
    )
    blockchain_tx_id: Optional[str] = Field(
        None,
        description="Blockchain transaction ID"
    )
    encrypted_vote_hash: str = Field(
        ...,
        description="Hash of the encrypted vote for verification"
    )
    timestamp: datetime = Field(..., description="Vote submission timestamp")


class VoteReceiptResponse(BaseModel):
    """Vote receipt for verification."""

    verification_code: str = Field(..., description="Verification code")
    election_id: UUID = Field(..., description="Election ID")
    election_title: str = Field(..., description="Election title")
    encrypted_vote_hash: str = Field(
        ...,
        description="Hash of encrypted vote"
    )
    blockchain_tx_id: Optional[str] = Field(
        None,
        description="Blockchain transaction ID"
    )
    block_number: Optional[str] = Field(
        None,
        description="Block number in which vote was recorded"
    )
    created_at: datetime = Field(..., description="Vote submission time")
    confirmed_at: Optional[datetime] = Field(
        None,
        description="Blockchain confirmation time"
    )


class VoteStatusResponse(BaseModel):
    """Response for checking vote status."""

    has_voted: bool = Field(..., description="Whether the user has voted")
    verification_code: Optional[str] = Field(
        None,
        description="Verification code if voted"
    )
    # 투표 방식별 상태
    voting_mode: str = Field(..., description="투표 방식")
    current_period: Optional[int] = Field(None, description="현재 투표 기간")
    can_vote_again: bool = Field(default=False, description="재투표 가능 여부")
    votes_cast_in_period: int = Field(default=0, description="현재 기간 투표 수")
    max_votes_allowed: int = Field(default=1, description="최대 투표 가능 수")
    next_vote_available_at: Optional[datetime] = Field(
        None,
        description="다음 투표 가능 시간 (PERIODIC_RESET)"
    )


class BallotResponse(BaseModel):
    """Ballot information for voting."""

    election_id: UUID = Field(..., description="Election ID")
    title: str = Field(..., description="Election title")
    description: Optional[str] = Field(None, description="Election description")
    candidates: list = Field(..., description="List of candidates")
    election_public_key: str = Field(
        ...,
        description="Public key for encrypting votes"
    )
    start_time: datetime = Field(..., description="Election start time")
    end_time: datetime = Field(..., description="Election end time")
    # 투표 방식 정보
    voting_mode: str = Field(..., description="투표 방식")
    max_candidates_per_voter: int = Field(default=1, description="투표 가능한 최대 후보 수")
    max_votes_per_candidate: int = Field(default=1, description="후보당 최대 중복 투표 수")
    reset_interval_hours: Optional[int] = Field(None, description="투표권 리셋 주기 (시간)")
    current_voting_period: Optional[int] = Field(None, description="현재 투표 기간")


class EncryptedVote(BaseModel):
    """Structure of an encrypted vote."""

    ciphertext: str = Field(..., description="CGS ciphertext")
    randomness_commitment: str = Field(
        ...,
        description="Commitment to randomness used in encryption"
    )
    public_key_hash: str = Field(
        ...,
        description="Hash of the public key used"
    )
