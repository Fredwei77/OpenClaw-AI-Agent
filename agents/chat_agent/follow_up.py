from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Optional

from agents.chat_agent.channel_adapters import EmailChannelAdapter
from db import get_db_pool
from scheduler.task_queue import TaskPriority, get_task_queue

logger = logging.getLogger(__name__)


def build_follow_up_copy(
    source: dict[str, Any],
    step: int,
    language: str = "en",
) -> dict[str, str]:
    subject = str(source.get("subject") or "").strip()
    cta = str(source.get("cta") or "").strip()
    if language == "zh":
        bodies = (
            "您好，想简单跟进一下之前的信息。如果这个方向与您目前的工作相关，我可以补充一份更具体的说明。",
            "最后跟进一次。如果现在不是合适的时间，我就不再打扰；如果您愿意了解，我们可以从一个具体问题开始交流。",
        )
        follow_subject = f"跟进：{subject}" if subject else "简单跟进"
    else:
        bodies = (
            "Hi, I wanted to briefly follow up on my earlier note. If this is relevant to your current priorities, I can share a more specific overview.",
            "One last follow-up from me. If the timing is not right, I will close the loop; if it is relevant, we can start with one specific question.",
        )
        follow_subject = f"Following up: {subject}" if subject else "Quick follow-up"
    body = bodies[min(max(step - 1, 0), len(bodies) - 1)]
    return {
        "subject": follow_subject if source.get("channel") == "email" else "",
        "body": body,
        "cta": cta,
    }

def build_follow_up_copy(
    source: dict[str, Any],
    step: int,
    language: str = "en",
) -> dict[str, str]:
    subject = str(source.get("subject") or "").strip()
    cta = str(source.get("cta") or "Check lead time or stock").strip()
    if language == "zh":
        bodies = (
            "第 3 天跟进：是否需要我先确认这个项目的交期或现货？",
            "第 7 天案例：可按类似项目的产品规格、数量、交期和现货风险做对照；如你有当前项目参数，我可以直接匹配。",
            "第 14 天项目进度：这个项目是否还在推进？需要我先查交期还是现货？",
        )
        follow_subject = f"跟进：{subject}" if subject else "项目交期或现货"
    else:
        bodies = (
            "Day 3 follow-up: should I check lead time or available stock for this project first?",
            "Day 7 case: for a similar project, the useful comparison is product spec, quantity, lead time, and stock risk. If you share the current parameters, I can match them directly.",
            "Day 14 project progress check: is this project still moving forward, and should I check lead time or available stock?",
        )
        follow_subject = f"Following up: {subject}" if subject else "Project lead time or stock"
    body = bodies[min(max(step - 1, 0), len(bodies) - 1)]
    return {
        "subject": follow_subject if source.get("channel") == "email" else "",
        "body": body,
        "cta": cta,
    }


async def stop_sequences_for_reply(
    conn,
    user_id: int,
    lead_id: int,
    conversation_id: Optional[int] = None,
) -> list[int]:
    rows = await conn.fetch(
        """UPDATE follow_up_sequences
           SET status = 'stopped', stopped_at = CURRENT_TIMESTAMP,
               stop_reason = 'reply_received', updated_at = CURRENT_TIMESTAMP
           WHERE user_id = $1 AND lead_id = $2 AND status = 'active'
             AND stop_on_reply = TRUE
           RETURNING id""",
        user_id,
        lead_id,
    )
    sequence_ids = [row["id"] for row in rows]
    if not sequence_ids:
        return []
    cancelled = await conn.fetch(
        """UPDATE marketing_messages
           SET status = 'cancelled', last_error = 'Follow-up stopped after reply',
               updated_at = CURRENT_TIMESTAMP
           WHERE user_id = $1
             AND follow_up_sequence_id = ANY($2::int[])
             AND status IN ('scheduled', 'scheduling', 'queued', 'approved')
           RETURNING id, delivery_task_id""",
        user_id,
        sequence_ids,
    )
    task_ids = [row["delivery_task_id"] for row in cancelled if row["delivery_task_id"]]
    if task_ids:
        await conn.execute(
            """UPDATE tasks
               SET status = 'cancelled', completed_at = CURRENT_TIMESTAMP,
                   error = 'Follow-up stopped after reply'
               WHERE user_id = $1 AND id = ANY($2::int[])
                 AND status IN ('pending', 'running')""",
            user_id,
            task_ids,
        )
    payload = json.dumps(
        {"reason": "reply_received", "conversation_id": conversation_id},
        ensure_ascii=False,
    )
    for row in cancelled:
        await conn.execute(
            """INSERT INTO marketing_message_events
               (message_id, user_id, event_type, payload)
               VALUES ($1, $2, 'follow_up_cancelled', $3::jsonb)""",
            row["id"],
            user_id,
            payload,
        )
    return sequence_ids


