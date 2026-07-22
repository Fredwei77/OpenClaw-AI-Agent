"""P2 regression coverage for scheduled follow-up sequences."""

from pathlib import Path

import pytest

from agents.chat_agent.follow_up import FollowUpWorker, build_follow_up_copy
from backend.api.chat import FollowUpSequenceRequest


def test_follow_up_request_defaults_and_copy():
    request = FollowUpSequenceRequest()
    assert request.delays_hours == [72, 168, 336]
    assert request.stop_on_reply is True
    first = build_follow_up_copy(
        {"channel": "email", "subject": "Initial note", "cta": "Compare priorities"},
        1,
    )
    second = build_follow_up_copy(
        {"channel": "linkedin_dm", "subject": "", "cta": "Compare priorities"},
        2,
    )
    third = build_follow_up_copy(
        {"channel": "email", "subject": "Initial note", "cta": "Compare priorities"},
        3,
    )
    assert first["subject"].startswith("Following up:")
    assert "Day 3 follow-up" in first["body"]
    assert second["subject"] == ""
    assert "Day 7 case" in second["body"]
    assert "Day 14 project progress" in third["body"]


@pytest.mark.asyncio
async def test_follow_up_worker_lifecycle_without_processing():
    worker = FollowUpWorker(interval_seconds=60)
    await worker.start()
    assert worker._running is True
    await worker.stop()
    assert worker._running is False


def test_follow_up_schema_worker_and_reply_stop_are_registered():
    schema = Path("database/migrations/init.sql").read_text(encoding="utf-8")
    runtime_schema = Path("backend/db.py").read_text(encoding="utf-8")
    main = Path("backend/main.py").read_text(encoding="utf-8")
    webhook = Path("backend/api/webhooks.py").read_text(encoding="utf-8")
    chat = Path("backend/api/chat.py").read_text(encoding="utf-8")
    frontend = Path("frontend/src/App.jsx").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS follow_up_sequences" in schema
    assert "follow_up_sequence_id" in schema
    assert "idx_marketing_messages_follow_up_due" in schema
    assert "CREATE TABLE IF NOT EXISTS follow_up_sequences" in runtime_schema
    assert "follow_up_worker.start()" in main
    assert "follow_up_worker.stop()" in main
    assert "stop_sequences_for_reply" in webhook
    assert '"/messages/{message_id}/follow-ups"' in chat
    assert '"/follow-ups/{sequence_id}/stop"' in chat
    assert "SET follow_up_sequence_id = $1" in chat
    assert "Start Follow-ups" in frontend
