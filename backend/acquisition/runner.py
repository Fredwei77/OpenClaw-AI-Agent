from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Optional

from db import get_db_pool

logger = logging.getLogger(__name__)


class AcquisitionTaskWorker:
    def __init__(self, interval_seconds: float = 3.0) -> None:
        self.interval_seconds = interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._running:
            return
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """UPDATE acquisition_tasks
                   SET status = 'active', updated_at = CURRENT_TIMESTAMP
                   WHERE status = 'running'"""
            )
            await conn.execute(
                """UPDATE acquisition_task_runs
                   SET status = 'failed', error = 'Interrupted by service restart',
                       completed_at = CURRENT_TIMESTAMP
                   WHERE status = 'running'"""
            )
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
                logger.exception("Acquisition task worker failed")
            await asyncio.sleep(self.interval_seconds)

    async def process_due(self) -> int:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """UPDATE acquisition_tasks
                   SET status = 'running', updated_at = CURRENT_TIMESTAMP
                   WHERE id = (
                       SELECT id FROM acquisition_tasks
                       WHERE status = 'active' AND next_run_at <= CURRENT_TIMESTAMP
                       ORDER BY next_run_at, id
                       FOR UPDATE SKIP LOCKED LIMIT 1
                   )
                   RETURNING *"""
            )
        if not row:
            return 0
        await self.execute(dict(row))
        return 1

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        pool = await get_db_pool()
        user = SimpleNamespace(id=task["user_id"])
        async with pool.acquire() as conn:
            run_id = await conn.fetchval(
                """INSERT INTO acquisition_task_runs (task_id, user_id, status)
                   VALUES ($1, $2, 'running') RETURNING id""",
                task["id"], task["user_id"],
            )
        stage = "acquisition"
        try:
            from api.agents import (
                AcquisitionPipelineRequest,
                acquisition_pipeline,
            )

            platforms = task["platforms"]
            if isinstance(platforms, str):
                platforms = json.loads(platforms)
            request = AcquisitionPipelineRequest(
                keyword=task["keyword"],
                platforms=platforms,
                max_results_per_platform=task["max_results_per_platform"],
                max_outreach_leads=task["max_outreach_leads"],
                product_context=task["product_context"] or task["keyword"],
            )
            await self._step(run_id, "acquisition", "running", request.model_dump(), {})
            result = await acquisition_pipeline(request, current_user=user)
            await self._step(run_id, "acquisition", "completed", request.model_dump(), result)
            stage = "delivery_policy"
            delivery = await self._apply_delivery_policy(task, run_id, result, user)
            final = {"acquisition": result, "delivery": delivery}
            await self._finish(task, run_id, final)
            return final
        except Exception as exc:
            logger.exception("Acquisition task %s failed", task["id"])
            await self._step(run_id, stage, "failed", {}, {}, str(exc)[:2000])
            async with pool.acquire() as conn:
                await conn.execute(
                    """UPDATE acquisition_task_runs SET status = 'failed', error = $1,
                              completed_at = CURRENT_TIMESTAMP WHERE id = $2""",
                    str(exc)[:2000], run_id,
                )
                await conn.execute(
                    """UPDATE acquisition_tasks SET status = 'failed', last_error = $1,
                              updated_at = CURRENT_TIMESTAMP WHERE id = $2""",
                    str(exc)[:2000], task["id"],
                )
            raise

    async def _apply_delivery_policy(self, task, run_id, result, user) -> dict[str, Any]:
        campaign_id = (result.get("outreach") or {}).get("summary", {}).get("campaign_id")
        await self._step(
            run_id,
            "delivery_policy",
            "running",
            {"approval_mode": task["approval_mode"], "delivery_mode": task["delivery_mode"]},
            {},
        )
        if not campaign_id or task["approval_mode"] == "review":
            output = {"status": "awaiting_review", "campaign_id": campaign_id}
            await self._step(run_id, "delivery_policy", "completed", {}, output)
            return output
        if task["delivery_mode"] != "live":
            output = {"status": "dry_run", "campaign_id": campaign_id, "sent": 0}
            await self._step(run_id, "delivery_policy", "completed", {}, output)
            return output

        from api.chat import (
            ChatSendRequest,
            FollowUpSequenceRequest,
            approve_message,
            create_follow_up_sequence,
            send_message,
        )

        pool = await get_db_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT m.id FROM marketing_messages m
                   JOIN leads l ON l.id = m.lead_id AND l.user_id = m.user_id
                   WHERE m.user_id = $1 AND m.campaign_id = $2
                     AND m.channel = 'email' AND m.status = 'draft'
                     AND NULLIF(BTRIM(l.email), '') IS NOT NULL
                   ORDER BY m.id""",
                task["user_id"], campaign_id,
            )
        sent_ids = []
        failures = []
        for row in rows:
            message_id = row["id"]
            try:
                await approve_message(message_id, current_user=user)
                sent = await send_message(
                    message_id,
                    ChatSendRequest(provider="email", dry_run=False),
                    current_user=user,
                )
                if sent.status == "sent":
                    await create_follow_up_sequence(
                        message_id,
                        FollowUpSequenceRequest(
                            delays_hours=[72, 168, 336], language="en", stop_on_reply=True
                        ),
                        current_user=user,
                    )
                    sent_ids.append(message_id)
            except Exception as exc:
                failures.append({"message_id": message_id, "error": str(exc)[:500]})
        output = {"status": "completed", "campaign_id": campaign_id, "sent_ids": sent_ids, "failures": failures}
        await self._step(run_id, "delivery_policy", "completed", {}, output)
        return output

    async def _finish(self, task, run_id, result) -> None:
        interval = task.get("interval_hours")
        next_run = datetime.now() + timedelta(hours=interval) if interval else task["next_run_at"]
        status = "active" if interval else "completed"
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """UPDATE acquisition_task_runs SET status = 'completed', result = $1::jsonb,
                              completed_at = CURRENT_TIMESTAMP WHERE id = $2""",
                    json.dumps(result, ensure_ascii=False, default=str), run_id,
                )
                await conn.execute(
                    """UPDATE acquisition_tasks SET status = $1, next_run_at = $2,
                              last_run_at = CURRENT_TIMESTAMP, run_count = run_count + 1,
                              last_error = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = $3""",
                    status, next_run, task["id"],
                )

    @staticmethod
    async def _step(run_id, step_type, status, input_data, output_data, error=None) -> None:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            if status == "running":
                await conn.execute(
                    """INSERT INTO acquisition_task_run_steps
                       (run_id, step_type, status, input) VALUES ($1, $2, $3, $4::jsonb)""",
                    run_id, step_type, status, json.dumps(input_data, default=str),
                )
            else:
                await conn.execute(
                    """UPDATE acquisition_task_run_steps SET status = $1, output = $2::jsonb,
                              error = $3, completed_at = CURRENT_TIMESTAMP
                       WHERE id = (SELECT id FROM acquisition_task_run_steps
                                   WHERE run_id = $4 AND step_type = $5
                                   ORDER BY id DESC LIMIT 1)""",
                    status, json.dumps(output_data, default=str), error, run_id, step_type,
                )


acquisition_task_worker = AcquisitionTaskWorker()
