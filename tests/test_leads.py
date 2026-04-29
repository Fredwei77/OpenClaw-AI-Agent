"""
Unit tests for backend/api/leads.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from fastapi import HTTPException

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.api.leads import (
    LeadCreate,
    LeadUpdate,
    VALID_PLATFORMS,
    VALID_LEAD_STATUSES,
)


class TestLeadModels:
    """Test Lead Pydantic models."""

    def test_lead_create_valid(self):
        """Should accept valid lead data."""
        lead = LeadCreate(
            platform="x",
            username="testuser",
            profile_url="https://x.com/testuser",
            followers=1000,
            tags=["fitness", "ecommerce"]
        )
        assert lead.platform == "x"
        assert lead.username == "testuser"
        assert lead.followers == 1000
        assert lead.tags == ["fitness", "ecommerce"]

    def test_lead_create_minimal(self):
        """Should accept lead with only required fields."""
        lead = LeadCreate(platform="x", username="testuser")
        assert lead.platform == "x"
        assert lead.username == "testuser"
        assert lead.profile_url is None
        assert lead.email is None
        assert lead.followers == 0
        assert lead.tags == []

    def test_lead_create_invalid_platform(self):
        """Should accept any platform string (validation at DB level)."""
        # Note: VALID_PLATFORMS is for reference, not strict validation
        lead = LeadCreate(platform="unknown_platform", username="testuser")
        assert lead.platform == "unknown_platform"

    def test_lead_update_partial(self):
        """Should accept partial update."""
        update = LeadUpdate(username="newusername")
        assert update.username == "newusername"
        assert update.platform is None
        assert update.followers is None

    def test_lead_update_with_status(self):
        """Should accept status update."""
        update = LeadUpdate(status="qualified")
        assert update.status == "qualified"


class TestLeadValidation:
    """Test lead validation logic."""

    def test_valid_platforms_constant(self):
        """Should have expected platforms defined."""
        assert "x" in VALID_PLATFORMS
        assert "instagram" in VALID_PLATFORMS
        assert "tiktok" in VALID_PLATFORMS
        assert "linkedin" in VALID_PLATFORMS

    def test_valid_statuses_constant(self):
        """Should have expected statuses defined."""
        assert "new" in VALID_LEAD_STATUSES
        assert "contacted" in VALID_LEAD_STATUSES
        assert "qualified" in VALID_LEAD_STATUSES
        assert "converted" in VALID_LEAD_STATUSES

    def test_lead_create_followers_non_negative(self):
        """Followers must be non-negative."""
        with pytest.raises(ValueError):
            LeadCreate(platform="x", username="test", followers=-1)


class TestLeadListResponseModel:
    """Test LeadListResponse model."""
    from backend.api.leads import LeadListResponse

    def test_lead_list_response_structure(self):
        """Should have correct structure."""
        from backend.api.leads import LeadListResponse
        response = LeadListResponse(
            leads=[],
            total=0,
            page=1,
            page_size=20
        )
        assert response.leads == []
        assert response.total == 0
        assert response.page == 1
        assert response.page_size == 20