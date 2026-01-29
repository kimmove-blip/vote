"""
Verification-related Pydantic schemas.
"""
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class CastVerificationRequest(BaseModel):
    """Request to verify a cast vote (cast-as-intended)."""

    verification_code: str = Field(
        ...,
        description="The verification code from the receipt"
    )


class CastVerificationResponse(BaseModel):
    """Response for cast-as-intended verification."""

    verified: bool = Field(..., description="Whether the vote was found")
    election_id: UUID = Field(..., description="Election ID")
    election_title: str = Field(..., description="Election title")
    encrypted_vote_hash: str = Field(
        ...,
        description="Hash of the encrypted vote"
    )
    blockchain_confirmed: bool = Field(
        ...,
        description="Whether the vote is confirmed on blockchain"
    )
    blockchain_tx_id: Optional[str] = Field(
        None,
        description="Blockchain transaction ID"
    )
    block_number: Optional[str] = Field(
        None,
        description="Block number containing the vote"
    )
    cast_time: datetime = Field(..., description="When the vote was cast")
    confirmation_time: Optional[datetime] = Field(
        None,
        description="When the vote was confirmed on blockchain"
    )


class RecordedVerificationRequest(BaseModel):
    """Request to verify a recorded vote (recorded-as-cast)."""

    election_id: UUID = Field(..., description="Election ID")
    encrypted_vote_hash: str = Field(
        ...,
        description="Hash of the encrypted vote to verify"
    )


class RecordedVerificationResponse(BaseModel):
    """Response for recorded-as-cast verification."""

    found: bool = Field(..., description="Whether the vote was found on blockchain")
    matches: bool = Field(..., description="Whether the hash matches")
    blockchain_record: Optional[Dict[str, Any]] = Field(
        None,
        description="The blockchain record"
    )
    verification_time: datetime = Field(..., description="Verification timestamp")


class TalliedVerificationRequest(BaseModel):
    """Request to verify tallied votes (tallied-as-recorded)."""

    election_id: UUID = Field(..., description="Election ID")


class TalliedVerificationResponse(BaseModel):
    """Response for tallied-as-recorded verification."""

    verified: bool = Field(..., description="Whether the tally is correct")
    total_recorded_votes: int = Field(..., description="Total votes on blockchain")
    total_tallied_votes: int = Field(..., description="Total votes in tally")
    homomorphic_verification: bool = Field(
        ...,
        description="Whether homomorphic sum matches"
    )
    zkp_verification: bool = Field(
        ...,
        description="Whether ZK proofs verify"
    )
    details: Dict[str, Any] = Field(
        ...,
        description="Detailed verification results"
    )


class PublicBulletinBoardEntry(BaseModel):
    """An entry on the public bulletin board."""

    sequence_number: int = Field(..., description="Entry sequence number")
    entry_type: str = Field(
        ...,
        description="Type: election_created, vote_cast, tally_started, etc."
    )
    data_hash: str = Field(..., description="Hash of the entry data")
    blockchain_tx_id: str = Field(..., description="Blockchain transaction ID")
    timestamp: datetime = Field(..., description="Entry timestamp")


class PublicBulletinBoardResponse(BaseModel):
    """Response for public bulletin board query."""

    election_id: UUID = Field(..., description="Election ID")
    entries: list[PublicBulletinBoardEntry] = Field(
        ...,
        description="Bulletin board entries"
    )
    merkle_root: str = Field(
        ...,
        description="Merkle root of all entries"
    )
    last_updated: datetime = Field(..., description="Last update time")


class AuditLogEntry(BaseModel):
    """An audit log entry."""

    id: UUID = Field(..., description="Entry ID")
    action: str = Field(..., description="Action performed")
    actor_type: str = Field(..., description="Type of actor: system, admin, voter")
    action_hash: str = Field(..., description="Hash of action details")
    timestamp: datetime = Field(..., description="Action timestamp")


class AuditLogResponse(BaseModel):
    """Response for audit log query."""

    election_id: UUID = Field(..., description="Election ID")
    entries: list[AuditLogEntry] = Field(..., description="Audit log entries")
    total_entries: int = Field(..., description="Total number of entries")
