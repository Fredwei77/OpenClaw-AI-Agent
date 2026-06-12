"""Regression coverage for AI qualification, human handoff, and run operations."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from automation.engine import SUPPORTED_STEP_TYPES, flow_matches_event  # noqa: E402
from automation.intelligence import analyze_message, generate_smart_reply  # noqa: E402


def test_intelligence_scores_high_intent_pricing_request():
    result = analyze_message(
        "We need enterprise pricing and a demo today for our team.",
        {"name": "Ada", "email": "ada@example.com"},
    )

    assert result["intent"] in {"pricing", "demo"}
    assert result["score"] >= 50
    assert result["temperature"] in {"warm", "hot"}
    assert result["priority"] in {"high", "urgent"}
    assert result["generation_mode"] == "local_intelligence"


def test_intelligence_detects_human_request_and_unsubscribe():
    handoff = analyze_message("I need to speak to a human sales representative today.")
    unsubscribe = analyze_message("Please unsubscribe and do not contact me.")

    assert handoff["recommended_handoff"] is True
    assert handoff["priority"] == "urgent"
    assert unsubscribe["intent"] == "unsubscribe"
    assert unsubscribe["score"] == 0
    assert unsubscribe["temperature"] == "cold"


def test_smart_reply_uses_intent_and_message_language():
    english = generate_smart_reply(
        {
            "contact": {"name": "Ada"},
            "message": {"content": "Please send pricing."},
            "intelligence": {"intent": "pricing"},
        }
    )
    chinese = generate_smart_reply(
        {
            "contact": {"name": "李明"},
            "message": {"content": "我想申请产品演示"},
            "intelligence": {"intent": "demo"},
        }
    )

    assert "pricing" in english.lower()
    assert "演示" in chinese


def test_phase_three_step_types_are_registered():
    assert {"analyze_intent", "smart_reply", "handoff"} <= SUPPORTED_STEP_TYPES


def test_definition_validation_rejects_invalid_runtime_configuration():
    from automation.engine import validate_definition

    with pytest.raises(ValueError, match="requires a field"):
        validate_definition({"steps": [{"type": "condition", "config": {}}]})
    with pytest.raises(ValueError, match="between 1 and 2592000"):
        validate_definition({"steps": [{"type": "delay", "config": {"seconds": 0}}]})
    with pytest.raises(ValueError, match="1-10000"):
        validate_definition({"steps": [{"type": "send_message", "config": {"content": " "}}]})


def test_human_mode_guard_is_present_in_event_processing():
    engine = (ROOT / "backend" / "automation" / "engine.py").read_text(encoding="utf-8")
    assert 'conversation_mode == "human"' in engine
    assert "FOR UPDATE" in engine
    assert "human_guard" in engine


def test_phase_four_and_five_schema_is_additive():
    schema = (ROOT / "database" / "migrations" / "init.sql").read_text(encoding="utf-8")
    runtime_schema = (ROOT / "backend" / "db.py").read_text(encoding="utf-8")

    for fragment in (
        "CREATE TABLE IF NOT EXISTS conversation_events",
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS mode",
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS priority",
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS unread_count",
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS intent",
        "ALTER TABLE automation_runs ADD COLUMN IF NOT EXISTS parent_run_id",
        "ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS conversation_id",
        "ALTER TABLE automation_jobs ADD COLUMN IF NOT EXISTS locked_at",
    ):
        assert fragment in schema
        assert fragment in runtime_schema


def test_operations_routes_and_ui_are_exposed():
    conversations = (ROOT / "backend" / "api" / "conversations.py").read_text(encoding="utf-8")
    automations = (ROOT / "backend" / "api" / "automations.py").read_text(encoding="utf-8")
    workbench = (
        ROOT / "frontend" / "src" / "features" / "automations" / "AutomationWorkbench.jsx"
    ).read_text(encoding="utf-8")

    for route in (
        '/{conversation_id}/takeover',
        '/{conversation_id}/release',
        '/{conversation_id}/messages',
        '/{conversation_id}/events',
    ):
        assert route in conversations
    for route in (
        '/templates/ai-qualification',
        '/analytics',
        '/runs/{run_id}',
        '/runs/{run_id}/retry',
    ):
        assert route in automations
    assert "/api/automations/analytics?days=30" in workbench
    assert "/takeover" in workbench
    assert "/retry" in workbench


def test_review_hardening_preserves_audit_and_idempotency_links():
    automations = (ROOT / "backend" / "api" / "automations.py").read_text(encoding="utf-8")
    webhooks = (ROOT / "backend" / "api" / "webhooks.py").read_text(encoding="utf-8")
    engine = (ROOT / "backend" / "automation" / "engine.py").read_text(encoding="utf-8")

    assert "SET status = 'archived'" in automations
    assert "DELETE FROM automation_flows" not in automations
    assert "SET lead_id = $1, conversation_id = $2" in webhooks
    assert "COALESCE(e.conversation_id, c.id)" in webhooks
    assert "locked_at IS NULL" in engine
    assert "status = 'suppressed'" in engine
    assert "context = $3::jsonb" in engine
    assert "idx_automation_messages_run_step" in (
        ROOT / "database" / "migrations" / "init.sql"
    ).read_text(encoding="utf-8")
    assert "Flow %s failed while processing event %s" in engine


def test_trigger_matching_remains_channel_scoped():
    flow = {
        "trigger_type": "inbound_message",
        "trigger_config": {"channel": "webhook"},
    }
    assert flow_matches_event(
        flow,
        {
            "event_type": "inbound_message",
            "channel": "webhook",
            "message": {"content": "pricing"},
        },
    )
    assert not flow_matches_event(
        flow,
        {
            "event_type": "inbound_message",
            "channel": "instagram",
            "message": {"content": "pricing"},
        },
    )
