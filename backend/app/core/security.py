"""
Security utilities for authentication and authorization.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import hashlib
import secrets

from jose import jwt, JWTError
from passlib.context import CryptContext
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization

from app.core.config import settings


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def generate_vote_token() -> str:
    """Generate a secure one-time vote token."""
    return secrets.token_urlsafe(32)


def hash_vote_token(token: str) -> str:
    """Hash a vote token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_nullifier(voter_id: str, election_id: str, secret: str) -> str:
    """
    Generate a nullifier for double-voting prevention.
    The nullifier is deterministic but doesn't reveal voter identity.
    """
    data = f"{voter_id}:{election_id}:{secret}"
    return hashlib.sha256(data.encode()).hexdigest()


def generate_verification_code() -> str:
    """Generate a human-readable verification code for receipts."""
    return secrets.token_hex(8).upper()


def generate_key_pair() -> tuple:
    """Generate an RSA key pair for encryption."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
    )
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    return private_pem.decode(), public_pem.decode()
