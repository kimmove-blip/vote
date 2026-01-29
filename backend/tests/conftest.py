"""
Pytest configuration and fixtures for backend tests.
"""
import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from httpx import AsyncClient

from app.main import app
from app.core.database import Base, get_db
from app.models.user import User, UserRole
from app.models.election import Election, Candidate, ElectionStatus
from app.core.security import create_access_token


# Test database URL (SQLite for testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(test_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with the test database."""
    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(test_db: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        did="did:omni:test123456789",
        display_name="Test User",
        role=UserRole.VOTER,
        is_verified=True,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_admin(test_db: AsyncSession) -> User:
    """Create a test admin user."""
    user = User(
        did="did:omni:admin123456789",
        display_name="Admin User",
        role=UserRole.ADMIN,
        is_verified=True,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict:
    """Create authentication headers for a test user."""
    token = create_access_token({
        "sub": str(test_user.id),
        "did": test_user.did,
        "role": test_user.role.value,
    })
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_auth_headers(test_admin: User) -> dict:
    """Create authentication headers for a test admin."""
    token = create_access_token({
        "sub": str(test_admin.id),
        "did": test_admin.did,
        "role": test_admin.role.value,
    })
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def test_election(test_db: AsyncSession, test_admin: User) -> Election:
    """Create a test election with candidates."""
    from datetime import datetime, timedelta

    election = Election(
        title="Test Election 2024",
        description="A test election for unit testing",
        status=ElectionStatus.ACTIVE,
        start_time=datetime.utcnow() - timedelta(hours=1),
        end_time=datetime.utcnow() + timedelta(days=1),
        voter_merkle_root="0x" + "a" * 64,
        election_public_key='{"p": "123", "q": "456", "g": "2", "h": "789"}',
        created_by=test_admin.id,
    )
    test_db.add(election)
    await test_db.flush()

    # Add candidates
    candidates = [
        Candidate(
            election_id=election.id,
            name="Candidate A",
            party="Party Alpha",
            symbol_number=1,
            display_order=1,
        ),
        Candidate(
            election_id=election.id,
            name="Candidate B",
            party="Party Beta",
            symbol_number=2,
            display_order=2,
        ),
        Candidate(
            election_id=election.id,
            name="Candidate C",
            party="Party Gamma",
            symbol_number=3,
            display_order=3,
        ),
    ]

    for candidate in candidates:
        test_db.add(candidate)

    await test_db.commit()
    await test_db.refresh(election)

    return election


@pytest.fixture
def mock_fabric_client():
    """Create a mock Fabric client."""
    mock = AsyncMock()
    mock.invoke_chaincode.return_value = {
        "success": True,
        "tx_id": "test_tx_id_123",
        "block_number": "12345",
    }
    mock.query_chaincode.return_value = {
        "votes": [],
        "verified": True,
    }
    return mock


@pytest.fixture
def mock_zkp_engine():
    """Create a mock ZKP engine."""
    mock = AsyncMock()
    mock.verify_eligibility_proof.return_value = True
    mock.verify_validity_proof.return_value = True
    return mock
