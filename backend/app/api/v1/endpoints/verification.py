"""
Verification API endpoints for vote and tally verification.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.verification_service import VerificationService
from app.schemas.verification import (
    CastVerificationRequest,
    CastVerificationResponse,
    RecordedVerificationRequest,
    RecordedVerificationResponse,
    TalliedVerificationRequest,
    TalliedVerificationResponse,
    PublicBulletinBoardResponse,
    AuditLogResponse,
)


router = APIRouter()


@router.get("/cast/{verification_code}", response_model=CastVerificationResponse)
async def verify_cast_as_intended(
    verification_code: str,
    db: AsyncSession = Depends(get_db)
) -> CastVerificationResponse:
    """
    Verify that a vote was cast as intended.

    This is the "cast-as-intended" verification that allows
    voters to confirm their encrypted vote was recorded correctly
    using the verification code from their receipt.

    The verification checks:
    1. The vote exists in the database
    2. The encrypted vote hash matches
    3. The vote is confirmed on the blockchain
    """
    verification_service = VerificationService(db)
    result = await verification_service.verify_cast_as_intended(verification_code)

    if not result.get("verified"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("error", "Verification failed")
        )

    return CastVerificationResponse(
        verified=True,
        election_id=result["election_id"],
        election_title=result["election_title"],
        encrypted_vote_hash=result["encrypted_vote_hash"],
        blockchain_confirmed=result["blockchain_confirmed"],
        blockchain_tx_id=result.get("blockchain_tx_id"),
        block_number=result.get("block_number"),
        cast_time=result["cast_time"],
        confirmation_time=result.get("confirmation_time")
    )


@router.post("/recorded", response_model=RecordedVerificationResponse)
async def verify_recorded_as_cast(
    request: RecordedVerificationRequest,
    db: AsyncSession = Depends(get_db)
) -> RecordedVerificationResponse:
    """
    Verify that a vote was recorded on the blockchain as it was cast.

    This is the "recorded-as-cast" verification that allows anyone
    to verify an encrypted vote exists on the blockchain with the
    correct hash.
    """
    verification_service = VerificationService(db)
    result = await verification_service.verify_recorded_as_cast(
        election_id=request.election_id,
        encrypted_vote_hash=request.encrypted_vote_hash
    )

    return RecordedVerificationResponse(
        found=result["found"],
        matches=result["matches"],
        blockchain_record=result.get("blockchain_record"),
        verification_time=result["verification_time"]
    )


@router.get("/tallied/{election_id}", response_model=TalliedVerificationResponse)
async def verify_tallied_as_recorded(
    election_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> TalliedVerificationResponse:
    """
    Verify that the tally correctly reflects all recorded votes.

    This is the "tallied-as-recorded" verification that allows
    anyone to verify:
    1. All recorded votes were included in the tally
    2. The homomorphic aggregation is correct
    3. The decryption proof is valid

    This provides end-to-end verifiability without revealing
    individual votes.
    """
    verification_service = VerificationService(db)
    result = await verification_service.verify_tallied_as_recorded(election_id)

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )

    return TalliedVerificationResponse(
        verified=result["verified"],
        total_recorded_votes=result["total_recorded_votes"],
        total_tallied_votes=result["total_tallied_votes"],
        homomorphic_verification=result["homomorphic_verification"],
        zkp_verification=result["zkp_verification"],
        details=result["details"]
    )


@router.get("/bulletin-board/{election_id}", response_model=PublicBulletinBoardResponse)
async def get_public_bulletin_board(
    election_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> PublicBulletinBoardResponse:
    """
    Get the public bulletin board for an election.

    The bulletin board contains all public events related to the election:
    - Election creation
    - Voter registration closure
    - Vote submissions (hashes only)
    - Tally initiation
    - Tally results

    Each entry includes a blockchain transaction ID for verification.
    """
    verification_service = VerificationService(db)
    result = await verification_service.get_public_bulletin_board(election_id)

    return PublicBulletinBoardResponse(
        election_id=result["election_id"],
        entries=result["entries"],
        merkle_root=result["merkle_root"],
        last_updated=result["last_updated"]
    )


@router.get("/audit-log/{election_id}", response_model=AuditLogResponse)
async def get_audit_log(
    election_id: UUID,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
) -> AuditLogResponse:
    """
    Get the audit log for an election.

    The audit log contains anonymized records of all voting activities
    for compliance and audit purposes. Individual voter identities
    are protected.
    """
    verification_service = VerificationService(db)
    result = await verification_service.get_audit_log(
        election_id=election_id,
        limit=limit,
        offset=offset
    )

    return AuditLogResponse(
        election_id=result["election_id"],
        entries=result["entries"],
        total_entries=result["total_entries"]
    )
