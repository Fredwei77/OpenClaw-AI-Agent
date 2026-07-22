from __future__ import annotations

import json
from typing import Any

from agents.base_agent import BaseAgent
from .follow_up import complete_sequence_if_finished
from .channel_adapters.social import SocialChannelAdapter


class ChatDeliveryAgent(BaseAgent):
    """Deliver one approved social draft and persist its final state."""

    def __init__(self, browser_manager=None, db=None, harness_manager=None):
        super().__init__("ChatDeliveryAgent", browser_manager, db, harness_manager)

    async def run(self, task: dict) -> dict:
        message_id = int(task["message_id"])
        user_id = int(task["user_id"])
        dry_run = bool(task.get("dry_run", False))
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT m.id, m.channel, m.body, m.status, m.idempotency_key,
                          m.follow_up_sequence_id,
                          l.id AS lead_id, l.platform, l.username, l.profile_url, l.email
                   FROM marketing_messages m
                   JOIN leads l ON l.id = m.lead_id AND l.user_id = m.user_id
                   WHERE m.id = $1 AND m.user_id = $2""",
                message_id,
                user_id,
            )
        if not row:
            return {"status": "failed", "message": "Chat message or lead no longer exists"}
        if row["status"] == "sent":
            return {"status": "success", "message_id": message_id, "idempotent": True}
        if row["status"] not in {"queued", "failed", "sending"}:
            return {"status": "failed", "message": f"Message is not deliverable from status {row['status']}"}

        message = dict(row)
        lead = {
            "id": row["lead_id"],
            "platform": row["platform"],
            "username": row["username"],
            "profile_url": row["profile_url"],
            "email": row["email"],
        }
        async with self.db.acquire() as conn:
            await conn.execute(
                """UPDATE marketing_messages
                   SET status = 'sending',
                       attempts = attempts + CASE WHEN $1 THEN 0 ELSE 1 END,
                       last_error = NULL, updated_at = CURRENT_TIMESTAMP
                   WHERE id = $2 AND user_id = $3""",
                dry_run,
                message_id,
                user_id,
            )
            await self._record_event(
                conn,
                message_id,
                user_id,
                "social_dry_run_started" if dry_run else "social_sending",
                {"channel": row["channel"]},
            )

        try:
            result = await SocialChannelAdapter(self.harness_manager).send(
                lead,
                message,
                row["idempotency_key"] or f"chat-message-{message_id}",
                dry_run=dry_run,
            )
        except Exception as exc:
            async with self.db.acquire() as conn:
                await conn.execute(
                    """UPDATE marketing_messages
                       SET status = 'failed', provider = 'social_harness',
                           last_error = $1, updated_at = CURRENT_TIMESTAMP
                       WHERE id = $2 AND user_id = $3""",
                    str(exc)[:2000],
                    message_id,
                    user_id,
                )
                await self._record_event(
                    conn,
                    message_id,
                    user_id,
                    "failed",
                    {"provider": "social_harness", "error": str(exc)[:2000]},
                )
            return {"status": "failed", "message": str(exc), "message_id": message_id}

        async with self.db.acquire() as conn:
            if dry_run:
                await conn.execute(
                    """UPDATE marketing_messages
                       SET status = 'approved', provider = $1, last_error = NULL,
                           updated_at = CURRENT_TIMESTAMP
                       WHERE id = $2 AND user_id = $3""",
                    result["provider"],
                    message_id,
                    user_id,
                )
                event_type = "social_dry_run_completed"
            else:
                await conn.execute(
                    """UPDATE marketing_messages
                       SET status = 'sent', provider = $1, provider_message_id = $2,
                           sent_at = CURRENT_TIMESTAMP, last_error = NULL,
                           updated_at = CURRENT_TIMESTAMP
                       WHERE id = $3 AND user_id = $4""",
                    result["provider"],
                    result["provider_message_id"],
                    message_id,
                    user_id,
                )
                event_type = "sent"
            await self._record_event(conn, message_id, user_id, event_type, result)
            if not dry_run:
                await complete_sequence_if_finished(
                    conn,
                    row["follow_up_sequence_id"],
                    user_id,
                )
        return {"status": "success", "message_id": message_id, **result}

    @staticmethod
    async def _record_event(
        conn,
        message_id: int,
        user_id: int,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        await conn.execute(
            """INSERT INTO marketing_message_events
               (message_id, user_id, event_type, payload)
               VALUES ($1, $2, $3, $4::jsonb)""",
            message_id,
            user_id,
            event_type,
            json.dumps(payload, ensure_ascii=False, default=str),
        )
