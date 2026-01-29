"""
Authentication-related Pydantic schemas.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class DIDVerifyRequest(BaseModel):
    """Request to verify a DID Verifiable Presentation."""

    verifiable_presentation: Dict[str, Any] = Field(
        ...,
        description="The Verifiable Presentation from the DID wallet"
    )
    challenge: str = Field(
        ...,
        description="The challenge that was signed"
    )
    domain: Optional[str] = Field(
        None,
        description="The domain for which the VP was created"
    )


class DIDVerifyResponse(BaseModel):
    """Response from DID verification."""

    verified: bool = Field(..., description="Whether the VP is valid")
    did: Optional[str] = Field(None, description="The verified DID")
    claims: Optional[Dict[str, Any]] = Field(
        None,
        description="Verified claims from the VP"
    )
    error: Optional[str] = Field(None, description="Error message if verification failed")


class FIDORegisterRequest(BaseModel):
    """Request to register a FIDO2 credential."""

    attestation_object: str = Field(
        ...,
        description="Base64-encoded attestation object"
    )
    client_data_json: str = Field(
        ...,
        description="Base64-encoded client data JSON"
    )


class FIDORegisterResponse(BaseModel):
    """Response from FIDO2 registration."""

    success: bool = Field(..., description="Whether registration succeeded")
    credential_id: Optional[str] = Field(
        None,
        description="The registered credential ID"
    )
    error: Optional[str] = Field(None, description="Error message if registration failed")


class FIDOAuthenticateRequest(BaseModel):
    """Request to authenticate with FIDO2."""

    credential_id: str = Field(
        ...,
        description="The credential ID to authenticate with"
    )
    authenticator_data: str = Field(
        ...,
        description="Base64-encoded authenticator data"
    )
    client_data_json: str = Field(
        ...,
        description="Base64-encoded client data JSON"
    )
    signature: str = Field(
        ...,
        description="Base64-encoded signature"
    )


class FIDOAuthenticateResponse(BaseModel):
    """Response from FIDO2 authentication."""

    success: bool = Field(..., description="Whether authentication succeeded")
    error: Optional[str] = Field(None, description="Error message if authentication failed")


class FIDOChallengeRequest(BaseModel):
    """Request for a FIDO2 challenge."""

    user_id: Optional[str] = Field(None, description="User ID for registration")


class FIDOChallengeResponse(BaseModel):
    """Response with FIDO2 challenge."""

    challenge: str = Field(..., description="Base64-encoded challenge")
    rp_id: str = Field(..., description="Relying party ID")
    rp_name: str = Field(..., description="Relying party name")
    user_id: Optional[str] = Field(None, description="User ID for registration")
    timeout: int = Field(default=60000, description="Timeout in milliseconds")
    allowed_credentials: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Allowed credentials for authentication"
    )


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user_id: str = Field(..., description="User ID")
    role: str = Field(..., description="User role")


class TokenRefreshRequest(BaseModel):
    """Request to refresh an access token."""

    refresh_token: str = Field(..., description="The refresh token")


class UserInfoResponse(BaseModel):
    """User information response."""

    id: str = Field(..., description="User ID")
    did: str = Field(..., description="User DID")
    display_name: Optional[str] = Field(None, description="Display name")
    role: str = Field(..., description="User role")
    is_verified: bool = Field(..., description="Whether the user is verified")
    created_at: datetime = Field(..., description="Account creation time")
