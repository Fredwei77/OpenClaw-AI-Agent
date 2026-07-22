from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx

from automation.delivery import sign_payload


class WebhookChannelAdapter:
    name = "webhook"

    def __init__(self, callback_url: str, secret: str):
        self.callback_url = callback_url
        self.secret = secret

    async def send(self, lead: dict, message: dict, idempotency_key: str) -> dict:
        payload = {
            "event": "chat.message.approved",
            "idempotency_key": idempotency_key,
            "lead": {
                "id": lead.get("id"),
                "platform": lead.get("platform"),
                "username": lead.get("username"),
                "profile_url": lead.get("profile_url"),
                "email": lead.get("email"),
            },
            "message": {
                "id": message.get("id"),
                "channel": message.get("channel"),
                "subject": message.get("subject"),
                "body": message.get("body"),
                "cta": message.get("cta"),
            },
        }
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        timestamp = datetime.now(timezone.utc).isoformat()
        signature = sign_payload(self.secret, timestamp, body)
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
            response = await client.post(
                self.callback_url,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-OpenClaw-Timestamp": timestamp,
                    "X-OpenClaw-Signature": f"sha256={signature}",
                    "Idempotency-Key": idempotency_key,
                },
            )
            response.raise_for_status()
        return {
            "provider": "webhook",
            "provider_message_id": response.headers.get("X-Message-Id", idempotency_key),
        }
