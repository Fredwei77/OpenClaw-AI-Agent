"""
Unit tests for backend/api/auth.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from fastapi import HTTPException

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.api.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
    UserCreate,
)


class TestPasswordHashing:
    """Test password hashing functions."""

    def test_hash_password_returns_string(self):
        """Hash should return a bcrypt hash string."""
        hashed = hash_password("testpassword")
        assert isinstance(hashed, str)
        assert hashed.startswith("$2b$")

    def test_hash_password_different_each_time(self):
        """Each hash should be different due to random salt."""
        hash1 = hash_password("testpassword")
        hash2 = hash_password("testpassword")
        assert hash1 != hash2

    def test_verify_password_correct(self):
        """Verify should return True for correct password."""
        hashed = hash_password("testpassword")
        assert verify_password("testpassword", hashed) is True

    def test_verify_password_incorrect(self):
        """Verify should return False for incorrect password."""
        hashed = hash_password("testpassword")
        assert verify_password("wrongpassword", hashed) is False


class TestJWTTokens:
    """Test JWT token creation and decoding."""

    def test_create_access_token(self):
        """Should create a valid JWT token."""
        token = create_access_token({"sub": "1", "email": "test@example.com"})
        assert isinstance(token, str)
        assert len(token) > 20

    def test_decode_token_valid(self):
        """Should decode a valid token."""
        os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing"
        token = create_access_token({"sub": "123", "email": "test@example.com"})
        token_data = decode_token(token)
        assert token_data.user_id == 123

    def test_decode_token_expired(self):
        """Should raise HTTPException for expired token."""
        from fastapi import HTTPException
        os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing"
        token = create_access_token(
            {"sub": "1", "email": "test@example.com"},
            expires_delta=timedelta(seconds=-1)
        )
        with pytest.raises(HTTPException) as exc_info:
            decode_token(token)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_decode_token_invalid(self):
        """Should raise HTTPException for invalid token."""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            decode_token("invalid.token.here")
        assert exc_info.value.status_code == 401


class TestUserCreateModel:
    """Test UserCreate Pydantic model validation."""

    def test_valid_user_create(self):
        """Should accept valid user data."""
        user = UserCreate(email="test@example.com", password="password123")
        assert user.email == "test@example.com"
        assert user.password == "password123"
        assert user.role == "user"

    def test_valid_user_create_with_role(self):
        """Should accept valid user with role."""
        user = UserCreate(email="test@example.com", password="password123", role="moderator")
        assert user.role == "moderator"

    def test_invalid_email_rejected(self):
        """Should reject invalid email format."""
        with pytest.raises(ValueError):
            UserCreate(email="not-an-email", password="password123")

    def test_short_password_rejected(self):
        """Should reject password less than 6 characters."""
        with pytest.raises(ValueError):
            UserCreate(email="test@example.com", password="12345")