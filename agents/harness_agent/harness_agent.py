"""
HarnessAgent - Browser-harness powered agent for authenticated scraping and interaction.

Uses CDP to connect to the user's real Chrome browser, inheriting logged-in sessions
for platforms like X, TikTok, LinkedIn.
"""
import logging
from typing import Optional

from agents.base_agent import BaseAgent
from browser_cluster.manager.browser_harness_manager import BrowserHarnessManager
from browser_cluster.handler.harness_social_handler import HarnessSocialHandler

from .domain_skills.x_skill import XDomainSkill
from .domain_skills.tiktok_skill import TikTokDomainSkill
from .domain_skills.linkedin_skill import LinkedInDomainSkill

logger = logging.getLogger(__name__)

SKILL_MAP = {
    "x": XDomainSkill,
    "twitter": XDomainSkill,
    "tiktok": TikTokDomainSkill,
    "linkedin": LinkedInDomainSkill,
}


class HarnessAgent(BaseAgent):
    """
    Agent that uses browser-harness for authenticated browser automation.

    Connects to the user's real Chrome via CDP, enabling:
    - Scraping while logged in (LinkedIn search results, X premium features)
    - Social interactions (follow, DM, connect)
    - Self-healing via domain skills

    Falls back to Playwright if harness is unavailable.
    """

    def __init__(
        self,
        browser_manager=None,
        db=None,
        harness_manager: Optional[BrowserHarnessManager] = None,
        dry_run: bool = False,
    ):
        super().__init__(name="HarnessAgent", browser_manager=browser_manager, db=db, harness_manager=harness_manager)
        self.harness_manager = harness_manager
        self.dry_run = dry_run

    async def run(self, task: dict) -> dict:
        """
        Execute a harness-based task.

        Task dict should contain:
            - action: "scrape" | "follow" | "message" | "connect" | "profile"
            - platform: "x" | "twitter" | "tiktok" | "linkedin"
            - keyword: search keyword (for scrape)
            - username: target username (for follow/message/profile)
            - message: message text (for message/connect)
            - limit: max results (for scrape, default 20)
        """
        action = task.get("action", "scrape")
        platform = task.get("platform", "x").lower()
        keyword = task.get("keyword", "")
        username = task.get("username", "")
        message = task.get("message", "")
        limit = task.get("limit", 20)

        # Check harness availability
        if not self.harness_manager or not self.harness_manager.is_connected:
            return {
                "status": "error",
                "message": "Browser harness not connected. Ensure Chrome is running with --remote-debugging-port."
            }

        # Get the domain skill for this platform
        skill_class = SKILL_MAP.get(platform)
        if not skill_class:
            return {
                "status": "error",
                "message": f"Unsupported platform: {platform}. Supported: {list(SKILL_MAP.keys())}"
            }

        skill = skill_class(self.harness_manager)

        try:
            if action == "scrape":
                return await self._do_scrape(skill, keyword, limit, task)
            elif action == "follow":
                return await self._do_follow(skill, username)
            elif action == "message":
                return await self._do_message(skill, username, message)
            elif action == "connect":
                return await self._do_connect(skill, username, message)
            elif action == "profile":
                return await self._do_profile(skill, username)
            else:
                return {"status": "error", "message": f"Unknown action: {action}"}

        except Exception as e:
            logger.exception(f"HarnessAgent error: {e}")
            return {"status": "error", "message": str(e)}

    async def _do_scrape(self, skill, keyword: str, limit: int, task: dict) -> dict:
        """Scrape leads. Caller is responsible for saving to database."""
        leads = await skill.search_users(keyword, limit=limit)

        return {
            "status": "success",
            "action": "scrape",
            "platform": skill.platform,
            "leads_found": len(leads),
            "data": leads,
        }

    async def _do_follow(self, skill, username: str) -> dict:
        if self.dry_run:
            return {"status": "success", "action": "follow", "message": f"[DRY RUN] Would follow {username}"}

        result = await skill.follow_user(username)
        return {
            "status": "success" if result else "failed",
            "action": "follow",
            "username": username,
            "message": f"Followed {username}" if result else "Follow failed",
        }

    async def _do_message(self, skill, target: str, message: str) -> dict:
        if self.dry_run:
            return {"status": "success", "action": "message", "message": f"[DRY RUN] Would message {target}"}

        result = await skill.send_message(target, message)
        return {
            "status": "success" if result else "failed",
            "action": "message",
            "target": target,
            "message": f"Sent message to {target}" if result else "Message failed",
        }

    async def _do_connect(self, skill, profile_url: str, note: str) -> dict:
        if self.dry_run:
            return {"status": "success", "action": "connect", "message": f"[DRY RUN] Would connect with {profile_url}"}

        if not hasattr(skill, "send_connect"):
            return {"status": "error", "message": f"{skill.platform} does not support connect"}

        result = await skill.send_connect(profile_url, note)
        return {
            "status": "success" if result else "failed",
            "action": "connect",
            "profile_url": profile_url,
        }

    async def _do_profile(self, skill, username: str) -> dict:
        profile = await skill.extract_profile(username)
        return {
            "status": "success",
            "action": "profile",
            "platform": skill.platform,
            "data": profile,
        }
