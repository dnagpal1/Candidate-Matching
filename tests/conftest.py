import asyncio
import os
from typing import Dict, Generator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Set test environment variables
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5432/test_candidate_matching"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["SECRET_KEY"] = "test_secret_key"
os.environ["ENCRYPTION_KEY"] = "test_encryption_key"
os.environ["OPENAI_API_KEY"] = "test_openai_key"
os.environ["LINKEDIN_EMAIL"] = "test@example.com"
os.environ["LINKEDIN_PASSWORD"] = "test_password"
os.environ["MAX_PROFILES_PER_DAY"] = "100"
os.environ["BROWSER_HEADLESS"] = "true"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_app() -> FastAPI:
    """Create a FastAPI test application."""
    from app.main import app
    return app


@pytest.fixture
def test_client(test_app: FastAPI) -> TestClient:
    """Create a test client for the FastAPI application."""
    return TestClient(test_app)


@pytest_asyncio.fixture
async def mock_redis() -> Dict:
    """
    Mock Redis storage for tests.
    Returns a simple dictionary that can be used as a Redis mock.
    """
    return {}


# Add more fixtures as needed, such as database setup/teardown 