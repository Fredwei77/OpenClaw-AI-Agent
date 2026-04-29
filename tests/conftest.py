"""
Pytest configuration and shared fixtures for OpenClaw AI Agent tests.
"""

import asyncio
import os
import sys
from typing import Generator

import pytest
from fastapi.testclient import TestClient

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db_pool(monkeypatch):
    """Mock database pool for tests that don't need real DB."""
    class MockPool:
        async def acquire(self):
            return MockConnection()
        async def release(self, conn):
            pass
        async def close(self):
            pass

    class MockConnection:
        async def fetchval(self, query, *args):
            return 0
        async def fetch(self, query, *args):
            return []
        async def execute(self, query, *args):
            return "OK"

    pool = MockPool()

    # Mock get_db_pool function
    import backend.db as db_module
    monkeypatch.setattr(db_module, "get_db_pool", lambda: pool)
    return pool


@pytest.fixture
def test_user():
    """Return a test user dict."""
    return {
        "email": "test@example.com",
        "password": "testpassword123",
        "name": "Test User"
    }


@pytest.fixture
def auth_headers(test_user):
    """Generate auth token for test user (mock)."""
    # In real tests, register/login to get real token
    # For unit tests, we can mock the token
    import jwt
    from datetime import datetime, timedelta

    payload = {
        "sub": "1",
        "email": test_user["email"],
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    token = jwt.encode(payload, os.getenv("JWT_SECRET_KEY", "test-secret"), algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}