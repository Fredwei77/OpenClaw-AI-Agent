"""Reliable signed outbound webhook delivery."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from automation.settings import get_delivery_secret
from db import get_db_pool

logger = logging.getLogger(__name__)


def sign_payload(secret: str, timestamp: str, body: bytes) -> str:
    message = timestamp.encode("utf-8") + b"." + body
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


async def enqueue_delivery(
    user_id: int,
    message_id: int,
    callback_url: str,
    payload: dict,
) -> int:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """INSERT INTO outbound_deliveries
               (user_id, message_id, callback_url, payload)
               VALUES ($1, $2, $3, $4::jsonb)
               ON CONFLICT (message_id)
               DO UPDATE SET callback_url = EXCLUDED.callback_url,
                             payload = EXCLUDED.payload,
                             status = 'pending',
                             attempts = 0,
                             next_attempt_at = CURRENT_TIMESTAMP,
                             locked_at = NULL,
                             error = NULL,
                             completed_at = NULL
               RETURNING id""",
            user_id,
            message_id,
            callback_url,
            json.dumps(payload, ensure_ascii=False),
        )


class OutboundDeliveryWorker:
    def __init__(self, interval_seconds: float = 1.0) -> None:
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
                logger.exception("Outbound delivery worker failed")
            await asyncio.sleep(self.interval_seconds)

    async def process_due(self) -> int:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """UPDATE outbound_deliveries
                   SET status = 'sending', attempts = attempts + 1,
                       locked_at = CURRENT_TIMESTAMP
                   WHERE id IN (
                       SELECT id FROM outbound_deliveries
                       WHERE (
                           status = 'pending' AND next_attempt_at <= CURRENT_TIMESTAMP
                       ) OR (
                           status = 'sending'
                           AND locked_at < CURRENT_TIMESTAMP - INTERVAL '5 minutes'
                       )
                       ORDER BY next_attempt_at, id
                       FOR UPDATE SKIP LOCKED
                       LIMIT 20
                   )
                   RETURNING id, user_id, message_id, callback_url, payload, attempts"""
            )

        completed = 0
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
            for row in rows:
                try:
                    await self._deliver(client, dict(row))
                    completed += 1
                except Exception as exc:
                    logger.warning("Delivery %s failed: %s", row["id"], exc)
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """UPDATE outbound_deliveries
                               SET status = CASE WHEN attempts >= 5 THEN 'failed' ELSE 'pending' END,
                                   error = $2, locked_at = NULL,
                                   next_attempt_at = CURRENT_TIMESTAMP
                                       + (LEAST(300, POWER(2, attempts)::int * 5) * INTERVAL '1 second')
                               WHERE id = $1 AND status = 'sending'""",
                            row["id"],
                            str(exc)[:2000],
                        )
                        await conn.execute(
                            """UPDATE conversation_messages
                               SET status = CASE WHEN $2 >= 5 THEN 'failed' ELSE 'queued' END
                               WHERE id = $1""",
                            row["message_id"],
                            row["attempts"],
                        )
        return completed

    async def _deliver(self, client: httpx.AsyncClient, delivery: dict) -> None:
        payload = delivery["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        timestamp = datetime.now(timezone.utc).isoformat()
        secret = await get_delivery_secret(delivery["user_id"])
        if not secret:
            raise RuntimeError("Outbound webhook secret is not configured")
        signature = sign_payload(secret, timestamp, body)
        response = await client.post(
            delivery["callback_url"],
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-OpenClaw-Timestamp": timestamp,
                "X-OpenClaw-Signature": f"sha256={signature}",
                "Idempotency-Key": f"message-{delivery['message_id']}",
            },
        )
        response.raise_for_status()

        pool = await get_db_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """UPDATE outbound_deliveries
                       SET status = 'delivered', response_status = $2,
                           response_body = $3, completed_at = CURRENT_TIMESTAMP,
                           locked_at = NULL, error = NULL
                       WHERE id = $1 AND status = 'sending'""",
                    delivery["id"],
                    response.status_code,
                    response.text[:4000],
                )
                await conn.execute(
                    "UPDATE conversation_messages SET status = 'sent' WHERE id = $1",
                    delivery["message_id"],
                )


outbound_delivery_worker = OutboundDeliveryWorker()