async def complete_sequence_if_finished(conn, sequence_id: Optional[int], user_id: int) -> None:
    if not sequence_id:
        return
    remaining = await conn.fetchval(
        """SELECT COUNT(*)
           FROM marketing_messages
           WHERE follow_up_sequence_id = $1 AND user_id = $2
             AND status IN ('scheduled', 'scheduling', 'queued', 'sending', 'approved', 'failed')""",
        sequence_id,
        user_id,
    )
    if remaining == 0:
        await conn.execute(
            """UPDATE follow_up_sequences
               SET status = 'completed', updated_at = CURRENT_TIMESTAMP
               WHERE id = $1 AND user_id = $2 AND status = 'active'""",
            sequence_id,
            user_id,
        )


class FollowUpWorker:
    def __init__(self, interval_seconds: float = 2.0) -> None:
        self.interval_seconds = interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        while self._running:
            try:
                await self.process_due()
            except Exception:
                logger.exception("Follow-up worker failed")
            await asyncio.sleep(self.interval_seconds)

    async def process_due(self) -> int:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await self._downgrade_stale_sequences(conn)
            rows = await conn.fetch(
                """UPDATE marketing_messages m
                   SET status = 'scheduling', updated_at = CURRENT_TIMESTAMP
                   FROM follow_up_sequences s
                   WHERE m.id IN (
                       SELECT candidate.id
                       FROM marketing_messages candidate
                       JOIN follow_up_sequences sequence
                         ON sequence.id = candidate.follow_up_sequence_id
                        AND sequence.user_id = candidate.user_id
                       WHERE candidate.status = 'scheduled'
                         AND candidate.scheduled_at <= CURRENT_TIMESTAMP
                         AND sequence.status = 'active'
                       ORDER BY candidate.scheduled_at, candidate.id
                       FOR UPDATE OF candidate SKIP LOCKED
                       LIMIT 20
                   )
                     AND s.id = m.follow_up_sequence_id
                   RETURNING m.id, m.user_id, m.lead_id, m.channel, m.subject,
                             m.body, m.cta, m.idempotency_key,
                             m.follow_up_sequence_id"""
            )
        processed = 0
        for row in rows:
            try:
                await self._deliver(dict(row))
                processed += 1
            except Exception as exc:
                logger.warning("Follow-up message %s failed: %s", row["id"], exc)
                async with pool.acquire() as conn:
                    await conn.execute(
                        """UPDATE marketing_messages
                           SET status = 'failed', last_error = $1,
                               updated_at = CURRENT_TIMESTAMP
                           WHERE id = $2 AND user_id = $3 AND status = 'scheduling'""",
                        str(exc)[:2000],
                        row["id"],
                        row["user_id"],
                    )
                    await self._record_event(
                        conn,
                        row["id"],
                        row["user_id"],
                        "follow_up_failed",
                        {"error": str(exc)[:2000]},
                    )
        return processed

    @staticmethod
    async def _downgrade_stale_sequences(conn) -> None:
        rows = await conn.fetch(
            """UPDATE follow_up_sequences
               SET status = 'completed',
                   stop_reason = 'no_reply_30_days',
                   stopped_at = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP
               WHERE status = 'active'
                 AND started_at <= CURRENT_TIMESTAMP - INTERVAL '30 days'
                 AND NOT EXISTS (
                     SELECT 1
                     FROM conversation_messages cm
                     JOIN conversations c
                       ON c.id = cm.conversation_id AND c.user_id = cm.user_id
                     WHERE cm.user_id = follow_up_sequences.user_id
                       AND c.lead_id = follow_up_sequences.lead_id
                       AND cm.direction = 'inbound'
                       AND cm.created_at >= follow_up_sequences.started_at
                 )
               RETURNING id, user_id, lead_id"""
        )
        for row in rows:
            await conn.execute(
                """UPDATE leads
                   SET quality_score = 0,
                       metadata = jsonb_set(
                           jsonb_set(COALESCE(metadata, '{}'::jsonb), '{tier}', '"C"', true),
                           '{downgrade_reason}', '"no_reply_30_days"', true
                       )
                   WHERE id = $1 AND user_id = $2""",
                row["lead_id"],
                row["user_id"],
            )
            await conn.execute(
                """UPDATE marketing_messages
                   SET status = 'cancelled',
                       last_error = 'Lead downgraded to C after 30 days without reply',
                       updated_at = CURRENT_TIMESTAMP
                   WHERE follow_up_sequence_id = $1 AND user_id = $2
                     AND status IN ('scheduled', 'scheduling', 'queued', 'approved')""",
                row["id"],
                row["user_id"],
            )

    async def _deliver(self, message: dict[str, Any]) -> None:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            replied = await conn.fetchval(
                """SELECT EXISTS (
                       SELECT 1
                       FROM conversation_messages cm
                       JOIN conversations c
                         ON c.id = cm.conversation_id AND c.user_id = cm.user_id
                       JOIN follow_up_sequences s
                         ON s.id = $1 AND s.user_id = cm.user_id
                       WHERE cm.user_id = $2 AND c.lead_id = s.lead_id
                         AND cm.direction = 'inbound'
                         AND cm.created_at >= s.started_at
                   )""",
                message["follow_up_sequence_id"],
                message["user_id"],
            )
            if replied:
                await stop_sequences_for_reply(
                    conn,
                    message["user_id"],
                    message["lead_id"],
                )
                return
            lead = await conn.fetchrow(
                """SELECT id, platform, username, profile_url, email
                   FROM leads WHERE id = $1 AND user_id = $2""",
                message["lead_id"],
                message["user_id"],
            )
        if not lead:
            raise ValueError("Follow-up lead no longer exists")

        if message["channel"] == "email":
            result = await EmailChannelAdapter().send(
                dict(lead),
                message,
                message["idempotency_key"] or f"follow-up-{message['id']}",
            )
            async with pool.acquire() as conn:
                await conn.execute(
                    """UPDATE marketing_messages
                       SET status = 'sent', provider = $1, provider_message_id = $2,
                           attempts = attempts + 1, sent_at = CURRENT_TIMESTAMP,
                           last_error = NULL, updated_at = CURRENT_TIMESTAMP
                       WHERE id = $3 AND user_id = $4 AND status = 'scheduling'""",
                    result["provider"],
                    result["provider_message_id"],
                    message["id"],
                    message["user_id"],
                )
                await self._record_event(
                    conn,
                    message["id"],
                    message["user_id"],
                    "follow_up_sent",
                    result,
                )
                await complete_sequence_if_finished(
                    conn,
                    message["follow_up_sequence_id"],
                    message["user_id"],
                )
            return

        platform = "linkedin" if message["channel"] == "linkedin_dm" else "x"
        async with pool.acquire() as conn:
            async with conn.transaction():
                task_id = await conn.fetchval(
                    """INSERT INTO tasks
                       (agent_name, task_type, payload, status, user_id)
                       VALUES ('ChatDeliveryAgent', 'message', $1::jsonb, 'pending', $2)
                       RETURNING id""",
                    json.dumps(
                        {
                            "message_id": message["id"],
                            "platform": platform,
                            "dry_run": False,
                        }
                    ),
                    message["user_id"],
                )
                await conn.execute(
                    """UPDATE marketing_messages
                       SET status = 'queued', delivery_task_id = $1,
                           idempotency_key = COALESCE(idempotency_key, $2),
                           updated_at = CURRENT_TIMESTAMP
                       WHERE id = $3 AND user_id = $4 AND status = 'scheduling'""",
                    task_id,
                    f"follow-up-{message['id']}",
                    message["id"],
                    message["user_id"],
                )
                await self._record_event(
                    conn,
                    message["id"],
                    message["user_id"],
                    "follow_up_queued",
                    {"task_id": task_id, "platform": platform},
                )
        queued = await get_task_queue().submit_task(
            task_id=task_id,
            user_id=message["user_id"],
            agent_name="ChatDeliveryAgent",
            task_type="message",
            payload={
                "message_id": message["id"],
                "platform": platform,
                "dry_run": False,
            },
            priority=TaskPriority.NORMAL,
            platform=platform,
        )
        if not queued:
            async with pool.acquire() as conn:
                await conn.execute(
                    """UPDATE marketing_messages
                       SET status = 'failed', last_error = 'Task queue rejected follow-up delivery',
                           updated_at = CURRENT_TIMESTAMP
                       WHERE id = $1 AND user_id = $2 AND status = 'queued'""",
                    message["id"],
                    message["user_id"],
                )
            raise RuntimeError("Task queue rejected follow-up delivery")

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


follow_up_worker = FollowUpWorker()
