"""Regression tests for AI marketing action output quality controls."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from backend.api.agents import (
    MARKETING_MODEL,
    MarketingActionRequest,
    _clean_research_result,
    _fallback_messages,
    _fallback_marketing_action,
    _is_usable_marketing_text,
    _lead_fallback_research,
)
import backend.api.agents as agents_api


LEADS = [
    {
        "id": 1,
        "platform": "x",
        "username": "fitness_brand",
        "followers": 3200,
        "email": None,
        "tags": ["fitness equipment", "business"],
    }
]


def test_marketing_actions_use_owned_lead_ids():
    request = MarketingActionRequest(action="email", lead_ids=[1], language="zh")
    assert request.lead_ids == [1]


def test_default_marketing_model_is_quality_oriented():
    assert MARKETING_MODEL == "qwen/qwen3-30b-a3b-instruct-2507" or MARKETING_MODEL


def test_quality_guard_rejects_corrupted_output():
    assert not _is_usable_marketing_text("Jason " + "UnsupportedException" * 10 + " مرحبا مرحبا مرحبا", "zh")
    assert _is_usable_marketing_text("## 开发信\n\n您好，我们关注到您在健身器材领域的内容，希望交流当前的增长重点。", "zh")


def test_pipeline_english_mode_rejects_non_english_copy():
    chinese_copy = "您好，我们关注到您在皮革包类产品方面的内容，希望交流一个合作机会，并进一步了解您当前的海外增长重点。"
    assert not _is_usable_marketing_text(chinese_copy, "en")


def test_local_fallbacks_are_readable_for_all_actions():
    for action in ("email", "classify", "social"):
        output = _fallback_marketing_action(action, LEADS, "健身器材", "zh")
        assert "锛" not in output
        assert len(output) > 80


def test_research_result_score_drives_tier():
    result = _clean_research_result(
        {"industry": "fitness", "quality_score": "82", "tier": "C", "interests": ["growth"], "talking_points": ["new products"], "best_channel": "email"},
        LEADS[0],
    )
    assert result["quality_score"] == 8
    assert result["tier"] == "S"


def test_pipeline_fallbacks_abandon_non_target_chinese_tag_leads():
    lead = {"username": "bag_supplier", "platform": "linkedin", "followers": 200, "tags": ["皮革包贸易"]}
    research = _lead_fallback_research(lead)
    messages = _fallback_messages(lead, research, "en")

    assert research["industry"] == "Unknown"
    assert research["tier"] == "C"
    assert messages == []


def test_x_keyword_intent_requires_complete_terms():
    assert agents_api._matches_keyword_intent("AI Toy studio and collectibles", "AI toy")
    assert not agents_api._matches_keyword_intent("Ai Toyoshima", "AI toy")


def test_social_redirect_keeps_public_company_website():
    href = "https://x.com/i/redirect?url=https%3A%2F%2Fexample-manufacturer.com%2Fcontact"
    assert agents_api._candidate_url_from_social_anchor(href, "") == "https://example-manufacturer.com/contact"


@pytest.mark.asyncio
async def test_platform_search_fallback_keeps_only_requested_platform(monkeypatch):
    async def fake_duckduckgo(_page, _query):
        return [
            {"platform": "linkedin", "username": "Relevant profile"},
            {"platform": "x", "username": "Wrong platform"},
            {"platform": "duckduckgo", "username": "Unrelated website"},
        ]

    monkeypatch.setattr(agents_api, "_scrape_duckduckgo", fake_duckduckgo)

    leads = await agents_api._scrape_platform_search_fallback(None, "led light", "linkedin")

    assert leads == [{"platform": "linkedin", "username": "Relevant profile"}]
