"""
Unit tests for backend/api/agents.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import os

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'backend'))

# Mock the scheduler module before importing agents
import unittest.mock as mock
sys.modules['scheduler'] = mock.MagicMock()
sys.modules['scheduler.task_queue'] = mock.MagicMock()
sys.modules['browser_cluster'] = mock.MagicMock()
sys.modules['browser_cluster.manager'] = mock.MagicMock()
sys.modules['browser_cluster.manager.browser_pool'] = mock.MagicMock()
sys.modules['db'] = mock.MagicMock()

from backend.api.agents import (
    ChatRequest,
    ScrapeRequest,
    TaskSubmitRequest,
    TaskStatusRequest,
)


class TestAPIModels:
    """Test API Pydantic models."""

    def test_chat_request_valid(self):
        """Should accept valid chat request."""
        req = ChatRequest(prompt="Hello, tell me about fitness equipment")
        assert req.prompt == "Hello, tell me about fitness equipment"

    def test_scrape_request_defaults(self):
        """Should have correct default values."""
        req = ScrapeRequest()
        assert req.keyword == "fitness equipment"
        assert req.platform == "x"
        assert req.geography == "all"
        assert req.follower_range == "all"
        assert req.content_type == "all"
        assert req.max_results == 50
        assert req.use_proxy is False
        assert req.cookies is None

    def test_scrape_request_custom(self):
        """Should accept custom values."""
        req = ScrapeRequest(
            keyword="瑜伽垫",
            platform="instagram",
            geography="us",
            follower_range="10k-50k",
            content_type="influencer",
            max_results=100,
            use_proxy=True
        )
        assert req.keyword == "瑜伽垫"
        assert req.platform == "instagram"
        assert req.geography == "us"
        assert req.follower_range == "10k-50k"
        assert req.content_type == "influencer"
        assert req.max_results == 100
        assert req.use_proxy is True

    def test_scrape_request_with_store_domain(self):
        """Should accept Shopify store domain."""
        req = ScrapeRequest(
            keyword="shopify store",
            platform="shopify",
            store_domain="mystore.myshopify.com"
        )
        assert req.store_domain == "mystore.myshopify.com"

    def test_scrape_request_with_cookies(self):
        """Should accept cookies for authenticated requests."""
        cookies = {"session_id": "abc123", "auth_token": "xyz789"}
        req = ScrapeRequest(cookies=cookies)
        assert req.cookies == cookies

    def test_task_submit_request_valid(self):
        """Should accept valid task submission."""
        req = TaskSubmitRequest(
            agent_name="lead_agent",
            task_type="scrape",
            payload={"keyword": "fitness", "platform": "x"},
            priority=2
        )
        assert req.agent_name == "lead_agent"
        assert req.task_type == "scrape"
        assert req.priority == 2
        assert req.platform is None

    def test_task_submit_request_with_platform(self):
        """Should accept task with platform."""
        req = TaskSubmitRequest(
            agent_name="tiktok_agent",
            task_type="scrape",
            payload={},
            priority=1,
            platform="tiktok"
        )
        assert req.platform == "tiktok"

    def test_task_status_request_valid(self):
        """Should accept valid task status request."""
        req = TaskStatusRequest(task_id=123)
        assert req.task_id == 123


class TestScrapeRequestValidation:
    """Test ScrapeRequest field validation."""

    def test_max_results_bounds(self):
        """Max results should be within reasonable bounds."""
        req = ScrapeRequest(max_results=200)
        assert req.max_results == 200

    def test_geography_values(self):
        """Should accept all valid geography values."""
        valid_geos = ["all", "us", "uk", "ca", "au", "de", "fr", "jp", "sg"]
        for geo in valid_geos:
            req = ScrapeRequest(geography=geo)
            assert req.geography == geo

    def test_follower_range_values(self):
        """Should accept all valid follower range values."""
        valid_ranges = ["all", "0-1k", "1k-10k", "10k-50k", "50k-100k", "100k+"]
        for fr in valid_ranges:
            req = ScrapeRequest(follower_range=fr)
            assert req.follower_range == fr

    def test_content_type_values(self):
        """Should accept all valid content type values."""
        valid_types = ["all", "influencer", "business", "creator", "reseller"]
        for ct in valid_types:
            req = ScrapeRequest(content_type=ct)
            assert req.content_type == ct