"""
Election management API endpoints.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.election_service import ElectionService
from app.models.election import ElectionStatus
from app.models.user import User, UserRole
from app.schemas.election import (
    ElectionCreate,
    ElectionUpdate,
    ElectionResponse,
    ElectionListResponse,
    ElectionStatusUpdate,
    ElectionKeySetup,
    VoterEligibilitySetup,
    CandidateCreate,
    CandidateResponse,
)
from app.api.v1.deps import get_current_user, require_role


router = APIRouter()


@router.get("", response_model=List[ElectionListResponse])
async def list_elections(
    status_filter: Optional[str] = Query(None, alias="status"),
    include_draft: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
) -> List[ElectionListResponse]:
    """
    Get all elections.
    Draft elections are only visible to admins.
    """
    election_service = ElectionService(db)

    # Non-admins cannot see drafts
    if include_draft and (not current_user or current_user.role not in [UserRole.ADMIN, UserRole.ELECTION_OFFICIAL]):
        include_draft = False

    status_enum = None
    if status_filter:
        try:
            status_enum = ElectionStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}"
            )

    elections = await election_service.get_elections(
        status=status_enum,
        include_draft=include_draft
    )

    return [
        ElectionListResponse(
            id=e.id,
            title=e.title,
            status=e.status.value,
            start_time=e.start_time,
            end_time=e.end_time,
            total_candidates=e.total_candidates,
            is_active=e.is_active
        )
        for e in elections
    ]


@router.get("/active", response_model=List[ElectionListResponse])
async def list_active_elections(
    db: AsyncSession = Depends(get_db)
) -> List[ElectionListResponse]:
    """
    Get all currently active elections that can be voted on.
    """
    election_service = ElectionService(db)
    elections = await election_service.get_active_elections()

    return [
        ElectionListResponse(
            id=e.id,
            title=e.title,
            status=e.status.value,
            start_time=e.start_time,
            end_time=e.end_time,
            total_candidates=e.total_candidates,
            is_active=e.is_active
        )
        for e in elections
    ]


@router.get("/{election_id}", response_model=ElectionResponse)
async def get_election(
    election_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> ElectionResponse:
    """
    Get a specific election by ID.
    """
    election_service = ElectionService(db)
    election = await election_service.get_election(election_id)

    if not election:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found"
        )

    return ElectionResponse(
        id=election.id,
        title=election.title,
        description=election.description,
        status=election.status.value,
        start_time=election.start_time,
        end_time=election.end_time,
        voter_merkle_root=election.voter_merkle_root,
        blockchain_election_id=election.blockchain_election_id,
        candidates=[
            CandidateResponse(
                id=c.id,
                election_id=c.election_id,
                name=c.name,
                party=c.party,
                description=c.description,
                symbol_number=c.symbol_number,
                photo_url=c.photo_url,
                display_order=c.display_order,
                created_at=c.created_at
            )
            for c in sorted(election.candidates, key=lambda x: x.display_order)
        ],
        total_candidates=election.total_candidates,
        is_active=election.is_active,
        created_at=election.created_at,
        updated_at=election.updated_at
    )


@router.post("", response_model=ElectionResponse, status_code=status.HTTP_201_CREATED)
async def create_election(
    election_data: ElectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.ELECTION_OFFICIAL]))
) -> ElectionResponse:
    """
    Create a new election.
    Requires admin or election official role.
    """
    election_service = ElectionService(db)
    election = await election_service.create_election(
        election_data=election_data,
        created_by=current_user.id
    )

    return ElectionResponse(
        id=election.id,
        title=election.title,
        description=election.description,
        status=election.status.value,
        start_time=election.start_time,
        end_time=election.end_time,
        voter_merkle_root=election.voter_merkle_root,
        blockchain_election_id=election.blockchain_election_id,
        candidates=[
            CandidateResponse(
                id=c.id,
                election_id=c.election_id,
                name=c.name,
                party=c.party,
                description=c.description,
                symbol_number=c.symbol_number,
                photo_url=c.photo_url,
                display_order=c.display_order,
                created_at=c.created_at
            )
            for c in election.candidates
        ],
        total_candidates=election.total_candidates,
        is_active=election.is_active,
        created_at=election.created_at,
        updated_at=election.updated_at
    )


@router.patch("/{election_id}", response_model=ElectionResponse)
async def update_election(
    election_id: UUID,
    election_data: ElectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.ELECTION_OFFICIAL]))
) -> ElectionResponse:
    """
    Update an election.
    Only draft elections can be modified.
    """
    election_service = ElectionService(db)

    try:
        election = await election_service.update_election(election_id, election_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    if not election:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found"
        )

    return ElectionResponse(
        id=election.id,
        title=election.title,
        description=election.description,
        status=election.status.value,
        start_time=election.start_time,
        end_time=election.end_time,
        voter_merkle_root=election.voter_merkle_root,
        blockchain_election_id=election.blockchain_election_id,
        candidates=[
            CandidateResponse(
                id=c.id,
                election_id=c.election_id,
                name=c.name,
                party=c.party,
                description=c.description,
                symbol_number=c.symbol_number,
                photo_url=c.photo_url,
                display_order=c.display_order,
                created_at=c.created_at
            )
            for c in election.candidates
        ],
        total_candidates=election.total_candidates,
        is_active=election.is_active,
        created_at=election.created_at,
        updated_at=election.updated_at
    )


@router.post("/{election_id}/status")
async def update_election_status(
    election_id: UUID,
    status_update: ElectionStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.ELECTION_OFFICIAL]))
) -> dict:
    """
    Update the status of an election.
    Status transitions are validated.
    """
    election_service = ElectionService(db)

    try:
        new_status = ElectionStatus(status_update.status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status: {status_update.status}"
        )

    success, error = await election_service.update_status(election_id, new_status)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )

    return {"message": f"Status updated to {new_status.value}"}


@router.post("/{election_id}/keys")
async def setup_election_keys(
    election_id: UUID,
    key_setup: ElectionKeySetup,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
) -> dict:
    """
    Set up the election encryption keys.
    Requires 5 encrypted key shares for threshold decryption.
    """
    election_service = ElectionService(db)

    success, error = await election_service.set_election_keys(
        election_id=election_id,
        public_key=key_setup.public_key,
        key_shares=key_setup.key_shares
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )

    return {"message": "Election keys configured"}


@router.post("/{election_id}/eligibility")
async def setup_voter_eligibility(
    election_id: UUID,
    eligibility: VoterEligibilitySetup,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.ELECTION_OFFICIAL]))
) -> dict:
    """
    Set up the voter eligibility Merkle root.
    """
    election_service = ElectionService(db)

    success, error = await election_service.set_voter_eligibility(
        election_id=election_id,
        merkle_root=eligibility.merkle_root
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )

    return {"message": "Voter eligibility configured"}


@router.post("/{election_id}/candidates", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
async def add_candidate(
    election_id: UUID,
    candidate_data: CandidateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.ELECTION_OFFICIAL]))
) -> CandidateResponse:
    """
    Add a candidate to an election.
    """
    election_service = ElectionService(db)

    try:
        candidate = await election_service.add_candidate(election_id, candidate_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found"
        )

    return CandidateResponse(
        id=candidate.id,
        election_id=candidate.election_id,
        name=candidate.name,
        party=candidate.party,
        description=candidate.description,
        symbol_number=candidate.symbol_number,
        photo_url=candidate.photo_url,
        display_order=candidate.display_order,
        created_at=candidate.created_at
    )


@router.delete("/{election_id}/candidates/{candidate_id}")
async def remove_candidate(
    election_id: UUID,
    candidate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.ELECTION_OFFICIAL]))
) -> dict:
    """
    Remove a candidate from an election.
    """
    election_service = ElectionService(db)

    try:
        success = await election_service.remove_candidate(election_id, candidate_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found"
        )

    return {"message": "Candidate removed"}


@router.delete("/{election_id}")
async def delete_election(
    election_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
) -> dict:
    """
    Delete a draft election.
    """
    election_service = ElectionService(db)

    try:
        success = await election_service.delete_election(election_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found"
        )

    return {"message": "Election deleted"}
