"""
Application configuration settings.
"""
from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Application
    APP_NAME: str = "Blockchain Voting System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/voting_db"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT Authentication
    JWT_SECRET_KEY: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "RS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # FIDO2 Configuration
    FIDO2_RP_ID: str = "voting.example.com"
    FIDO2_RP_NAME: str = "Blockchain Voting System"
    FIDO2_ORIGIN: str = "https://voting.example.com"

    # DID Configuration
    DID_RESOLVER_URL: str = "https://did-resolver.example.com"
    OMNIONE_API_URL: str = "https://omnione.example.com/api"
    OMNIONE_API_KEY: str = ""

    # Hyperledger Fabric
    FABRIC_NETWORK_CONFIG: str = "/etc/fabric/network-config.yaml"
    FABRIC_CHANNEL_NAME: str = "votingchannel"
    FABRIC_CHAINCODE_NAME: str = "votecontract"
    FABRIC_ORG_NAME: str = "NEC"
    FABRIC_USER_NAME: str = "Admin"
    FABRIC_PEER_ENDPOINT: str = "grpcs://peer0.nec.example.com:7051"

    # AWS Configuration
    AWS_REGION: str = "ap-northeast-2"
    AWS_KMS_KEY_ID: str = ""
    AWS_SQS_QUEUE_URL: str = ""

    # Cryptography
    ELECTION_KEY_THRESHOLD: int = 3
    ELECTION_KEY_TOTAL_SHARES: int = 5
    ZKP_PROVING_KEY_PATH: str = "/etc/zkp/proving.key"
    ZKP_VERIFICATION_KEY_PATH: str = "/etc/zkp/verification.key"

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # CORS
    CORS_ORIGINS: List[str] = ["https://voting.example.com", "http://localhost:3000"]

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
