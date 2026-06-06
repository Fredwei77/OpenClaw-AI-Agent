"""Regression tests for persisted recent marketing campaigns."""

from pathlib import Path

from backend.api.outreach import _campaign_stage


ROOT = Path(__file__).resolve().parents[1]


def test_campaign_stage_tracks_draft_lifecycle():
    assert _campaign_stage(0, 0, 0, 0, 0) == ("queued", 0)
    assert _campaign_stage(3, 3, 0, 0, 0) == ("queued", 0)
    assert _campaign_stage(3, 2, 1, 0, 0) == ("running", 33)
    assert _campaign_stage(3, 0, 1, 1, 1) == ("done", 100)


def test_campaign_schema_and_pipeline_link_are_present():
    schema = (ROOT / "database" / "migrations" / "init.sql").read_text(encoding="utf-8")
    db = (ROOT / "backend" / "db.py").read_text(encoding="utf-8")
    agents = (ROOT / "backend" / "api" / "agents.py").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS marketing_campaigns" in schema
    assert "ALTER TABLE marketing_messages ADD COLUMN IF NOT EXISTS campaign_id INT" in schema
    assert "idx_marketing_campaigns_user_created_at" in schema
    assert "create_marketing_campaign" in db
    assert '"campaign_id": campaign_id' in agents


def test_frontend_recent_campaigns_use_api_not_demo_rows():
    app = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
    assert "/api/outreach/campaigns?limit=10" in app
    assert "Fitness Equipment Outreach" not in app
    assert "Shopify Store Owner Invites" not in app
    assert "SaaS Tool Subscription Drive" not in app
