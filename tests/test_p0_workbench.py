"""Regression tests for the single-machine lead workbench P0 fixes."""

import asyncio
from pathlib import Path

import pytest

from backend.scheduler.task_queue import QueuedTask, TaskPriority, TaskQueue


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_priority_queue_runs_urgent_tasks_first():
    queue = TaskQueue()
    queue._init_queue()
    queue._running = True

    await queue.submit_task(1, 1, "LeadAgent", "scrape", {}, TaskPriority.LOW)
    await queue.submit_task(2, 1, "LeadAgent", "scrape", {}, TaskPriority.URGENT)

    _, first = await queue._queue.get()
    _, second = await queue._queue.get()

    assert first.task_id == 2
    assert second.task_id == 1


@pytest.mark.asyncio
async def test_rate_limited_task_releases_concurrency_slot():
    class RejectLimiter:
        async def acquire(self):
            return False

        async def wait_time(self):
            return 1.0

    queue = TaskQueue(max_concurrent=1)
    queue._init_queue()
    queue._running = True
    queue._concurrency_semaphore = asyncio.Semaphore(1)
    queue._rate_limiters["x"] = RejectLimiter()

    task = QueuedTask(
        task_id=1,
        user_id=1,
        agent_name="LeadAgent",
        task_type="scrape",
        payload={},
        platform="x",
    )
    await queue._queue.put(((0, 0), task))

    worker = asyncio.create_task(queue._worker_loop())
    await asyncio.sleep(0.01)
    assert queue._concurrency_semaphore._value == 1
    queue._running = False
    worker.cancel()
    await worker

def test_schema_contains_required_lead_workbench_objects():
    schema = (ROOT / "database" / "migrations" / "init.sql").read_text(encoding="utf-8")

    assert "metadata JSONB" in schema
    assert "quality_score INT" in schema
    assert "CREATE TABLE IF NOT EXISTS marketing_messages" in schema
    assert "CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_user_platform_username" in schema


def test_desktop_package_does_not_bundle_env_file():
    package_json = (ROOT / "desktop" / "electron_app" / "package.json").read_text(encoding="utf-8")

    assert '"from": "../../.env"' not in package_json
