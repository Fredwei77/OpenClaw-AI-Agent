"""Coverage for real AI generation policy and signed outbound delivery."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from automation.delivery import sign_payload  # noqa: E402
from automation.providers import _local_result, _normalize_output  # noqa: E402
from automation.settings import decrypt_secret, encrypt_secret  # noqa: E402


def test_local_provider_returns_structured_analysis_and_reply():
    result = _local_result(
        {
            "contact": {"name": "Ada", "email": "ada@example.com"},
            "message": {"content": "Please send enterprise pricing and a demo."},
        }
    )

    assert result.provider == "local"
    assert result.output["intent"] in {"pricing", "demo"}
    assert 0 <= result.output["score"] <= 100
    assert 0 <= result.output["confidence"] <= 1
    assert result.output["reply"]


def test_provider_normalization_rejects_invalid_values():
    context = {
        "contact": {"name": "Ada"},
        "message": {"content": "Need help"},
    }
    output = _normalize_output(
        {
            "intent": "invented",
            "score": 900,
            "confidence": -2,
            "priority": "impossible",
            "reply": "Valid reply",
        },
        context,
        "auto",
    )

    assert output["intent"] == "general"
    assert output["score"] == 100
    assert output["confidence"] == 0
    assert output["priority"] in {"normal", "high", "urgent"}


def test_webhook_signature_is_stable_and_secret_sensitive():
    signature = sign_payload("secret", "2026-06-12T00:00:00Z", b'{"ok":true}')
    assert len(signature) == 64
    assert signature == sign_payload("secret", "2026-06-12T00:00:00Z", b'{"ok":true}')
    assert signature != sign_payload("different", "2026-06-12T00:00:00Z", b'{"ok":true}')


def test_webhook_secret_round_trip_is_encrypted(monkeypatch):
    monkeypatch.setenv("AUTOMATION_SECRET_KEY", "test-secret-key")
    encrypted = encrypt_secret("callback-secret")

    assert encrypted
    assert encrypted != "callback-secret"
    assert decrypt_secret(encrypted) == "callback-secret"


def test_real_output_schema_and_workers_are_registered():
    schema = (ROOT / "database" / "migrations" / "init.sql").read_text(encoding="utf-8")
    runtime_schema = (ROOT / "backend" / "db.py").read_text(encoding="utf-8")
    main = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")

    for table in ("automation_settings", "automation_ai_calls", "outbound_deliveries"):
        fragment = f"CREATE TABLE IF NOT EXISTS {table}"
        assert fragment in schema
        assert fragment in runtime_schema
    assert "outbound_delivery_worker.start" in main
    assert "outbound_delivery_worker.stop" in main


def test_real_output_api_and_frontend_controls_exist():
    api = (ROOT / "backend" / "api" / "automations.py").read_text(encoding="utf-8")
    workbench = (
        ROOT / "frontend" / "src" / "features" / "automations" / "AutomationWorkbench.jsx"
    ).read_text(encoding="utf-8")

    for route in (
        '"/settings"',
        '"/ai-calls/recent"',
        '"/deliveries/recent"',
        '"/messages/{message_id}/approve"',
        '"/deliveries/{delivery_id}/retry"',
    ):
        assert route in api
    assert "/api/automations/settings" in workbench
    assert "/api/automations/messages/" in workbench
    assert "outbound_webhook_enabled" in workbench


def test_provider_module_uses_openrouter_with_local_fallback():
    provider = (ROOT / "backend" / "automation" / "providers.py").read_text(encoding="utf-8")
    engine = (ROOT / "backend" / "automation" / "engine.py").read_text(encoding="utf-8")
    assert "AsyncOpenAI" in provider
    assert "OPENROUTER_API_KEY" in provider
    assert "provider_mode == \"local\"" in provider
    assert "All automation models failed" in provider
    assert "'failed', $6" in engine


@pytest.mark.parametrize("mode", ["draft", "review", "automatic"])
def test_supported_reply_modes_are_exposed(mode):
    api = (ROOT / "backend" / "api" / "automations.py").read_text(encoding="utf-8")
    assert mode in api
