"""Regression coverage for outbound review to inbound automation bridge."""

from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from backend.api.outreach import _to_review_item
from backend.api.webhooks import WebhookSimulationRequest


def test_review_queue_normalizes_joined_outreach_rows():
    item = _to_review_item({
        "id": 8,
        "campaign_id": 40,
        "campaign_name": "LED strip light Outreach",
        "lead_id": 318,
        "lead_name": "Demo Lighting",
        "lead_email": "sales@example.com",
        "channel": "email",
        "subject": "Project lead time",
        "body": "Should I check lead time for your current project?",
        "status": "draft",
        "quality_score": 82,
        "risk_flags": "[]",
        "scheduled_at": None,
        "sent_at": None,
        "follow_up_sequence_id": None,
        "last_error": None,
        "created_at": datetime(2026, 7, 13),
    })

    assert item.campaign_id == 40
    assert item.lead_id == 318
    assert item.status == "draft"
    assert item.risk_flags == []


def test_inbound_reply_can_target_the_original_outbound_lead():
    request = WebhookSimulationRequest(
        lead_id=318,
        channel="email",
        contact={"external_id": "reply-318", "name": "Demo", "email": "sales@example.com"},
        message={"content": "Please send lead time."},
    )
    assert request.lead_id == 318


def test_bridge_routes_and_frontend_workflow_are_exposed():
    outreach = (ROOT / "backend" / "api" / "outreach.py").read_text(encoding="utf-8")
    webhooks = (ROOT / "backend" / "api" / "webhooks.py").read_text(encoding="utf-8")
    workbench = (
        ROOT / "frontend" / "src" / "features" / "automations" / "AutomationWorkbench.jsx"
    ).read_text(encoding="utf-8")

    assert '@router.get("/review-queue"' in outreach
    assert "m.channel <> 'email' OR NULLIF(BTRIM(l.email), '') IS NOT NULL" in outreach
    assert "request.lead_id is not None" in webhooks
    assert "/api/outreach/review-queue?limit=100" in workbench
    assert "Approve & send" in workbench
    assert "apiErrorMessage" in workbench
    assert "发送失败：${error.message}" in workbench
    assert "item.channel === 'email' && !item.lead_email" in workbench
    assert "delays_hours: [72, 168, 336]" in workbench
    assert "Start Day 3/7/14 follow-ups" in workbench
