"""Automated acquisition task policy and lifecycle coverage."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from acquisition import runner as runner_module  # noqa: E402
from api import chat as chat_api  # noqa: E402
from api.acquisition_tasks import AcquisitionTaskCreate  # noqa: E402


class Acquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return None


def task(**overrides):
    value = {
        "id": 1,
        "user_id": 7,
        "approval_mode": "review",
        "delivery_mode": "dry_run",
    }
    value.update(overrides)
    return value


@pytest.mark.asyncio
async def test_review_policy_completes_without_delivery(monkeypatch):
    worker = runner_module.AcquisitionTaskWorker()
    worker._step = AsyncMock()
    result = await worker._apply_delivery_policy(
        task(), 10, {"outreach": {"summary": {"campaign_id": 40}}}, SimpleNamespace(id=7)
    )
    assert result == {"status": "awaiting_review", "campaign_id": 40}


@pytest.mark.asyncio
async def test_live_policy_with_no_email_drafts_sends_nothing(monkeypatch):
    conn = AsyncMock()
    conn.fetch.return_value = []
    monkeypatch.setattr(runner_module, "get_db_pool", AsyncMock(return_value=SimpleNamespace(acquire=lambda: Acquire(conn))))
    worker = runner_module.AcquisitionTaskWorker()
    worker._step = AsyncMock()
    result = await worker._apply_delivery_policy(
        task(approval_mode="automatic", delivery_mode="live"),
        10,
        {"outreach": {"summary": {"campaign_id": 40}}},
        SimpleNamespace(id=7),
    )
    assert result["sent_ids"] == []
    assert result["failures"] == []
    assert "NULLIF(BTRIM(l.email), '') IS NOT NULL" in conn.fetch.await_args.args[0]


@pytest.mark.asyncio
async def test_approval_block_is_audited_as_failure(monkeypatch):
    conn = AsyncMock()
    conn.fetch.return_value = [{"id": 767}]
    monkeypatch.setattr(runner_module, "get_db_pool", AsyncMock(return_value=SimpleNamespace(acquire=lambda: Acquire(conn))))
    monkeypatch.setattr(chat_api, "approve_message", AsyncMock(side_effect=RuntimeError("quality review blocked")))
    worker = runner_module.AcquisitionTaskWorker()
    worker._step = AsyncMock()
    result = await worker._apply_delivery_policy(
        task(approval_mode="automatic", delivery_mode="live"), 10,
        {"outreach": {"summary": {"campaign_id": 40}}}, SimpleNamespace(id=7),
    )
    assert result["failures"][0]["message_id"] == 767
    assert "quality review blocked" in result["failures"][0]["error"]


@pytest.mark.asyncio
async def test_send_failure_is_recorded_and_can_be_retried(monkeypatch):
    conn = AsyncMock()
    conn.fetch.return_value = [{"id": 768}]
    monkeypatch.setattr(runner_module, "get_db_pool", AsyncMock(return_value=SimpleNamespace(acquire=lambda: Acquire(conn))))
    monkeypatch.setattr(chat_api, "approve_message", AsyncMock(return_value=SimpleNamespace(status="approved")))
    monkeypatch.setattr(chat_api, "send_message", AsyncMock(side_effect=RuntimeError("SMTP unavailable")))
    worker = runner_module.AcquisitionTaskWorker()
    worker._step = AsyncMock()
    result = await worker._apply_delivery_policy(
        task(approval_mode="automatic", delivery_mode="live"), 10,
        {"outreach": {"summary": {"campaign_id": 40}}}, SimpleNamespace(id=7),
    )
    assert result["failures"] == [{"message_id": 768, "error": "SMTP unavailable"}]
    api = (ROOT / "backend" / "api" / "acquisition_tasks.py").read_text(encoding="utf-8")
    assert '@router.post("/{task_id}/retry"' in api


def test_automatic_live_requires_explicit_policy_and_reply_stops_followups():
    request = AcquisitionTaskCreate(
        name="LED automation",
        keyword="led strip light",
        platforms=[{"platform": "linkedin", "priority": 3}],
        approval_mode="automatic",
        delivery_mode="live",
    )
    assert request.approval_mode == "automatic" and request.delivery_mode == "live"
    follow_up = (ROOT / "agents" / "chat_agent" / "follow_up.py").read_text(encoding="utf-8")
    webhooks = (ROOT / "backend" / "api" / "webhooks.py").read_text(encoding="utf-8")
    assert "stop_reason = 'reply_received'" in follow_up
    assert "await stop_sequences_for_reply" in webhooks


def test_schema_runtime_routes_and_ui_are_registered():
    schema = (ROOT / "database" / "migrations" / "init.sql").read_text(encoding="utf-8")
    runtime = (ROOT / "backend" / "db.py").read_text(encoding="utf-8")
    main = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    ui = (ROOT / "frontend" / "src" / "features" / "automations" / "AutomationWorkbench.jsx").read_text(encoding="utf-8")
    for table in ("acquisition_tasks", "acquisition_task_runs", "acquisition_task_run_steps"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in schema
        assert f"CREATE TABLE IF NOT EXISTS {table}" in runtime
    assert 'prefix="/api/acquisition-tasks"' in main
    assert "acquisition_task_worker.start" in main
    assert "/api/acquisition-tasks/" in ui
    assert "Automated acquisition tasks" in ui
    assert "Recent run audit" in ui
    assert "/runs`" in ui
