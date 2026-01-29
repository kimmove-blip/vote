"""
Vote-related Pydantic schemas.
"""
from typing import Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class VoteTokenRequest(BaseModel):
    """Request for a one-time vote token."""

    election_id: UUID = Field(..., description="ID of the election to vote in")


class VoteTokenResponse(BaseModel):
    """Response with a one-time vote token."""

    token: str = Field(..., description="One-time vote token")
    expires_at: datetime = Field(..., description="Token expiration time")
    election_id: UUID = Field(..., description="Election ID")
    election_public_key: str = Field(..., description="Election public key for encryption")


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
