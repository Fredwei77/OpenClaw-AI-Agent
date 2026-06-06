"""Regression tests for scraped follower count normalization."""

from backend.api.agents import _parse_social_count
from backend.db import MAX_REASONABLE_FOLLOWERS, normalize_followers


def test_parse_social_count_requires_follower_context_or_compact_suffix():
    assert _parse_social_count("12.5K followers") == 12_500
    assert _parse_social_count("3.2M") == 3_200_000
    assert _parse_social_count("Model M 73999835") == 0


def test_normalize_followers_prevents_batch_failure_for_oversized_values():
    assert normalize_followers(73_999_835_000_000) == MAX_REASONABLE_FOLLOWERS
    assert normalize_followers("12.5K") == 12_500
    assert normalize_followers("not-a-number") == 0
