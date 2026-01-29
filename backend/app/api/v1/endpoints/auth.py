"""
Authentication API endpoints.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.auth_service import AuthService
from app.schemas.auth import (
    DIDVerifyRequest,
    DIDVerifyResponse,
    FIDORegisterRequest,
    FIDORegisterResponse,
    FIDOAuthenticateRequest,
    FIDOAuthenticateResponse,
    FIDOChallengeRequest,
    FIDOChallengeResponse,
    TokenResponse,
    TokenRefreshRequest,
    UserInfoResponse,
)
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.core.config import settings


router = APIRouter()


@router.post("/did/challenge")
async def get_did_challenge() -> dict:
    """Get a challenge for DID verification."""
    import secrets
    challenge = secrets.token_urlsafe(32)
    return {
        "challenge": challenge,
        "domain": settings.FIDO2_RP_ID,
        "expires_in": 300  # 5 minutes
    }


@router.post("/did/verify", response_model=DIDVerifyResponse)
async def verify_did(
    request: DIDVerifyRequest,
    db: AsyncSession = Depends(get_db)
) -> DIDVerifyResponse:
    """
    Verify a DID Verifiable Presentation and authenticate the user.
    """
    auth_service = AuthService(db)

    verified, did, claims, error = await auth_service.verify_did_presentation(
        verifiable_presentation=request.verifiable_presentation,
        challenge=request.challenge,
        domain=request.domain
    )

    if not verified:
        return DIDVerifyResponse(
            verified=False,
            error=error
        )

    return DIDVerifyResponse(
        verified=True,
        did=did,
        claims=claims
    )


@router.post("/did/login", response_model=TokenResponse)
async def did_login(
    request: DIDVerifyRequest,
    db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """
    Complete DID authentication and get access tokens.
    """
    auth_service = AuthService(db)

    # Verify the VP
    verified, did, claims, error = await auth_service.verify_did_presentation(
        verifiable_presentation=request.verifiable_presentation,
        challenge=request.challenge,
        domain=request.domain
    )

    if not verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error or "DID verification failed"
        )

    # Get or create user
    user = await auth_service.get_or_create_user(did, claims or {})

    # Create tokens
    tokens = auth_service.create_tokens(user)

    return TokenResponse(**tokens)


@router.post("/fido/challenge", response_model=FIDOChallengeResponse)
async def get_fido_challenge(
    request: FIDOChallengeRequest,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> FIDOChallengeResponse:
    """
    Get a challenge for FIDO2 registration or authentication.
    """
    auth_service = AuthService(db)
    challenge = auth_service.generate_fido_challenge()

    response = FIDOChallengeResponse(
        challenge=challenge,
        rp_id=settings.FIDO2_RP_ID,
        rp_name=settings.FIDO2_RP_NAME,
        timeout=60000,
    )

    if current_user:
        response.user_id = str(current_user.id)
        # Get existing credentials for authentication
        if current_user.fido_credentials:
            response.allowed_credentials = [
                {"id": cred["credential_id"], "type": "public-key"}
                for cred in current_user.fido_credentials
            ]

    return response


@router.post("/fido/register", response_model=FIDORegisterResponse)
async def register_fido(
    request: FIDORegisterRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> FIDORegisterResponse:
    """
    Register a FIDO2 credential for biometric authentication.
    """
    auth_service = AuthService(db)

    success, credential_id, error = await auth_service.register_fido_credential(
        user_id=str(current_user.id),
        attestation_object=request.attestation_object,
        client_data_json=request.client_data_json
    )

    return FIDORegisterResponse(
        success=success,
        credential_id=credential_id,
        error=error
    )


@router.post("/fido/authenticate", response_model=TokenResponse)
async def authenticate_fido(
    request: FIDOAuthenticateRequest,
    db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """
    Authenticate using FIDO2 biometric credential.
    """
    auth_service = AuthService(db)

    # Note: In production, you'd get user_id from a session or the credential_id lookup
    # This is simplified for the example
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="FIDO authentication requires session context. Use DID login first."
    )


@router.post("/token/refresh", response_model=TokenResponse)
async def refresh_token(
    request: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """
    Refresh an access token using a refresh token.
    """
    auth_service = AuthService(db)
    tokens = await auth_service.refresh_access_token(request.refresh_token)

    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    return TokenResponse(**tokens)


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
) -> UserInfoResponse:
    """
    Get the current authenticated user's information.
    """
    return UserInfoResponse(
        id=str(current_user.id),
        did=current_user.did,
        display_name=current_user.display_name,
        role=current_user.role.value,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at
    )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Logout the current user (invalidate tokens on client side).
    """
    # In a production system, you might want to:
    # 1. Add the token to a blocklist
    # 2. Clear any server-side sessions
    # For JWT-based auth, client-side token deletion is usually sufficient
    return {"message": "Logged out successfully"}
