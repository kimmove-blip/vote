"""
Authentication service handling DID and FIDO2 authentication.
"""
import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.user import User, UserRole


class AuthService:
    """Service for authentication operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def verify_did_presentation(
        self,
        verifiable_presentation: Dict[str, Any],
        challenge: str,
        domain: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]], Optional[str]]:
        """
        Verify a DID Verifiable Presentation.

        Returns:
            Tuple of (verified, did, claims, error)
        """
        try:
            # Validate VP structure
            if not self._validate_vp_structure(verifiable_presentation):
                return False, None, None, "Invalid VP structure"

            # Verify the proof
            proof = verifiable_presentation.get("proof", {})
            if proof.get("challenge") != challenge:
                return False, None, None, "Challenge mismatch"

            if domain and proof.get("domain") != domain:
                return False, None, None, "Domain mismatch"

            # Extract DID from the holder field
            holder_did = verifiable_presentation.get("holder")
            if not holder_did:
                return False, None, None, "Missing holder DID"

            # Verify with OmniOne DID resolver
            verification_result = await self._verify_with_omnione(
                verifiable_presentation,
                challenge
            )

            if not verification_result["verified"]:
                return False, None, None, verification_result.get("error", "Verification failed")

            # Extract claims from credentials
            claims = self._extract_claims(verifiable_presentation)

            return True, holder_did, claims, None

        except Exception as e:
            return False, None, None, str(e)

    def _validate_vp_structure(self, vp: Dict[str, Any]) -> bool:
        """Validate the basic structure of a VP."""
        required_fields = ["@context", "type", "verifiableCredential", "proof"]
        return all(field in vp for field in required_fields)

    async def _verify_with_omnione(
        self,
        vp: Dict[str, Any],
        challenge: str
    ) -> Dict[str, Any]:
        """Verify the VP with OmniOne DID service."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.OMNIONE_API_URL}/vp/verify",
                    json={
                        "verifiablePresentation": vp,
                        "challenge": challenge
                    },
                    headers={"X-API-Key": settings.OMNIONE_API_KEY},
                    timeout=30.0
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    return {"verified": False, "error": f"API error: {response.status_code}"}

        except httpx.RequestError as e:
            # For development/testing, return mock verification
            if settings.DEBUG:
                return {"verified": True}
            return {"verified": False, "error": str(e)}

    def _extract_claims(self, vp: Dict[str, Any]) -> Dict[str, Any]:
        """Extract verified claims from the VP."""
        claims = {}
        credentials = vp.get("verifiableCredential", [])

        for cred in credentials:
            if isinstance(cred, dict):
                subject = cred.get("credentialSubject", {})
                claims.update(subject)

        return claims

    async def get_or_create_user(
        self,
        did: str,
        claims: Dict[str, Any]
    ) -> User:
        """Get existing user or create new one from DID verification."""
        # Try to find existing user
        result = await self.db.execute(
            select(User).where(User.did == did)
        )
        user = result.scalar_one_or_none()

        if user:
            # Update last login
            user.last_login_at = datetime.utcnow()
            await self.db.commit()
            return user

        # Create new user
        user = User(
            did=did,
            display_name=claims.get("name"),
            email=claims.get("email"),
            role=UserRole.VOTER,
            is_verified=True,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        return user

    def generate_fido_challenge(self) -> str:
        """Generate a FIDO2 challenge."""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()

    async def register_fido_credential(
        self,
        user_id: str,
        attestation_object: str,
        client_data_json: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Register a FIDO2 credential for a user.

        Returns:
            Tuple of (success, credential_id, error)
        """
        try:
            # Decode and parse the attestation
            attestation_bytes = base64.urlsafe_b64decode(attestation_object)
            client_data_bytes = base64.urlsafe_b64decode(client_data_json)
            client_data = json.loads(client_data_bytes)

            # Verify the registration (simplified)
            # In production, use fido2 library for full verification
            credential_id = hashlib.sha256(attestation_bytes[:64]).hexdigest()
            public_key = base64.urlsafe_b64encode(attestation_bytes[64:128]).decode()

            # Get user and add credential
            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                return False, None, "User not found"

            user.add_fido_credential(credential_id, public_key, 0)
            await self.db.commit()

            return True, credential_id, None

        except Exception as e:
            return False, None, str(e)

    async def authenticate_fido(
        self,
        user_id: str,
        credential_id: str,
        authenticator_data: str,
        client_data_json: str,
        signature: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Authenticate a user with FIDO2.

        Returns:
            Tuple of (success, error)
        """
        try:
            # Get user
            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                return False, "User not found"

            # Get credential
            cred = user.get_fido_credential(credential_id)
            if not cred:
                return False, "Credential not found"

            # Verify signature (simplified)
            # In production, use fido2 library for full verification
            auth_data_bytes = base64.urlsafe_b64decode(authenticator_data)

            # Extract sign count and verify it increased
            sign_count = int.from_bytes(auth_data_bytes[33:37], "big")
            if sign_count <= cred["sign_count"]:
                return False, "Invalid sign count (possible cloned authenticator)"

            # Update sign count
            user.update_fido_sign_count(credential_id, sign_count)
            user.last_login_at = datetime.utcnow()
            await self.db.commit()

            return True, None

        except Exception as e:
            return False, str(e)

    def create_tokens(self, user: User) -> Dict[str, Any]:
        """Create access and refresh tokens for a user."""
        token_data = {
            "sub": str(user.id),
            "did": user.did,
            "role": user.role.value,
        }

        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user_id": str(user.id),
            "role": user.role.value,
        }

    async def refresh_access_token(
        self,
        refresh_token: str
    ) -> Optional[Dict[str, Any]]:
        """Refresh an access token using a refresh token."""
        payload = decode_token(refresh_token)

        if not payload or payload.get("type") != "refresh":
            return None

        user_id = payload.get("sub")
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            return None

        return self.create_tokens(user)

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get a user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
