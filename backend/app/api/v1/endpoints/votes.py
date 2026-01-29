"""
Vote submission API endpoints.
This is a core module handling the secure submission of encrypted votes.
"""
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.vote_service import VoteService
from app.services.election_service import ElectionService
from app.models.user import User
from app.schemas.vote import (
    VoteTokenRequest,
    VoteTokenResponse,
    VoteSubmitRequest,
    VoteSubmitResponse,
    VoteReceiptResponse,
    VoteStatusResponse,
    BallotResponse,
)
from app.schemas.election import CandidateResponse
from app.api.v1.deps import get_current_user


router = APIRouter()


@router.post("/token", response_model=VoteTokenResponse)
async def request_vote_token(
    request: VoteTokenRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> VoteTokenResponse:
    """
    Request a one-time vote token.

    The token is required to submit a vote and can only be used once.
    Tokens expire after 30 minutes.

    Prerequisites:
    - User must be authenticated via DID
    - User must be eligible to vote in the election (verified via ZKP)
    - Election must be active
    """
    vote_service = VoteService(db)
    election_service = ElectionService(db)

    # Get election
    election = await election_service.get_election(request.election_id)
    if not election:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found"
        )

    if not election.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Election is not currently active"
        )

    # Issue token
    token, expires_at, error = await vote_service.issue_vote_token(
        user_id=current_user.id,
        election_id=request.election_id
    )

    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )

    return VoteTokenResponse(
        token=token,
        expires_at=expires_at,
        election_id=request.election_id,
        election_public_key=election.election_public_key
    )


@router.post("/submit", response_model=VoteSubmitResponse)
async def submit_vote(
    request: VoteSubmitRequest,
    db: AsyncSession = Depends(get_db)
) -> VoteSubmitResponse:
    """
    Submit an encrypted vote.

    This is the core voting endpoint that:
    1. Validates the one-time vote token
    2. Verifies the ZKP eligibility proof (proves voter is eligible without revealing identity)
    3. Verifies the ZKP validity proof (proves vote is for a valid candidate)
    4. Checks the nullifier to prevent double voting
    5. Records the encrypted vote on the blockchain
    6. Returns a verification receipt

    The vote is encrypted with CGS homomorphic encryption on the client side
    and can only be decrypted during the tally process with threshold keys.

    Request body:
    - election_id: The election to vote in
    - vote_token: The one-time token from /token endpoint
    - encrypted_vote: CGS-encrypted vote ciphertext
    - nullifier: Hash that prevents double voting without revealing identity
    - eligibility_proof: ZKP proving voter eligibility
    - validity_proof: ZKP proving vote validity
    """
    vote_service = VoteService(db)

    success, receipt_data, error = await vote_service.submit_vote(
        election_id=request.election_id,
        vote_token=request.vote_token,
        encrypted_vote=request.encrypted_vote,
        nullifier=request.nullifier,
        eligibility_proof=request.eligibility_proof,
        validity_proof=request.validity_proof,
        client_signature=request.client_signature
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )

    return VoteSubmitResponse(
        success=True,
        verification_code=receipt_data["verification_code"],
        blockchain_tx_id=receipt_data["blockchain_tx_id"],
        encrypted_vote_hash=receipt_data["encrypted_vote_hash"],
        timestamp=receipt_data["timestamp"]
    )


@router.get("/receipt/{verification_code}", response_model=VoteReceiptResponse)
async def get_vote_receipt(
    verification_code: str,
    db: AsyncSession = Depends(get_db)
) -> VoteReceiptResponse:
    """
    Get a vote receipt by verification code.

    The receipt allows voters to verify their vote was recorded
    without revealing how they voted.
    """
    vote_service = VoteService(db)
    election_service = ElectionService(db)

    receipt = await vote_service.get_receipt(verification_code)

    if not receipt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found"
        )

    election = await election_service.get_election(receipt.election_id)

    return VoteReceiptResponse(
        verification_code=receipt.verification_code,
        election_id=receipt.election_id,
        election_title=election.title if election else "Unknown",
        encrypted_vote_hash=receipt.encrypted_vote_hash,
        blockchain_tx_id=receipt.blockchain_tx_id,
        block_number=receipt.block_number,
        created_at=receipt.created_at,
        confirmed_at=receipt.confirmed_at
    )


@router.get("/status/{election_id}", response_model=VoteStatusResponse)
async def check_vote_status(
    election_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> VoteStatusResponse:
    """
    Check if the current user has voted in an election.

    Note: This uses anonymized tracking and does not reveal
    how the user voted.
    """
    vote_service = VoteService(db)

    has_voted, verification_code = await vote_service.check_vote_status(
        user_id=current_user.id,
        election_id=election_id
    )

    return VoteStatusResponse(
        has_voted=has_voted,
        verification_code=verification_code
    )


@router.get("/ballot/{election_id}", response_model=BallotResponse)
async def get_ballot(
    election_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> BallotResponse:
    """
    Get the ballot information for an election.

    Returns the candidates and the public key needed to encrypt votes.
    """
    election_service = ElectionService(db)

    election = await election_service.get_election(election_id)

    if not election:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found"
        )

    if not election.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Election is not currently active"
        )

    candidates = [
        {
            "id": str(c.id),
            "name": c.name,
            "party": c.party,
            "symbol_number": c.symbol_number,
            "photo_url": c.photo_url,
        }
        for c in sorted(election.candidates, key=lambda x: x.display_order)
    ]

    return BallotResponse(
        election_id=election.id,
        title=election.title,
        description=election.description,
        candidates=candidates,
        election_public_key=election.election_public_key,
        start_time=election.start_time,
        end_time=election.end_time
    )
