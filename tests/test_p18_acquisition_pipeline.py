"""End-to-end orchestration coverage for prioritized lead acquisition."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from backend.api import agents as agents_api


def test_platform_priority_is_descending_and_stable():
    platforms = [
        agents_api.AcquisitionPlatform(platform="x", priority=1),
        agents_api.AcquisitionPlatform(platform="linkedin", priority=3),
        agents_api.AcquisitionPlatform(platform="shopify", priority=3),
    ]
    ordered = agents_api._ordered_acquisition_platforms(platforms)
    assert [item.platform for item in ordered] == ["linkedin", "shopify", "x"]


@pytest.mark.asyncio
async def test_acquisition_pipeline_persists_then_drafts_for_email_assets(monkeypatch):
    scrape = AsyncMock(side_effect=[
        {"status": "success", "leads_found": 2, "emails_found": 1, "source": "linkedin"},
        {"status": "success", "leads_found": 3, "emails_found": 1, "source": "x"},
    ])
    outreach = AsyncMock(return_value={"status": "success", "summary": {"campaign_id": 9}})
    connection = AsyncMock()
    connection.fetch.return_value = [{"id": 41}, {"id": 42}]

    class Acquire:
        async def __aenter__(self):
            return connection

        async def __aexit__(self, *_args):
            return None

    pool = SimpleNamespace(acquire=lambda: Acquire())
    monkeypatch.setattr(agents_api, "test_scraper", scrape)
    monkeypatch.setattr(agents_api, "marketing_pipeline", outreach)
    monkeypatch.setattr("db.get_db_pool", AsyncMock(return_value=pool))

    result = await agents_api.acquisition_pipeline(
        agents_api.AcquisitionPipelineRequest(
            keyword="industrial lighting",
            platforms=[
                {"platform": "x", "priority": 1},
                {"platform": "linkedin", "priority": 3},
            ],
            product_context="LED drivers",
        ),
        current_user=SimpleNamespace(id=7),
    )

    assert [call.args[0].platform for call in scrape.await_args_list] == ["linkedin", "x"]
    assert result["assets_persisted"] == 5
    assert result["email_ready_lead_ids"] == [41, 42]
    assert result["next_action"] == "review_drafts"
    assert outreach.await_args.args[0].lead_ids == [41, 42]
    query_args = connection.fetch.await_args.args
    assert "email IS NOT NULL" in query_args[0]
    assert "BTRIM(email) <> ''" in query_args[0]
    assert query_args[1:] == (7, ["linkedin", "x"], "industrial lighting", 20)


@pytest.mark.asyncio
async def test_acquisition_pipeline_reports_partial_failure_without_sending(monkeypatch):
    scrape = AsyncMock(return_value={"status": "error", "message": "login required"})
    outreach = AsyncMock()
    monkeypatch.setattr(agents_api, "test_scraper", scrape)
    monkeypatch.setattr(agents_api, "marketing_pipeline", outreach)

    result = await agents_api.acquisition_pipeline(
        agents_api.AcquisitionPipelineRequest(
            keyword="lighting contractor",
            platforms=[{"platform": "linkedin", "priority": 3}],
        ),
        current_user=SimpleNamespace(id=7),
    )

    assert result["status"] == "partial_success"
    assert result["email_ready_lead_ids"] == []
    assert result["next_action"] == "refine_search_for_public_emails"
    outreach.assert_not_awaited()


def test_frontend_exposes_one_click_acquisition():
    app = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
    assert "/api/agents/acquisition-pipeline" in app
    assert "handleAcquisitionPipeline" in app
    assert "Acquire & Draft" in app
