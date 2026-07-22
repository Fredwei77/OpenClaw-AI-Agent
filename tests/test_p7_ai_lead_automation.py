"""Regression tests for the webhook-driven AI lead automation MVP."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from automation.engine import (  # noqa: E402
    evaluate_condition,
    flow_matches_event,
    render_template,
    validate_definition,
)


def test_template_rendering_supports_dotted_context():
    context = {
        "contact": {"name": "Ada"},
        "message": {"content": "Need pricing"},
    }
    result = render_template(
        "Hi {{ contact.name }}, we received: {{message.content}}",
        context,
    )
    assert result == "Hi Ada, we received: Need pricing"


def test_condition_operators_cover_core_workflow_filters():
    context = {
        "contact": {"status": "new", "tags": ["simulator", "high-intent"]},
        "message": {"content": "I need a product demo"},
        "score": 82,
    }
    assert evaluate_condition({"field": "contact.status", "operator": "equals", "value": "new"}, context)
    assert evaluate_condition({"field": "contact.tags", "operator": "contains", "value": "high-intent"}, context)
    assert evaluate_condition({"field": "message.content", "operator": "contains", "value": "PRODUCT"}, context)
    assert evaluate_condition({"field": "score", "operator": "gte", "value": 75}, context)
    assert not evaluate_condition({"field": "score", "operator": "lt", "value": 50}, context)


def test_trigger_matching_checks_event_channel_and_keywords():
    flow = {
        "trigger_type": "inbound_message",
        "trigger_config": {
            "channel": "webhook",
            "keywords": ["demo", "pricing"],
            "keyword_match": "any",
        },
    }
    event = {
        "event_type": "inbound_message",
        "channel": "webhook",
        "message": {"content": "Can I get a pricing demo?"},
    }
    assert flow_matches_event(flow, event)
    assert not flow_matches_event(flow, {**event, "channel": "email"})
    assert not flow_matches_event(
        flow,
        {**event, "message": {"content": "Just saying hello"}},
    )


def test_definition_validation_rejects_unknown_steps():
    validate_definition(
        {
            "steps": [
                {"type": "send_message", "config": {"content": "Hello"}},
                {"type": "delay", "config": {"seconds": 10}},
                {"type": "add_tag", "config": {"tag": "qualified"}},
            ]
        }
    )
    with pytest.raises(ValueError, match="unsupported step type"):
        validate_definition({"steps": [{"type": "launch_missiles"}]})


def test_schema_and_routes_include_automation_runtime():
    schema = (ROOT / "database" / "migrations" / "init.sql").read_text(encoding="utf-8")
    main = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    for table in (
        "automation_flows",
        "conversations",
        "conversation_messages",
        "webhook_events",
        "automation_runs",
        "automation_run_steps",
        "automation_jobs",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in schema
    assert 'prefix="/api/automations"' in main
    assert 'prefix="/api/conversations"' in main
    assert 'prefix="/api/webhooks"' in main


def test_frontend_exposes_automation_workbench():
    app = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
    workbench = (
        ROOT / "frontend" / "src" / "features" / "automations" / "AutomationWorkbench.jsx"
    ).read_text(encoding="utf-8")
    assert "AutomationWorkbench" in app
    assert "activeTab === 'automations'" in app
    assert "/api/webhooks/simulate" in workbench
    assert "/api/automations/templates/welcome" in workbench
    workbench_index = app.index("<AutomationWorkbench lang={lang} />")
    main_close_index = app.index("</main>")
    drawer_index = app.index('className={`assistant-drawer')
    assert workbench_index < main_close_index < drawer_index
