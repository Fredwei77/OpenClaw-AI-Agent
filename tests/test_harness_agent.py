"""Tests for the HarnessAgent and browser-harness integration."""
import pytest
import sys
import os
import importlib
import types

# Ensure project root is in path (same as conftest.py)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force re-import of browser_cluster as a proper package (not namespace package)
# This is needed because other test modules may have imported it as a namespace package
if "browser_cluster" in sys.modules:
    del sys.modules["browser_cluster"]
    for key in list(sys.modules.keys()):
        if key.startswith("browser_cluster."):
            del sys.modules[key]


class TestHarnessAgentModels:
    """Test HarnessAgent configuration and models."""

    def test_skill_map_contains_platforms(self):
        from agents.harness_agent.harness_agent import SKILL_MAP
        assert "x" in SKILL_MAP
        assert "twitter" in SKILL_MAP
        assert "tiktok" in SKILL_MAP
        assert "linkedin" in SKILL_MAP

    def test_x_skill_class(self):
        from agents.harness_agent.domain_skills.x_skill import XDomainSkill
        assert XDomainSkill.platform == "x"
        assert hasattr(XDomainSkill, "search_users")
        assert hasattr(XDomainSkill, "extract_profile")
        assert hasattr(XDomainSkill, "follow_user")
        assert hasattr(XDomainSkill, "send_message")

    def test_tiktok_skill_class(self):
        from agents.harness_agent.domain_skills.tiktok_skill import TikTokDomainSkill
        assert TikTokDomainSkill.platform == "tiktok"
        assert hasattr(TikTokDomainSkill, "search_users")
        assert hasattr(TikTokDomainSkill, "extract_profile")
        assert hasattr(TikTokDomainSkill, "follow_user")

    def test_linkedin_skill_class(self):
        from agents.harness_agent.domain_skills.linkedin_skill import LinkedInDomainSkill
        assert LinkedInDomainSkill.platform == "linkedin"
        assert hasattr(LinkedInDomainSkill, "search_users")
        assert hasattr(LinkedInDomainSkill, "extract_profile")
        assert hasattr(LinkedInDomainSkill, "send_connect")
        assert hasattr(LinkedInDomainSkill, "send_message")

    def test_base_skill_interface(self):
        from agents.harness_agent.domain_skills.base_skill import BaseDomainSkill
        assert hasattr(BaseDomainSkill, "search_users")
        assert hasattr(BaseDomainSkill, "extract_profile")
        assert hasattr(BaseDomainSkill, "follow_user")
        assert hasattr(BaseDomainSkill, "send_message")
        assert hasattr(BaseDomainSkill, "_make_lead")

    def test_make_lead_format(self):
        from agents.harness_agent.domain_skills.base_skill import BaseDomainSkill

        class DummySkill(BaseDomainSkill):
            platform = "test"
            async def search_users(self, keyword, limit=20): return []
            async def extract_profile(self, username): return {}

        skill = DummySkill(harness_manager=None)
        lead = skill._make_lead("user1", "https://example.com/user1", followers=100, tags=["test"])

        assert lead["platform"] == "test"
        assert lead["username"] == "user1"
        assert lead["profile_url"] == "https://example.com/user1"
        assert lead["followers"] == 100
        assert lead["tags"] == ["test"]
        assert lead["email"] is None


class TestHarnessAgentExecution:
    """Test HarnessAgent run method."""

    @pytest.mark.asyncio
    async def test_run_without_harness_returns_error(self):
        from agents.harness_agent.harness_agent import HarnessAgent
        agent = HarnessAgent(harness_manager=None)
        result = await agent.run({"action": "scrape", "platform": "x", "keyword": "test"})
        assert result["status"] == "error"
        assert "not connected" in result["message"]

    @pytest.mark.asyncio
    async def test_run_reconnects_harness_before_failing(self):
        from agents.harness_agent.harness_agent import HarnessAgent

        class RecoveringHM:
            is_connected = False

            async def start(self):
                self.is_connected = True
                return True

        manager = RecoveringHM()
        result = await HarnessAgent(harness_manager=manager).run(
            {"action": "unknown", "platform": "x"}
        )

        assert manager.is_connected is True
        assert result["message"] == "Unknown action: unknown"

    @pytest.mark.asyncio
    async def test_run_unsupported_platform(self):
        from agents.harness_agent.harness_agent import HarnessAgent

        class FakeHM:
            is_connected = True

        agent = HarnessAgent(harness_manager=FakeHM())
        result = await agent.run({"action": "scrape", "platform": "unknown", "keyword": "test"})
        assert result["status"] == "error"
        assert "Unsupported platform" in result["message"]

    @pytest.mark.asyncio
    async def test_run_unknown_action(self):
        from agents.harness_agent.harness_agent import HarnessAgent

        class FakeHM:
            is_connected = True

        agent = HarnessAgent(harness_manager=FakeHM())
        result = await agent.run({"action": "unknown", "platform": "x"})
        assert result["status"] == "error"
        assert "Unknown action" in result["message"]

    @pytest.mark.asyncio
    async def test_dry_run_follow(self):
        from agents.harness_agent.harness_agent import HarnessAgent

        class FakeHM:
            is_connected = True

        agent = HarnessAgent(harness_manager=FakeHM(), dry_run=True)
        result = await agent.run({"action": "follow", "platform": "x", "username": "testuser"})
        assert result["status"] == "success"
        assert "DRY RUN" in result["message"]


