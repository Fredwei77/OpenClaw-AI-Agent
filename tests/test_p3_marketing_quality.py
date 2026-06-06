"""Regression tests for AI marketing action output quality controls."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from backend.api.agents import (
    MARKETING_MODEL,
    MarketingActionRequest,
    _clean_research_result,
    _fallback_marketing_action,
    _is_usable_marketing_text,
)


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
    assert result["quality_score"] == 82
    assert result["tier"] == "A"
