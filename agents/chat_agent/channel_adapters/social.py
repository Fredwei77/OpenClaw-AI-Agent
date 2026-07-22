from __future__ import annotations

import re
from urllib.parse import urlparse

from agents.harness_agent.harness_agent import HarnessAgent


_X_HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")
_X_RESERVED_PATHS = {"home", "explore", "messages", "notifications", "search", "settings"}


def resolve_x_handle(lead: dict) -> str:
    profile_url = str(lead.get("profile_url") or "").strip()
    if profile_url:
        parsed = urlparse(profile_url if "://" in profile_url else f"https://{profile_url}")
        host = parsed.netloc.lower().split(":", 1)[0]
        parts = [part for part in parsed.path.split("/") if part]
        if host.removeprefix("www.") in {"x.com", "twitter.com"} and parts:
            candidate = parts[0].lstrip("@")
            if candidate.lower() not in _X_RESERVED_PATHS and _X_HANDLE_RE.fullmatch(candidate):
                return candidate

    username = str(lead.get("username") or "").strip()
    mentions = re.findall(r"@([A-Za-z0-9_]{1,15})\b", username)
    candidate = mentions[-1] if mentions else username.lstrip("@")
    if _X_HANDLE_RE.fullmatch(candidate):
        return candidate
    raise ValueError("Lead does not have a valid X handle or profile URL")


class SocialChannelAdapter:
    name = "social"

    def __init__(self, harness_manager=None):
        self.harness_manager = harness_manager

    async def send(self, lead: dict, message: dict, idempotency_key: str, dry_run: bool = False) -> dict:
        channel = str(message.get("channel") or "")
        platform = {
            "linkedin_dm": "linkedin",
            "twitter_dm": "x",
        }.get(channel)
        if not platform:
            raise ValueError(f"Unsupported social channel: {channel}")

        target = str(lead.get("profile_url") or "").strip() if platform == "linkedin" else resolve_x_handle(lead)
        if not target:
            raise ValueError(f"Lead does not have a valid {platform} target")
        if dry_run:
            return {
                "provider": f"{platform}_dry_run",
                "provider_message_id": idempotency_key,
                "dry_run": True,
                "target": target,
            }

        agent = HarnessAgent(harness_manager=self.harness_manager)
        result = await agent.run(
            {
                "action": "message",
                "platform": platform,
                "username": target,
                "message": message.get("body") or "",
            }
        )
        if result.get("status") != "success":
            raise RuntimeError(result.get("message") or f"{platform} message delivery failed")
        return {
            "provider": f"{platform}_harness",
            "provider_message_id": idempotency_key,
            "dry_run": False,
            "target": target,
        }
