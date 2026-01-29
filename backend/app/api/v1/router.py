"""
API v1 router configuration.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, elections, votes, tally, verification


api_router = APIRouter()

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

api_router.include_router(
    elections.router,
    prefix="/elections",
    tags=["Elections"]
)

api_router.include_router(
    votes.router,
    prefix="/votes",
    tags=["Voting"]
)

api_router.include_router(
    tally.router,
    prefix="/tally",
    tags=["Tally"]
)

api_router.include_router(
    verification.router,
    prefix="/verification",
    tags=["Verification"]
)
