"""
API dependencies for authentication and authorization.
"""
from typing import List, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User, UserRole
from app.services.auth_service import AuthService


security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Get the current authenticated user from the JWT token.
    Returns None if no valid token is provided.
    """
    if not credentials:
        return None

    token = credentials.credentials
    payload = decode_token(token)

    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(user_id)

    if not user or not user.is_active:
        return None

    return user


async def require_authentication(
    current_user: Optional[User] = Depends(get_current_user)
) -> User:
    """
    Require a valid authenticated user.
    Raises 401 if not authenticated.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


def require_role(allowed_roles: List[UserRole]):
    """
    Factory function to create a dependency that requires specific roles.
    """
    async def role_checker(
        current_user: User = Depends(require_authentication)
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user

    return role_checker


async def get_verified_voter(
    current_user: User = Depends(require_authentication)
) -> User:
    """
    Require an authenticated and verified voter.
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Voter verification required"
        )
    return current_user
