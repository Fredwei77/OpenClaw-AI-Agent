"""Regression tests for the productized single-machine runtime status."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_system_status_router_is_registered():
    main = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert 'prefix="/api/system"' in main
    assert "system.router" in main


def test_runtime_status_never_returns_secret_values():
    system_api = (ROOT / "backend" / "api" / "system.py").read_text(encoding="utf-8")
    assert '"openrouter_api_key": bool(API_KEY)' in system_api
    assert '"jwt_secret": bool(os.getenv("JWT_SECRET_KEY"))' in system_api
    assert '"database_url": bool(os.getenv("DATABASE_URL"))' in system_api
    assert '"api_key": API_KEY' not in system_api


def test_frontend_uses_runtime_status_instead_of_fake_settings():
    app = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
    assert "/api/system/status" in app
    assert "sk-proj-xxxxxxxx" not in app
    assert "GLM-4-Plus (Zhipu)" not in app
    assert "handleTestWebhook" not in app
    assert "scripts/dev.ps1 -Restart" in app
