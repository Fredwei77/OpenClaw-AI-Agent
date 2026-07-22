"""P1 regression coverage for queued LinkedIn and X delivery."""

from pathlib import Path

import pytest

from agents.chat_agent.channel_adapters.social import SocialChannelAdapter, resolve_x_handle
from agents.harness_agent.domain_skills.x_skill import XDomainSkill
from backend.api.chat import ChatSendRequest


@pytest.mark.asyncio
async def test_social_adapter_dry_run_has_no_browser_dependency():
    result = await SocialChannelAdapter().send(
        {"platform": "x", "username": "@prospect"},
        {"channel": "twitter_dm", "body": "Hello"},
        "chat-message-12",
        dry_run=True,
    )
    assert result["dry_run"] is True
    assert result["provider"] == "x_dry_run"
    assert result["target"] == "prospect"


def test_x_handle_prefers_profile_url_over_display_name():
    lead = {
        "username": "Leather Bag Spa© (@leatherbagspa)",
        "profile_url": "https://x.com/leatherbagspa",
    }
    assert resolve_x_handle(lead) == "leatherbagspa"


def test_x_handle_falls_back_to_parenthesized_mention():
    assert resolve_x_handle({"username": "Leather Bag Spa (@leatherbagspa)"}) == "leatherbagspa"


class FakeHarnessManager:
    def __init__(self):
        self.navigated = []
        self.clicked = []

    async def navigate(self, url):
        self.navigated.append(url)

    async def wait_for_load(self):
        return True

    async def get_page_info(self):
        return {"url": self.navigated[-1]}

    async def click_element(self, selector, timeout=5):
        self.clicked.append(selector)
        return selector in {
            '[data-testid="sendDMFromProfile"]',
            '[data-testid="dmComposerSendButton"]',
        }

    async def wait_for_element(self, selector, timeout=10, visible=False):
        return True

    async def fill_input(self, selector, message):
        return True

    async def execute_js(self, expression):
        return True


@pytest.mark.asyncio
async def test_x_send_uses_profile_dm_button_and_verifies_submission(monkeypatch):
    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr("agents.harness_agent.domain_skills.x_skill.asyncio.sleep", no_sleep)
    harness = FakeHarnessManager()
    sent = await XDomainSkill(harness).send_message("leatherbagspa", "Hello")

    assert sent is True
    assert harness.navigated == ["https://x.com/leatherbagspa"]
    assert '[data-testid="sendDMFromProfile"]' in harness.clicked
    assert '[data-testid="dmComposerSendButton"]' in harness.clicked


@pytest.mark.asyncio
async def test_linkedin_dry_run_uses_profile_url():
    result = await SocialChannelAdapter().send(
        {"platform": "linkedin", "profile_url": "https://www.linkedin.com/in/demo"},
        {"channel": "linkedin_dm", "body": "Hello"},
        "chat-message-13",
        dry_run=True,
    )
    assert result["target"] == "https://www.linkedin.com/in/demo"


def test_social_send_contract_and_queue_registration():
    request = ChatSendRequest(provider="social", dry_run=True)
    queue = Path("backend/scheduler/task_queue.py").read_text(encoding="utf-8")
    chat_api = Path("backend/api/chat.py").read_text(encoding="utf-8")
    assert request.provider == "social"
    assert request.dry_run is True
    assert '"ChatDeliveryAgent"' in queue
    assert "failed without automatic replay" in queue
    assert "TaskPriority.HIGH" in chat_api
    db = Path("backend/db.py").read_text(encoding="utf-8")
    assert "serialized_result = json.dumps(result" in db
    assert "$2::varchar" in db


def test_social_delivery_schema_and_frontend_controls():
    schema = Path("database/migrations/init.sql").read_text(encoding="utf-8")
    frontend = Path("frontend/src/App.jsx").read_text(encoding="utf-8")
    assert "marketing_messages ADD COLUMN IF NOT EXISTS delivery_task_id" in schema
    assert "idx_marketing_messages_delivery_task" in schema
    assert "dry_run: true" in frontend
    assert "Dry Run" in frontend
    assert "/api/tasks/${taskId}" in frontend
    assert "Delivery is still running after 60 seconds" in frontend
