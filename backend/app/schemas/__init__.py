"""
Pydantic schemas for request/response validation.
"""
from app.schemas.auth import (
    DIDVerifyRequest,
    DIDVerifyResponse,
    FIDORegisterRequest,
    FIDORegisterResponse,
    FIDOAuthenticateRequest,
    FIDOAuthenticateResponse,
    TokenResponse,
)
from app.schemas.election import (
    ElectionCreate,
    ElectionUpdate,
    ElectionResponse,
    CandidateCreate,
    CandidateResponse,
)
from app.schemas.vote import (
    VoteTokenRequest,
    VoteTokenResponse,
    VoteSubmitRequest,
    VoteSubmitResponse,
    VoteReceiptResponse,
)
from app.schemas.tally import (
    TallyStartRequest,
    TallyStatusResponse,
    TallyResultResponse,
)
from app.schemas.verification import (
    CastVerificationRequest,
    CastVerificationResponse,
)

__all__ = [
    # Auth
    "DIDVerifyRequest",
    "DIDVerifyResponse",
    "FIDORegisterRequest",
    "FIDORegisterResponse",
    "FIDOAuthenticateRequest",
    "FIDOAuthenticateResponse",
    "TokenResponse",
    # Election
    "ElectionCreate",
    "ElectionUpdate",
    "ElectionResponse",
    "CandidateCreate",
    "CandidateResponse",
    # Vote
    "VoteTokenRequest",
    "VoteTokenResponse",
    "VoteSubmitRequest",
    "VoteSubmitResponse",
    "VoteReceiptResponse",
    # Tally
    "TallyStartRequest",
    "TallyStatusResponse",
    "TallyResultResponse",
    # Verification
    "CastVerificationRequest",
    "CastVerificationResponse",
]
