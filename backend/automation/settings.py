"""Automation settings, policy evaluation, and local secret protection."""

from __future__ import annotations

import base64
import hashlib
import os
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

from db import get_db_pool


DEFAULT_SETTINGS = {
    "ai_provider": "hybrid",
    "ai_model": "",
    "reply_mode": "review",
    "min_confidence": 0.65,
    "handoff_score": 85,
    "max_auto_replies_per_hour": 5,
    "blocked_terms": [],
    "outbound_webhook_enabled": False,
    "outbound_webhook_url": "",
}


def _fernet() -> Fernet:
    seed = os.getenv("AUTOMATION_SECRET_KEY") or os.getenv("JWT_SECRET_KEY")
    if not seed:
        seed = "openclaw-local-dev-key"
    key = base64.urlsafe_b64encode(hashlib.sha256(seed.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> Optional[str]:
    if not value:
        return None
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


async def get_automation_settings(user_id: int) -> Dict[str, Any]:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT ai_provider, ai_model, reply_mode, min_confidence,
                      handoff_score, max_auto_replies_per_hour, blocked_terms,
                      outbound_webhook_enabled, outbound_webhook_url,
                      outbound_webhook_secret
               FROM automation_settings
               WHERE user_id = $1""",
            user_id,
        )
    if not row:
        return {**DEFAULT_SETTINGS, "webhook_secret_configured": False}
    data = dict(row)
    data["blocked_terms"] = list(data.get("blocked_terms") or [])
    data["min_confidence"] = float(data["min_confidence"])
    data["webhook_secret_configured"] = bool(data.pop("outbound_webhook_secret", None))
    return data


async def get_delivery_secret(user_id: int) -> str:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        encrypted = await conn.fetchval(
            "SELECT outbound_webhook_secret FROM automation_settings WHERE user_id = $1",
            user_id,
        )
    return decrypt_secret(encrypted)


async def evaluate_reply_policy(
    user_id: int,
    conversation_id: int,
    content: str,
    intelligence: Dict[str, Any],
) -> Dict[str, Any]:
    settings = await get_automation_settings(user_id)
    blocked_terms = [
        term for term in settings["blocked_terms"]
        if term.casefold() in content.casefold()
    ]
    confidence = float(intelligence.get("confidence", 0))
    score = int(intelligence.get("score", 0))
    reason = ""
    action = settings["reply_mode"]

    if blocked_terms:
        action = "review"
        reason = f"Blocked terms detected: {', '.join(blocked_terms)}"
    elif confidence < settings["min_confidence"]:
        action = "review"
        reason = "AI confidence is below the automatic reply threshold."
    elif intelligence.get("recommended_handoff") or score >= settings["handoff_score"]:
        action = "review"
        reason = intelligence.get("handoff_reason") or "Lead reached the handoff threshold."

    if action == "automatic":
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            recent = await conn.fetchval(
                """SELECT COUNT(*)
                   FROM conversation_messages
                   WHERE conversation_id = $1 AND user_id = $2
                     AND direction = 'outbound'
                     AND metadata->>'source' = 'automation'
                     AND created_at >= CURRENT_TIMESTAMP - INTERVAL '1 hour'""",
                conversation_id,
                user_id,
            )
        if recent >= settings["max_auto_replies_per_hour"]:
            action = "review"
            reason = "Automatic reply rate limit reached."

    return {
        "action": action,
        "reason": reason,
        "blocked_terms": blocked_terms,
        "settings": settings,
    }
