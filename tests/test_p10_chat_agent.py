"""Regression coverage for the guarded outbound Chat Agent P0."""

from pathlib import Path

import pytest

from agents.chat_agent import ChatAgent
from agents.chat_agent.chat_agent import _contains_cjk
from agents.chat_agent.validators import validate_message
from backend.api.chat import ChatGenerateRequest, ChatMessageUpdate, ChatSendRequest


def test_chat_agent_selects_only_reachable_channels():
    assert ChatAgent.available_channels({"platform": "linkedin", "email": "lead@example.com"}) == [
        "email",
        "linkedin_dm",
    ]
    assert ChatAgent.available_channels({"platform": "x", "email": None}) == ["twitter_dm"]
    assert ChatAgent.available_channels({"platform": "facebook", "email": None}) == ["facebook_dm"]
    assert ChatAgent.available_channels({"platform": "instagram", "email": None}) == ["instagram_dm"]
    assert ChatAgent.available_channels({"platform": "tiktok", "email": None}) == ["tiktok_dm"]
    assert ChatAgent.available_channels({
        "platform": "duckduckgo",
        "profile_url": "https://www.linkedin.com/company/example",
        "email": None,
    }) == ["linkedin_dm"]


def test_quality_guard_rejects_unsupported_claims_and_long_dm():
    score, flags = validate_message(
        {
            "channel": "twitter_dm",
            "subject": "",
            "body": "Guaranteed 100% success. " + ("x" * 280),
        },
        [],
    )
    assert score < 60
    assert "channel_length_exceeded" in flags
    assert "unsupported_guarantee" in flags


def test_english_language_guard_and_richer_evidence():
    assert _contains_cjk("你好") is True
    assert _contains_cjk("Hello there") is False
    evidence = ChatAgent._evidence(
        {"platform": "x", "username": "maker", "tags": ["leather bags"]},
        {"bio": "Handmade leather accessories"},
    )
    assert "Handmade leather accessories" in evidence
    assert "leather bags" in evidence


@pytest.mark.asyncio
async def test_local_chat_generation_keeps_personalization_evidence():
    agent = ChatAgent()
    agent.api_key = ""
    result = await agent.run(
        {
            "lead": {
                "id": 1,
                "platform": "linkedin",
                "username": "Alex",
                "email": "alex@example.com",
            },
            "research": {
                "industry": "lighting contractor",
                "talking_points": ["your facade lighting project"],
            },
            "product_context": "用户填写",
            "language": "en",
            "channels": ["email", "linkedin_dm"],
        }
    )
    assert result["provider"] == "local"
    assert {item["channel"] for item in result["messages"]} == {"email", "linkedin_dm"}
    assert all(item["personalization_evidence"] for item in result["messages"])
    assert all(item["quality_score"] >= 60 for item in result["messages"])


def test_chat_api_contract_defaults_to_reviewable_actions():
    request = ChatGenerateRequest(lead_ids=[1])
    assert request.language == "en"
    assert ChatSendRequest().provider == "auto"
    assert ChatSendRequest().dry_run is False
    assert ChatMessageUpdate(body="Updated draft").body == "Updated draft"
    assert ChatGenerateRequest(lead_ids=[1], channels=["instagram_dm"]).channels == ["instagram_dm"]


def test_search_fallback_recovers_social_platform_from_profile_url():
    from backend.api.agents import (
        _clean_search_result_url,
        _extract_public_emails,
        _is_search_verification_page,
        _lead_email_discovery_query,
        _social_platform_from_url,
    )

    assert _social_platform_from_url("https://www.linkedin.com/company/example") == "linkedin"
    assert _social_platform_from_url("https://m.facebook.com/example") == "facebook"
    assert _social_platform_from_url("https://www.instagram.com/example/") == "instagram"
    assert _social_platform_from_url("https://www.tiktok.com/@example") == "tiktok"
    assert _social_platform_from_url("https://example.com/profile") == "duckduckgo"

    assert _extract_public_emails("Contact sales@example.com, info@test.com, buyer@lightingco.com") == [
        "buyer@lightingco.com"
    ]
    assert _extract_public_emails("DuckDuckGo error page error-lite@duckduckgo.com") == []
    assert _extract_public_emails('mailto:sales@contractor.co.uk')[0] == "sales@contractor.co.uk"
    assert _extract_public_emails("sales [at] distributor [dot] de")[0] == "sales@distributor.de"
    assert _is_search_verification_page("Please verify you are human. error-lite@duckduckgo.com")

    redirect = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fcontractor.example%2Fcontact"
    assert _clean_search_result_url(redirect) == "https://contractor.example/contact"

    query = _lead_email_discovery_query(
        {"username": "Example Lighting Director (@example)", "metadata": {"title": "Project lighting contractor"}},
        "facade lighting",
    )
    assert "Example Lighting Director" in query
    assert "Project lighting contractor" in query
    assert "facade lighting" in query
    assert "contact email" in query


def test_chat_schema_contains_auditable_outbox_fields():
    schema = Path("database/migrations/init.sql").read_text(encoding="utf-8")
    for field in (
        "personalization_evidence",
        "quality_score",
        "risk_flags",
        "approved_by",
        "idempotency_key",
        "attempts",
        "last_error",
    ):
        assert f"marketing_messages ADD COLUMN IF NOT EXISTS {field}" in schema
    assert "CREATE TABLE IF NOT EXISTS marketing_message_events" in schema
    assert "idx_marketing_messages_idempotency" in schema


def test_chat_router_and_frontend_actions_are_registered():
    main = Path("backend/main.py").read_text(encoding="utf-8")
    frontend = Path("frontend/src/App.jsx").read_text(encoding="utf-8")
    outreach = Path("backend/api/outreach.py").read_text(encoding="utf-8")
    assert 'prefix="/api/chat"' in main
    assert "/api/chat/messages/" in frontend
    assert "/api/chat/generate" in frontend
    assert "activeTab === 'chat'" in frontend
    assert "Select a lead to test Chat Agent" in frontend
    assert "Generate English Drafts" in frontend
    assert "Auto-approve and send" in frontend
    assert "chatMinQuality" in frontend
    assert "Use the Chat Agent approval and send endpoints" in outreach
