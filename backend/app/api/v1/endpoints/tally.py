"""
Tally API endpoints for vote counting.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.tally_service import TallyService
from app.models.user import User, UserRole
from app.schemas.tally import (
    TallyStartRequest,
    TallyStatusResponse,
    TallyResultResponse,
    CandidateResult,
)
from app.api.v1.deps import require_role


router = APIRouter()


@router.post("/start")
async def start_tally(
    request: TallyStartRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
) -> dict:
    """
    Start the tallying process for an election.

    Requires:
    - Election must be in 'closed' status
    - At least 3 valid key shares (threshold decryption)
    - Proofs for each key share

    The tally process:
    1. Aggregates all encrypted votes using homomorphic addition
    2. Combines key shares using Shamir's secret sharing
    3. Decrypts the aggregated ciphertext
    4. Verifies the decryption with ZKP
    5. Records results on blockchain
    """
    tally_service = TallyService(db)

    success, tally_id, error = await tally_service.start_tally(
        election_id=request.election_id,
        key_shares=request.key_shares,
        share_proofs=request.share_proofs
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )

    return {
        "message": "Tally started",
        "tally_id": tally_id
    }


@router.get("/status/{election_id}", response_model=TallyStatusResponse)
async def get_tally_status(
    election_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> TallyStatusResponse:
    """
    Get the current status of the tallying process.
    """
    tally_service = TallyService(db)
    status_data = await tally_service.get_tally_status(election_id)

    if status_data.get("status") == "not_found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found"
        )

    return TallyStatusResponse(
        election_id=election_id,
        status=status_data["status"],
        total_votes=status_data.get("total_votes"),
        started_at=status_data.get("started_at"),
        completed_at=status_data.get("completed_at"),
        progress=None,  # Could be calculated based on processing
        error=None
    )


@router.get("/results/{election_id}", response_model=TallyResultResponse)
async def get_tally_results(
    election_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> TallyResultResponse:
    """
    Get the final tally results for an election.

    Only available after the tally process is complete.
    Results include cryptographic proofs for verification.
    """
    tally_service = TallyService(db)
    results = await tally_service.get_tally_results(election_id)

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Results not available. Election may not be completed."
        )

    candidate_results = [
        CandidateResult(
            candidate_id=r["candidate_id"],
            name=r["name"],
            party=r.get("party"),
            symbol_number=r["symbol_number"],
            vote_count=r["vote_count"],
            percentage=r["percentage"]
        )
        for r in results["results"]
    ]

    return TallyResultResponse(
        election_id=results["election_id"],
        election_title=results["election_title"],
        status=results["status"],
        total_votes=results["total_votes"],
        total_eligible_voters=results["total_eligible_voters"],
        turnout_percentage=results["turnout_percentage"],
        results=candidate_results,
        aggregated_ciphertext_hash=results["aggregated_ciphertext_hash"],
        decryption_proof=results["decryption_proof"],
        tally_tx_id=results.get("tally_tx_id"),
        election_start_time=results["election_start_time"],
        election_end_time=results["election_end_time"],
        tally_completed_at=results["tally_completed_at"]
    )