class TestHarnessLauncher:
    """Test harness launcher utilities."""

    def test_is_debug_port_open_returns_false_when_no_chrome(self):
        from browser_cluster.harness_launcher import is_debug_port_open
        # Port 19999 is unlikely to have Chrome running
        assert is_debug_port_open(19999) is False

    def test_find_chrome_returns_string_or_none(self):
        from browser_cluster.harness_launcher import _find_chrome_executable
        result = _find_chrome_executable()
        # On CI this may be None, on dev machine it should find Chrome
        assert result is None or isinstance(result, str)


class TestHarnessSocialHandler:
    """Test HarnessSocialHandler rate limiting."""

    def test_rate_limit_tracking(self):
        from browser_cluster.handler.harness_social_handler import HarnessSocialHandler

        class FakeHM:
            is_connected = True

        handler = HarnessSocialHandler(harness_manager=FakeHM(), platform="x")
        # Rate limit config should exist
        from browser_cluster.handler.social_handler import RateLimitConfig
        max_req, window = RateLimitConfig.get_limit("x", "follow")
        assert max_req > 0
        assert window > 0


class TestBrowserHarnessManager:
    """Test BrowserHarnessManager initialization."""

    @pytest.fixture
    def fake_browser_harness(self, monkeypatch):
        from browser_cluster.manager import browser_harness_manager

        helpers = types.SimpleNamespace(NAME="default")
        ipc = types.SimpleNamespace(ping=lambda _name: False)
        package = types.ModuleType("browser_harness")
        admin = types.ModuleType("browser_harness.admin")
        admin.ensure_daemon = lambda **_kwargs: None
        package.admin = admin

        monkeypatch.setitem(sys.modules, "browser_harness", package)
        monkeypatch.setitem(sys.modules, "browser_harness.admin", admin)
        monkeypatch.setattr(browser_harness_manager, "BH_AVAILABLE", True)
        monkeypatch.setattr(browser_harness_manager, "bh", helpers, raising=False)
        monkeypatch.setattr(browser_harness_manager, "ipc", ipc, raising=False)
        return browser_harness_manager, admin

    def test_manager_init(self, fake_browser_harness):
        browser_harness_manager, _admin = fake_browser_harness
        BrowserHarnessManager = browser_harness_manager.BrowserHarnessManager
        manager = BrowserHarnessManager(name="test")
        assert manager.name == "test"
        assert not manager.is_connected
        assert browser_harness_manager.bh.NAME == "test"

    @pytest.mark.asyncio
    async def test_manager_start_without_daemon(
        self, monkeypatch, fake_browser_harness
    ):
        browser_harness_manager, admin = fake_browser_harness

        monkeypatch.setattr(browser_harness_manager.ipc, "ping", lambda _name: False)
        monkeypatch.setattr(
            admin,
            "ensure_daemon",
            lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("daemon unavailable")),
        )

        BrowserHarnessManager = browser_harness_manager.BrowserHarnessManager
        manager = BrowserHarnessManager(name="test_nonexistent")
        result = await manager.start()
        assert result is False
        assert manager.is_connected is False

    @pytest.mark.asyncio
    async def test_manager_start_without_package(self, monkeypatch):
        from browser_cluster.manager import browser_harness_manager

        monkeypatch.setattr(browser_harness_manager, "BH_AVAILABLE", False)
        manager = browser_harness_manager.BrowserHarnessManager(name="test_missing")

        assert await manager.start() is False
        assert manager.is_connected is False
