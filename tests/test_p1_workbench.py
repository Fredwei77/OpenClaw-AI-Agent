"""Regression tests for the usable local Lead workbench P1 flow."""

from pathlib import Path

from backend.api.agents import MarketingPipelineRequest, _fallback_messages, _lead_fallback_research
from backend.api.outreach import MarketingMessageUpdate


def test_pipeline_request_uses_owned_lead_ids():
    request = MarketingPipelineRequest(lead_ids=[1, 2], product_context="fitness")
    assert request.lead_ids == [1, 2]


def test_local_fallback_creates_editable_outreach_drafts():
    lead = {"username": "demo", "platform": "x", "followers": 1200, "tags": ["fitness"]}
    research = _lead_fallback_research(lead)
    messages = _fallback_messages(lead, research, "en")
    assert research["quality_score"] > 0
    assert {message["channel"] for message in messages} == {"email", "linkedin_dm", "twitter_dm"}


def test_outreach_statuses_are_explicit():
    assert MarketingMessageUpdate(status="approved").status == "approved"


def test_schema_indexes_outreach_status():
    schema = Path("database/migrations/init.sql").read_text(encoding="utf-8")
    assert "idx_marketing_messages_user_status" in schema
