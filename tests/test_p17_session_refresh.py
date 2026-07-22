"""Regression coverage for durable frontend sessions and refresh tokens."""

from pathlib import Path

from backend.api.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    Token,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)


def test_refresh_token_contract_and_default_lifetimes():
    refresh = create_refresh_token({"sub": "7", "email": "user@example.com"})
    access = create_access_token({"sub": "7", "email": "user@example.com"})
    response = Token(access_token=access, refresh_token=refresh)

    assert decode_refresh_token(response.refresh_token).user_id == 7
    assert response.expires_in == ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert ACCESS_TOKEN_EXPIRE_MINUTES >= 60
    assert REFRESH_TOKEN_EXPIRE_DAYS >= 7


def test_frontend_renews_session_without_forced_logout():
    frontend = Path("frontend/src/App.jsx").read_text(encoding="utf-8")
    auth = Path("backend/api/auth.py").read_text(encoding="utf-8")
    env = Path(".env.example").read_text(encoding="utf-8")

    assert "refreshSessionToken" in frontend
    assert "getSessionAccessToken" in frontend
    assert "authenticatedFetch" in frontend
    assert "visibilitychange" in frontend
    assert "localStorage.setItem('refresh_token'" in frontend
    assert "RefreshTokenRequest" in auth
    assert "decode_refresh_token" in auth
    assert "ACCESS_TOKEN_EXPIRE_MINUTES=1440" in env
    assert "REFRESH_TOKEN_EXPIRE_DAYS=30" in env
