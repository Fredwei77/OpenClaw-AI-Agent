"""Regression tests for the Electron 1.1 desktop release."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_electron_installer_version_and_resources_are_current():
    package = json.loads((ROOT / "desktop" / "electron_app" / "package.json").read_text(encoding="utf-8"))
    assert package["version"] == "1.1.0"
    resources = package["build"]["extraResources"]
    assert {"from": "../../frontend/dist", "to": "www"} in resources
    assert {"from": "../../backend", "to": "backend"} in resources
    assert {"from": "../../database", "to": "database"} in resources
    assert {"from": "../../.env.example", "to": "config/.env.example"} in resources


def test_electron_uses_generated_user_config_and_real_app_version():
    main = (ROOT / "desktop" / "electron_app" / "main.js").read_text(encoding="utf-8")
    assert "ensureUserConfig()" in main
    assert "OPENCLAW_ENV_FILE" in main
    assert "crypto.randomBytes(32)" in main
    assert "app.getVersion()" in main
    assert "import asyncpg, bcrypt, fastapi, uvicorn" in main


def test_backend_applies_additive_desktop_schema_upgrade():
    db = (ROOT / "backend" / "db.py").read_text(encoding="utf-8")
    app = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert "async def ensure_runtime_schema" in db
    assert "CREATE TABLE IF NOT EXISTS marketing_campaigns" in db
    assert "await ensure_runtime_schema()" in app
