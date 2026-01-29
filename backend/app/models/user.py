"""
User database model.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, DateTime, Boolean, Text, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
import enum

from app.core.database import Base


class UserRole(str, enum.Enum):
    """User role enumeration."""
    VOTER = "voter"
    ADMIN = "admin"
    AUDITOR = "auditor"
    ELECTION_OFFICIAL = "election_official"


class User(Base):
    """
    User model for authentication and authorization.
    Note: Voter identity is kept separate from votes for anonymity.
    """

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # DID-based identity
    did = Column(String(200), unique=True, nullable=False, index=True)
    did_document = Column(JSONB, nullable=True)

    # Basic info (from verified DID claims)
    display_name = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)

    # Role and permissions
    role = Column(Enum(UserRole), default=UserRole.VOTER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)

    # FIDO2 credentials
    fido_credentials = Column(JSONB, nullable=True)

    # Voter eligibility (encrypted/hashed)
    eligibility_merkle_proof = Column(Text, nullable=True)

    # Session management
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip_hash = Column(String(66), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, did='{self.did[:30]}...', role={self.role})>"

    def add_fido_credential(self, credential_id: str, public_key: str, sign_count: int) -> None:
        """Add a FIDO2 credential."""
        if self.fido_credentials is None:
            self.fido_credentials = []

        self.fido_credentials.append({
            "credential_id": credential_id,
            "public_key": public_key,
            "sign_count": sign_count,
            "created_at": datetime.utcnow().isoformat()
        })

    def get_fido_credential(self, credential_id: str) -> Optional[dict]:
        """Get a specific FIDO2 credential."""
        if not self.fido_credentials:
            return None

        for cred in self.fido_credentials:
            if cred["credential_id"] == credential_id:
                return cred
        return None

    def update_fido_sign_count(self, credential_id: str, new_sign_count: int) -> bool:
        """Update the sign count for a FIDO2 credential."""
        if not self.fido_credentials:
            return False

        for cred in self.fido_credentials:
            if cred["credential_id"] == credential_id:
                cred["sign_count"] = new_sign_count
                return True
        return False
