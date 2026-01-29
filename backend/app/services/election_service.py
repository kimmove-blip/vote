"""
Election management service.
"""
import uuid
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.election import Election, Candidate, ElectionStatus
from app.schemas.election import ElectionCreate, ElectionUpdate, CandidateCreate


class ElectionService:
    """Service for election management operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_election(
        self,
        election_data: ElectionCreate,
        created_by: Optional[uuid.UUID] = None
    ) -> Election:
        """Create a new election with candidates."""
        election = Election(
            title=election_data.title,
            description=election_data.description,
            start_time=election_data.start_time,
            end_time=election_data.end_time,
            status=ElectionStatus.DRAFT,
            created_by=created_by,
        )

        self.db.add(election)
        await self.db.flush()

        # Add candidates
        for idx, candidate_data in enumerate(election_data.candidates):
            candidate = Candidate(
                election_id=election.id,
                name=candidate_data.name,
                party=candidate_data.party,
                description=candidate_data.description,
                symbol_number=candidate_data.symbol_number,
                photo_url=candidate_data.photo_url,
                display_order=candidate_data.display_order or idx,
            )
            self.db.add(candidate)

        await self.db.commit()
        await self.db.refresh(election)

        return election

    async def get_election(self, election_id: uuid.UUID) -> Optional[Election]:
        """Get an election by ID with candidates."""
        result = await self.db.execute(
            select(Election)
            .options(selectinload(Election.candidates))
            .where(Election.id == election_id)
        )
        return result.scalar_one_or_none()

    async def get_elections(
        self,
        status: Optional[ElectionStatus] = None,
        include_draft: bool = False
    ) -> List[Election]:
        """Get all elections, optionally filtered by status."""
        query = select(Election).options(selectinload(Election.candidates))

        if status:
            query = query.where(Election.status == status)
        elif not include_draft:
            query = query.where(Election.status != ElectionStatus.DRAFT)

        query = query.order_by(Election.created_at.desc())
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def get_active_elections(self) -> List[Election]:
        """Get all currently active elections."""
        now = datetime.utcnow()
        result = await self.db.execute(
            select(Election)
            .options(selectinload(Election.candidates))
            .where(
                Election.status == ElectionStatus.ACTIVE,
                Election.start_time <= now,
                Election.end_time > now
            )
            .order_by(Election.end_time.asc())
        )
        return list(result.scalars().all())

    async def update_election(
        self,
        election_id: uuid.UUID,
        election_data: ElectionUpdate
    ) -> Optional[Election]:
        """Update an election."""
        election = await self.get_election(election_id)
        if not election:
            return None

        # Only allow updates to draft elections
        if election.status != ElectionStatus.DRAFT:
            raise ValueError("Cannot modify a non-draft election")

        update_data = election_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(election, field, value)

        election.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(election)

        return election

    async def update_status(
        self,
        election_id: uuid.UUID,
        new_status: ElectionStatus
    ) -> Tuple[bool, Optional[str]]:
        """Update election status with validation."""
        election = await self.get_election(election_id)
        if not election:
            return False, "Election not found"

        # Validate status transition
        valid_transitions = {
            ElectionStatus.DRAFT: [ElectionStatus.PENDING, ElectionStatus.CANCELLED],
            ElectionStatus.PENDING: [ElectionStatus.ACTIVE, ElectionStatus.CANCELLED],
            ElectionStatus.ACTIVE: [ElectionStatus.CLOSED, ElectionStatus.CANCELLED],
            ElectionStatus.CLOSED: [ElectionStatus.TALLYING],
            ElectionStatus.TALLYING: [ElectionStatus.COMPLETED],
            ElectionStatus.COMPLETED: [],
            ElectionStatus.CANCELLED: [],
        }

        if new_status not in valid_transitions.get(election.status, []):
            return False, f"Invalid status transition from {election.status} to {new_status}"

        # Additional validation
        if new_status == ElectionStatus.ACTIVE:
            if not election.election_public_key:
                return False, "Election public key not set"
            if not election.voter_merkle_root:
                return False, "Voter eligibility not configured"
            if len(election.candidates) < 2:
                return False, "Election must have at least 2 candidates"

        election.status = new_status
        election.updated_at = datetime.utcnow()
        await self.db.commit()

        return True, None

    async def set_election_keys(
        self,
        election_id: uuid.UUID,
        public_key: str,
        key_shares: List[str]
    ) -> Tuple[bool, Optional[str]]:
        """Set the election encryption keys."""
        election = await self.get_election(election_id)
        if not election:
            return False, "Election not found"

        if election.status != ElectionStatus.DRAFT:
            return False, "Can only set keys for draft elections"

        if len(key_shares) != 5:
            return False, "Must provide exactly 5 key shares"

        election.election_public_key = public_key
        election.election_private_key_shares = ",".join(key_shares)
        election.updated_at = datetime.utcnow()
        await self.db.commit()

        return True, None

    async def set_voter_eligibility(
        self,
        election_id: uuid.UUID,
        merkle_root: str
    ) -> Tuple[bool, Optional[str]]:
        """Set the voter eligibility Merkle root."""
        election = await self.get_election(election_id)
        if not election:
            return False, "Election not found"

        if election.status != ElectionStatus.DRAFT:
            return False, "Can only set eligibility for draft elections"

        election.voter_merkle_root = merkle_root
        election.updated_at = datetime.utcnow()
        await self.db.commit()

        return True, None

    async def add_candidate(
        self,
        election_id: uuid.UUID,
        candidate_data: CandidateCreate
    ) -> Optional[Candidate]:
        """Add a candidate to an election."""
        election = await self.get_election(election_id)
        if not election:
            return None

        if election.status != ElectionStatus.DRAFT:
            raise ValueError("Cannot add candidates to a non-draft election")

        candidate = Candidate(
            election_id=election_id,
            name=candidate_data.name,
            party=candidate_data.party,
            description=candidate_data.description,
            symbol_number=candidate_data.symbol_number,
            photo_url=candidate_data.photo_url,
            display_order=candidate_data.display_order,
        )

        self.db.add(candidate)
        await self.db.commit()
        await self.db.refresh(candidate)

        return candidate

    async def remove_candidate(
        self,
        election_id: uuid.UUID,
        candidate_id: uuid.UUID
    ) -> bool:
        """Remove a candidate from an election."""
        election = await self.get_election(election_id)
        if not election:
            return False

        if election.status != ElectionStatus.DRAFT:
            raise ValueError("Cannot remove candidates from a non-draft election")

        result = await self.db.execute(
            select(Candidate).where(
                Candidate.id == candidate_id,
                Candidate.election_id == election_id
            )
        )
        candidate = result.scalar_one_or_none()

        if not candidate:
            return False

        await self.db.delete(candidate)
        await self.db.commit()

        return True

    async def delete_election(self, election_id: uuid.UUID) -> bool:
        """Delete a draft election."""
        election = await self.get_election(election_id)
        if not election:
            return False

        if election.status != ElectionStatus.DRAFT:
            raise ValueError("Can only delete draft elections")

        await self.db.delete(election)
        await self.db.commit()

        return True
