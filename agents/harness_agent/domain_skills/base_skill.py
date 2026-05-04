"""
Base class for domain skills.
Each skill provides platform-specific scraping and interaction capabilities.
"""
from abc import ABC, abstractmethod
from typing import Any


class BaseDomainSkill(ABC):
    """Base class for browser-harness domain skills."""

    platform: str = ""

    def __init__(self, harness_manager):
        self.hm = harness_manager

    @abstractmethod
    async def search_users(self, keyword: str, limit: int = 20) -> list[dict]:
        """Search for users/leads by keyword. Returns list of lead dicts."""
        ...

    @abstractmethod
    async def extract_profile(self, username: str) -> dict:
        """Extract full profile data for a user."""
        ...

    async def follow_user(self, username: str) -> bool:
        """Follow a user. Returns True on success."""
        raise NotImplementedError(f"{self.platform} does not support follow")

    async def send_message(self, target: str, message: str) -> bool:
        """Send a message to a user. Returns True on success."""
        raise NotImplementedError(f"{self.platform} does not support messaging")

    def _make_lead(self, username: str, profile_url: str, **kwargs) -> dict:
        """Create a lead dict matching the OpenClaw schema."""
        return {
            "platform": self.platform,
            "username": username,
            "profile_url": profile_url,
            "email": kwargs.get("email"),
            "followers": kwargs.get("followers", 0),
            "tags": kwargs.get("tags", []),
        }
