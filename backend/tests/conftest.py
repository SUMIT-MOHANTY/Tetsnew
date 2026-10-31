"""
DERTOUR Test Configuration and Fixtures
Pytest configuration with async database support
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.main import create_application
from app.database import get_db_session, Base
from app.models.user import User, UserRole
from app.models.initiative import Initiative, InitiativeStatus, InitiativePriority
from app.core.security import create_access_token, get_password_hash

# Test database URL - use SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

# Create async engine for tests
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=NullPool,
    echo=False,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def setup_database():
    """Set up the test database."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session(setup_database) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async with AsyncSessionLocal() as session:
        yield session
        # Rollback after test
        await session.rollback()


@pytest.fixture
def test_app():
    """Create a test FastAPI application."""
    app = create_application()
    return app


@pytest.fixture
def client(test_app):
    """Create a test client."""
    return TestClient(test_app)


@pytest_asyncio.fixture
async def async_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    async with AsyncClient(app=test_app, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=str(uuid4()),
        email="test@dertour.com",
        name="Test User",
        hashed_password=get_password_hash("testpassword"),
        role=UserRole.TEAM_MEMBER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_pmo_user(db_session: AsyncSession) -> User:
    """Create a test PMO user."""
    user = User(
        id=str(uuid4()),
        email="pmo@dertour.com",
        name="PMO User",
        hashed_password=get_password_hash("testpassword"),
        role=UserRole.PMO,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_executive_user(db_session: AsyncSession) -> User:
    """Create a test executive user."""
    user = User(
        id=str(uuid4()),
        email="executive@dertour.com",
        name="Executive User",
        hashed_password=get_password_hash("testpassword"),
        role=UserRole.EXECUTIVE,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_initiative(db_session: AsyncSession, test_user: User) -> Initiative:
    """Create a test initiative."""
    initiative = Initiative(
        id=str(uuid4()),
        code="TEST-001",
        name="Test Initiative",
        description="A test initiative for QA",
        status=InitiativeStatus.ACTIVE,
        priority=InitiativePriority.MEDIUM,
        owner_id=test_user.id,
        start_date=datetime.now(),
        target_end_date=datetime.now() + timedelta(days=90),
        budget=100000.0,
        benefit_target=50000.0,
    )
    db_session.add(initiative)
    await db_session.commit()
    await db_session.refresh(initiative)
    return initiative


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Generate authentication headers for test user."""
    token = create_access_token({"sub": test_user.id, "role": test_user.role.value})
    return {
        "Authorization": f"Bearer {token}",
        "X-Role": test_user.role.value,
    }


@pytest.fixture
def pmo_auth_headers(test_pmo_user: User) -> dict:
    """Generate authentication headers for PMO user."""
    token = create_access_token({"sub": test_pmo_user.id, "role": test_pmo_user.role.value})
    return {
        "Authorization": f"Bearer {token}",
        "X-Role": test_pmo_user.role.value,
    }


@pytest.fixture
def executive_auth_headers(test_executive_user: User) -> dict:
    """Generate authentication headers for executive user."""
    token = create_access_token({"sub": test_executive_user.id, "role": test_executive_user.role.value})
    return {
        "Authorization": f"Bearer {token}",
        "X-Role": test_executive_user.role.value,
    }


@pytest.fixture
def sample_agent_action_data() -> dict:
    """Sample data for agent action submission."""
    return {
        "plan": "Update milestone dates for initiative TEST-001 based on recent delays",
        "evidence": {
            "data_sources": ["milestone_tracker", "dependency_graph", "risk_register"],
            "reasoning_steps": [
                "Analyzed current milestone completion rates",
                "Identified 3 blocked dependencies",
                "Calculated new realistic timeline"
            ],
            "alternative_considered": [
                "Keep original dates and accept risk",
                "Reduce scope to meet deadline",
                "Request additional resources"
            ],
            "risk_assessment": "Low risk - dates based on actual team velocity and resolved blockers"
        },
        "confidence": 0.85,
        "tool_activity": "milestone_analyzer_v2.3 -> dependency_checker -> date_calculator",
        "request_type": "MATERIAL_ACTION",
        "initiative_id": None,
    }


@pytest.fixture
def sample_approval_decision_data() -> dict:
    """Sample data for approval decision."""
    return {
        "decision": "APPROVED",
        "notes": "Approved after reviewing evidence. Timeline adjustments are reasonable.",
        "conditional_terms": None,
    }


@pytest.fixture
def sample_rejection_data() -> dict:
    """Sample data for rejection."""
    return {
        "decision": "REJECTED",
        "notes": "Insufficient evidence for timeline changes. Please provide resource analysis.",
        "conditional_terms": None,
    }


# Configure pytest-asyncio
pytest_plugins = ["pytest_asyncio"]
