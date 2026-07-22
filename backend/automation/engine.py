import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from db import get_db_pool
from automation.intelligence import analyze_message, generate_smart_reply
from automation.delivery import enqueue_delivery
from automation.providers import automation_ai_provider
from automation.settings import evaluate_reply_policy, get_automation_settings

logger = logging.getLogger(__name__)

SUPPORTED_TRIGGER_TYPES = {
    "inbound_message",
    "new_contact",
    "profile_submitted",
    "webhook",
}
SUPPORTED_STEP_TYPES = {
    "condition",
    "send_message",
    "add_tag",
    "update_lead_status",
    "delay",
    "analyze_intent",
    "smart_reply",
    "handoff",
    "end",
}
SUPPORTED_CONDITION_OPERATORS = {
    "equals",
    "not_equals",
    "contains",
    "in",
    "exists",
    "gt",
    "gte",
    "lt",
    "lte",
}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def as_dict(value: Any, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else (default or {})
        except json.JSONDecodeError:
            return default or {}
    return default or {}


def render_template(template: str, context: Dict[str, Any]) -> str:
    """Render simple dotted placeholders such as {{contact.name}}."""

    def replace(match: re.Match) -> str:
        value: Any = context
        for part in match.group(1).strip().split("."):
            if not isinstance(value, dict):
                return ""
            value = value.get(part)
        return "" if value is None else str(value)

    return re.sub(r"\{\{\s*([^{}]+?)\s*\}\}", replace, template or "")


def get_context_value(context: Dict[str, Any], field: str) -> Any:
    value: Any = context
    for part in field.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def evaluate_condition(config: Dict[str, Any], context: Dict[str, Any]) -> bool:
    actual = get_context_value(context, str(config.get("field", "")))
    expected = config.get("value")
    operator = config.get("operator", "equals")

    if operator == "exists":
        return actual not in (None, "", [], {})
    if operator == "equals":
        return actual == expected
    if operator == "not_equals":
        return actual != expected
    if operator == "contains":
        if isinstance(actual, list):
            return expected in actual
        return str(expected).lower() in str(actual or "").lower()
    if operator == "in":
        return actual in (expected if isinstance(expected, list) else [expected])
    if operator in {"gt", "gte", "lt", "lte"}:
        try:
            left, right = float(actual), float(expected)
        except (TypeError, ValueError):
            return False
        return {
            "gt": left > right,
            "gte": left >= right,
            "lt": left < right,
            "lte": left <= right,
        }[operator]
    return False


def flow_matches_event(flow: Dict[str, Any], event: Dict[str, Any]) -> bool:
    if flow.get("trigger_type") != event.get("event_type"):
        return False
    config = as_dict(flow.get("trigger_config"))
    channel = config.get("channel")
    if channel and channel != event.get("channel"):
        return False
    keywords = [str(item).lower() for item in config.get("keywords", []) if str(item).strip()]
    if keywords:
        content = str(event.get("message", {}).get("content", "")).lower()
        match_mode = config.get("keyword_match", "any")
        matches = [keyword in content for keyword in keywords]
        if match_mode == "all" and not all(matches):
            return False
        if match_mode != "all" and not any(matches):
            return False
    return True


def validate_definition(definition: Dict[str, Any]) -> None:
    steps = definition.get("steps")
    if not isinstance(steps, list):
        raise ValueError("definition.steps must be a list")
    if len(steps) > 100:
        raise ValueError("definition.steps cannot contain more than 100 steps")
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError(f"step {index} must be an object")
        step_type = step.get("type")
        if step_type not in SUPPORTED_STEP_TYPES:
            raise ValueError(f"unsupported step type at index {index}: {step_type}")
        config = step.get("config", {})
        if not isinstance(config, dict):
            raise ValueError(f"step {index} config must be an object")
        if step_type == "condition":
            if not str(config.get("field", "")).strip():
                raise ValueError(f"condition step {index} requires a field")
            if config.get("operator", "equals") not in SUPPORTED_CONDITION_OPERATORS:
                raise ValueError(f"condition step {index} has an invalid operator")
        elif step_type == "send_message":
            content = str(config.get("content", ""))
            if not content.strip() or len(content) > 10000:
                raise ValueError(f"send_message step {index} content must be 1-10000 characters")
        elif step_type == "add_tag":
            tag = str(config.get("tag", ""))
            if not tag.strip() or len(tag) > 100:
                raise ValueError(f"add_tag step {index} tag must be 1-100 characters")
        elif step_type == "delay":
            try:
                seconds = int(config.get("seconds", 0))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"delay step {index} seconds must be an integer") from exc
            if seconds < 1 or seconds > 30 * 24 * 3600:
                raise ValueError(f"delay step {index} seconds must be between 1 and 2592000")


class AutomationEngine:
    async def process_event(
        self,
        user_id: int,
        event_row_id: int,
        event: Dict[str, Any],
        conversation_id: Optional[int],
        lead_id: Optional[int],
    ) -> list[int]:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            if conversation_id is not None:
                conversation_mode = await conn.fetchval(
                    "SELECT mode FROM conversations WHERE id = $1 AND user_id = $2",
                    conversation_id,
                    user_id,
                )
                if conversation_mode == "human":
                    return []
            rows = await conn.fetch(
                """SELECT id, user_id, name, trigger_type, trigger_config, definition
                   FROM automation_flows
                   WHERE user_id = $1 AND status = 'active'
                   ORDER BY id""",
                user_id,
            )

        run_ids = []
        for row in rows:
            flow = dict(row)
            flow["trigger_config"] = as_dict(flow.get("trigger_config"))
            flow["definition"] = as_dict(flow.get("definition"), {"steps": []})
            if flow_matches_event(flow, event):
                try:
                    run_id = await self.execute_flow(
                        flow=flow,
                        event=event,
                        event_row_id=event_row_id,
                        conversation_id=conversation_id,
                        lead_id=lead_id,
                    )
                    run_ids.append(run_id)
                except Exception:
                    logger.exception("Flow %s failed while processing event %s", flow["id"], event_row_id)
                    async with pool.acquire() as conn:
                        failed_run_id = await conn.fetchval(
                            """SELECT id
                               FROM automation_runs
                               WHERE user_id = $1 AND flow_id = $2 AND event_id = $3
                               ORDER BY id DESC
                               LIMIT 1""",
                            user_id,
                            flow["id"],
                            event_row_id,
                        )
                    if failed_run_id is not None:
                        run_ids.append(failed_run_id)
        return run_ids

    async def execute_flow(
        self,
        flow: Dict[str, Any],
        event: Dict[str, Any],
        event_row_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
        lead_id: Optional[int] = None,
        start_step: int = 0,
        run_id: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
        parent_run_id: Optional[int] = None,
    ) -> int:
        definition = as_dict(flow.get("definition"), {"steps": []})
        validate_definition(definition)
        run_context = context or self._build_context(event, conversation_id, lead_id)
        pool = await get_db_pool()

        async with pool.acquire() as conn:
            if run_id is None:
                run_id = await conn.fetchval(
                    """INSERT INTO automation_runs
                       (flow_id, user_id, event_id, conversation_id, lead_id, context,
                        current_step, parent_run_id)
                       VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)
                       RETURNING id""",
                    flow["id"],
                    flow["user_id"],
                    event_row_id,
                    conversation_id,
                    lead_id,
                    _json(run_context),
                    start_step,
                    parent_run_id,
                )
            else:
                await conn.execute(
                    """UPDATE automation_runs
                       SET status = 'running', current_step = $2, error = NULL
                       WHERE id = $1""",
                    run_id,
                    start_step,
                )

        if start_step > 0 and await self._is_human_owned(conversation_id, flow["user_id"]):
            async with pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO automation_run_steps
                       (run_id, step_index, step_type, status, input, output, completed_at)
                       VALUES ($1, $2, 'human_guard', 'completed', '{}'::jsonb, $3::jsonb,
                               CURRENT_TIMESTAMP)""",
                    run_id,
                    start_step,
                    _json(
                        {
                            "skipped": True,
                            "suppressed": True,
                            "reason": "conversation is human-owned",
                        }
                    ),
                )
                await conn.execute(
                    """UPDATE automation_runs
                       SET status = 'suppressed', current_step = $2,
                           completed_at = CURRENT_TIMESTAMP
                       WHERE id = $1""",
                    run_id,
                    start_step,
                )
            return run_id

        try:
            for index in range(start_step, len(definition["steps"])):
                step = definition["steps"][index]
                result = await self._execute_step(
                    run_id=run_id,
                    user_id=flow["user_id"],
                    step_index=index,
                    step=step,
                    context=run_context,
                    conversation_id=conversation_id,
                    lead_id=lead_id,
                )
                async with pool.acquire() as conn:
                    await conn.execute(
                        """UPDATE automation_runs
                           SET current_step = $2, context = $3::jsonb
                           WHERE id = $1""",
                        run_id,
                        index,
                        _json(run_context),
                    )
                if result.get("waiting"):
                    return run_id
                if result.get("suppressed"):
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """UPDATE automation_runs
                               SET status = 'suppressed', completed_at = CURRENT_TIMESTAMP
                               WHERE id = $1""",
                            run_id,
                        )
                    return run_id
                if result.get("stop"):
                    break

            async with pool.acquire() as conn:
                await conn.execute(
                    """UPDATE automation_runs
                       SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                       WHERE id = $1""",
                    run_id,
                )
            return run_id
        except Exception as exc:
            logger.exception("Automation run %s failed", run_id)
            async with pool.acquire() as conn:
                await conn.execute(
                    """UPDATE automation_runs
                       SET status = 'failed', error = $2, completed_at = CURRENT_TIMESTAMP
                       WHERE id = $1""",
                    run_id,
                    str(exc),
                )
            raise

    async def _execute_step(
        self,
        run_id: int,
        user_id: int,
        step_index: int,
        step: Dict[str, Any],
        context: Dict[str, Any],
        conversation_id: Optional[int],
        lead_id: Optional[int],
    ) -> Dict[str, Any]:
        step_type = step["type"]
        config = step.get("config") or {}
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            step_row_id = await conn.fetchval(
                """INSERT INTO automation_run_steps
                   (run_id, step_index, step_type, status, input)
                   VALUES ($1, $2, $3, 'running', $4::jsonb)
                   RETURNING id""",
                run_id,
                step_index,
                step_type,
                _json(config),
            )

        try:
            if step_type in {"send_message", "smart_reply"} and await self._is_human_owned(
                conversation_id,
                user_id,
            ):
                result = {
                    "skipped": True,
                    "reason": "conversation is human-owned",
                    "suppressed": True,
                    "stop": True,
                }
            elif step_type == "condition":
                matched = evaluate_condition(config, context)
                result = {"matched": matched, "stop": not matched and config.get("on_false", "stop") == "stop"}
            elif step_type == "send_message":
                if conversation_id is None:
                    raise ValueError("send_message requires a conversation")
                content = render_template(str(config.get("content", "")), context)
                message_id = await self._insert_automation_message(
                    conversation_id,
                    user_id,
                    content,
                    {"source": "automation", "run_id": run_id},
                    step_index,
                )
                result = (
                    {"message_id": message_id, "content": content}
                    if message_id is not None
                    else {
                        "skipped": True,
                        "reason": "conversation is human-owned",
                        "suppressed": True,
                        "stop": True,
                    }
                )
            elif step_type == "add_tag":
                if lead_id is None:
                    raise ValueError("add_tag requires a lead")
                tag = render_template(str(config.get("tag", "")), context).strip()
                if not tag:
                    raise ValueError("tag cannot be empty")
                async with pool.acquire() as conn:
                    await conn.execute(
                        """UPDATE leads
                           SET tags = ARRAY(
                               SELECT DISTINCT value
                               FROM unnest(COALESCE(tags, '{}'::text[]) || ARRAY[$1]::text[]) AS value
                           )
                           WHERE id = $2 AND user_id = $3""",
                        tag,
                        lead_id,
                        user_id,
                    )
                context.setdefault("contact", {}).setdefault("tags", []).append(tag)
                result = {"tag": tag}
            elif step_type == "update_lead_status":
                if lead_id is None:
                    raise ValueError("update_lead_status requires a lead")
                status = str(config.get("status", "qualified"))
                if status not in {"new", "contacted", "qualified", "converted", "lost"}:
                    raise ValueError("invalid lead status")
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE leads SET status = $1 WHERE id = $2 AND user_id = $3",
                        status,
                        lead_id,
                        user_id,
                    )
                context.setdefault("contact", {})["status"] = status
                result = {"status": status}
            elif step_type == "delay":
                seconds = int(config.get("seconds", 0))
                if seconds < 1 or seconds > 30 * 24 * 3600:
                    raise ValueError("delay seconds must be between 1 and 2592000")
                execute_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=seconds)
                async with pool.acquire() as conn:
                    job_id = await conn.fetchval(
                        """INSERT INTO automation_jobs
                           (run_id, user_id, step_index, execute_at, payload)
                           VALUES ($1, $2, $3, $4, $5::jsonb)
                           ON CONFLICT (run_id, step_index)
                           DO UPDATE SET
                               execute_at = EXCLUDED.execute_at,
                               payload = EXCLUDED.payload,
                               status = 'pending',
                               attempts = 0,
                               locked_at = NULL,
                               error = NULL,
                               completed_at = NULL
                           RETURNING id""",
                        run_id,
                        user_id,
                        step_index,
                        execute_at,
                        _json({"context": context}),
                    )
                    await conn.execute(
                        "UPDATE automation_runs SET status = 'waiting', current_step = $2 WHERE id = $1",
                        run_id,
                        step_index,
                    )
                result = {"waiting": True, "job_id": job_id, "execute_at": execute_at.isoformat()}
            elif step_type == "analyze_intent":
                settings = await get_automation_settings(user_id)
                try:
                    ai_result = await automation_ai_provider.generate(
                        context=context,
                        provider_mode=settings["ai_provider"],
                        model=settings["ai_model"] or None,
                        language=str(config.get("language", "auto")),
                    )
                except Exception as exc:
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """INSERT INTO automation_ai_calls
                               (user_id, run_id, conversation_id, provider, model,
                                status, error)
                               VALUES ($1, $2, $3, $4, $5, 'failed', $6)""",
                            user_id,
                            run_id,
                            conversation_id,
                            settings["ai_provider"],
                            settings["ai_model"] or "configured-fallback-chain",
                            str(exc)[:2000],
                        )
                    raise
                intelligence = ai_result.output
                context["intelligence"] = intelligence
                async with pool.acquire() as conn:
                    await conn.execute(
                        """INSERT INTO automation_ai_calls
                           (user_id, run_id, conversation_id, provider, model, status,
                            prompt_tokens, completion_tokens, latency_ms, output, error)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11)""",
                        user_id,
                        run_id,
                        conversation_id,
                        ai_result.provider,
                        ai_result.model,
                        "fallback" if ai_result.error else "completed",
                        ai_result.prompt_tokens,
                        ai_result.completion_tokens,
                        ai_result.latency_ms,
                        _json(intelligence),
                        ai_result.error,
                    )
                    if lead_id is not None:
                        await conn.execute(
                            """UPDATE leads
                               SET quality_score = $1,
                                   metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb
                               WHERE id = $3 AND user_id = $4""",
                            intelligence["score"],
                            _json(
                                {
                                    "intent": intelligence["intent"],
                                    "temperature": intelligence["temperature"],
                                    "intelligence": intelligence,
                                }
                            ),
                            lead_id,
                            user_id,
                        )
                    if conversation_id is not None:
                        await conn.execute(
                            """UPDATE conversations
                               SET intent = $1, intent_confidence = $2, ai_summary = $3,
                                   priority = $4, updated_at = CURRENT_TIMESTAMP
                               WHERE id = $5 AND user_id = $6""",
                            intelligence["intent"],
                            intelligence["confidence"],
                            intelligence["summary"],
                            intelligence["priority"],
                            conversation_id,
                            user_id,
                        )
                result = intelligence
            elif step_type == "smart_reply":
                if conversation_id is None:
                    raise ValueError("smart_reply requires a conversation")
                if "intelligence" not in context:
                    context["intelligence"] = analyze_message(
                        str((context.get("message") or {}).get("content", "")),
                        context.get("contact") or {},
                    )
                content = str(
                    context["intelligence"].get("reply")
                    or generate_smart_reply(context, config)
                ).strip()
                policy = await evaluate_reply_policy(
                    user_id,
                    conversation_id,
                    content,
                    context["intelligence"],
                )
                settings = policy["settings"]
                action = policy["action"]
                message_status = {
                    "draft": "draft",
                    "review": "pending_review",
                    "automatic": "queued",
                }[action]
                if action == "automatic" and (
                    not settings["outbound_webhook_enabled"]
                    or not settings["outbound_webhook_url"]
                    or not settings["webhook_secret_configured"]
                ):
                    action = "review"
                    message_status = "pending_review"
                    policy["reason"] = "Outbound webhook is not fully configured."
                message_id = await self._insert_automation_message(
                    conversation_id,
                    user_id,
                    content,
                    {
                        "source": "automation",
                        "generation_mode": "local_intelligence",
                        "run_id": run_id,
                        "provider": context["intelligence"].get("generation_mode", "local_intelligence"),
                        "policy_action": action,
                        "policy_reason": policy["reason"],
                    },
                    step_index,
                    message_status,
                )
                delivery_id = None
                if message_id is not None and action == "automatic":
                    delivery_id = await enqueue_delivery(
                        user_id=user_id,
                        message_id=message_id,
                        callback_url=settings["outbound_webhook_url"],
                        payload={
                            "event": "automation.message.created",
                            "message_id": message_id,
                            "conversation_id": conversation_id,
                            "external_id": (context.get("contact") or {}).get("external_id"),
                            "contact": context.get("contact") or {},
                            "content": content,
                            "intent": context["intelligence"].get("intent"),
                            "score": context["intelligence"].get("score"),
                            "confidence": context["intelligence"].get("confidence"),
                            "run_id": run_id,
                            "step_index": step_index,
                        },
                    )
                result = (
                    {
                        "message_id": message_id,
                        "content": content,
                        "message_status": message_status,
                        "policy_action": action,
                        "policy_reason": policy["reason"],
                        "delivery_id": delivery_id,
                    }
                    if message_id is not None
                    else {
                        "skipped": True,
                        "reason": "conversation is human-owned",
                        "suppressed": True,
                        "stop": True,
                    }
                )
            elif step_type == "handoff":
                if conversation_id is None:
                    raise ValueError("handoff requires a conversation")
                intelligence = context.get("intelligence") or {}
                only_if_recommended = bool(config.get("only_if_recommended", False))
                if only_if_recommended and not intelligence.get("recommended_handoff"):
                    result = {"handed_off": False, "reason": "handoff not recommended"}
                else:
                    reason = render_template(
                        str(config.get("reason") or intelligence.get("handoff_reason") or "Automation requested human review."),
                        context,
                    )
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """UPDATE conversations
                               SET mode = 'human', status = 'open', priority = 'urgent',
                                   handoff_reason = $1, updated_at = CURRENT_TIMESTAMP
                               WHERE id = $2 AND user_id = $3""",
                            reason,
                            conversation_id,
                            user_id,
                        )
                        await conn.execute(
                            """INSERT INTO conversation_events
                               (conversation_id, user_id, event_type, actor_type, payload)
                               VALUES ($1, $2, 'handoff_requested', 'automation', $3::jsonb)
                               ON CONFLICT DO NOTHING""",
                            conversation_id,
                            user_id,
                            _json({"run_id": run_id, "reason": reason}),
                        )
                    result = {"handed_off": True, "reason": reason, "stop": True}
            elif step_type == "end":
                result = {"stop": True}
            else:
                raise ValueError(f"unsupported step type: {step_type}")

            async with pool.acquire() as conn:
                await conn.execute(
                    """UPDATE automation_run_steps
                       SET status = $2, output = $3::jsonb, completed_at = CURRENT_TIMESTAMP
                       WHERE id = $1""",
                    step_row_id,
                    "waiting" if result.get("waiting") else "completed",
                    _json(result),
                )
            return result
        except Exception as exc:
            async with pool.acquire() as conn:
                await conn.execute(
                    """UPDATE automation_run_steps
                       SET status = 'failed', error = $2, completed_at = CURRENT_TIMESTAMP
                       WHERE id = $1""",
                    step_row_id,
                    str(exc),
                )
            raise

    @staticmethod
    async def _is_human_owned(conversation_id: Optional[int], user_id: int) -> bool:
        if conversation_id is None:
            return False
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            mode = await conn.fetchval(
                "SELECT mode FROM conversations WHERE id = $1 AND user_id = $2",
                conversation_id,
                user_id,
            )
        return mode == "human"

    @staticmethod
    async def _insert_automation_message(
        conversation_id: int,
        user_id: int,
        content: str,
        metadata: Dict[str, Any],
        step_index: int,
        status: str = "simulated",
    ) -> Optional[int]:
        """Insert only while automation owns the conversation.

        The row lock establishes ordering with takeover/release updates, so an
        automation send cannot race past a committed human takeover.
        """

        pool = await get_db_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                mode = await conn.fetchval(
                    """SELECT mode
                       FROM conversations
                       WHERE id = $1 AND user_id = $2
                       FOR UPDATE""",
                    conversation_id,
                    user_id,
                )
                if mode is None:
                    raise ValueError("conversation no longer exists")
                if mode == "human":
                    return None
                message_metadata = {**metadata, "step_index": step_index}
                message_id = await conn.fetchval(
                    """INSERT INTO conversation_messages
                       (conversation_id, user_id, direction, message_type, content, status, metadata)
                       VALUES ($1, $2, 'outbound', 'text', $3, $4, $5::jsonb)
                       ON CONFLICT DO NOTHING
                       RETURNING id""",
                    conversation_id,
                    user_id,
                    content,
                    status,
                    _json(message_metadata),
                )
                if message_id is None:
                    message_id = await conn.fetchval(
                        """SELECT id
                           FROM conversation_messages
                           WHERE conversation_id = $1
                             AND user_id = $2
                             AND metadata->>'source' = 'automation'
                             AND metadata->>'run_id' = $3
                             AND metadata->>'step_index' = $4
                           ORDER BY id DESC
                           LIMIT 1""",
                        conversation_id,
                        user_id,
                        str(metadata["run_id"]),
                        str(step_index),
                    )
                await conn.execute(
                    """UPDATE conversations
                       SET last_message_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                       WHERE id = $1 AND user_id = $2""",
                    conversation_id,
                    user_id,
                )
        return message_id

    @staticmethod
    def _build_context(
        event: Dict[str, Any],
        conversation_id: Optional[int],
        lead_id: Optional[int],
    ) -> Dict[str, Any]:
        return {
            "event": event,
            "message": event.get("message") or {},
            "contact": event.get("contact") or {},
            "conversation": {"id": conversation_id},
            "lead_id": lead_id,
        }


class AutomationJobWorker:
    def __init__(self, interval_seconds: float = 1.0):
        self.interval_seconds = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self.engine = AutomationEngine()

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
                await self.process_due_jobs()
            except Exception:
                logger.exception("Failed to process automation jobs")
            await asyncio.sleep(self.interval_seconds)

    async def process_due_jobs(self) -> int:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            jobs = await conn.fetch(
                """UPDATE automation_jobs
                   SET status = 'running', attempts = attempts + 1,
                       locked_at = CURRENT_TIMESTAMP
                   WHERE id IN (
                       SELECT id FROM automation_jobs
                       WHERE (
                           status = 'pending' AND execute_at <= CURRENT_TIMESTAMP
                       ) OR (
                           status = 'running'
                           AND (
                               locked_at IS NULL
                               OR locked_at < CURRENT_TIMESTAMP - INTERVAL '5 minutes'
                           )
                       )
                       ORDER BY execute_at
                       FOR UPDATE SKIP LOCKED
                       LIMIT 20
                   )
                   RETURNING id, run_id, user_id, step_index, payload"""
            )

        processed = 0
        for job in jobs:
            try:
                await self._resume_job(dict(job))
                async with pool.acquire() as conn:
                    await conn.execute(
                        """UPDATE automation_jobs
                           SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                           WHERE id = $1 AND status = 'running'""",
                        job["id"],
                    )
                processed += 1
            except Exception as exc:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """UPDATE automation_jobs
                           SET status = CASE WHEN attempts >= 3 THEN 'failed' ELSE 'pending' END,
                               error = $2,
                               locked_at = NULL,
                               execute_at = CASE WHEN attempts >= 3 THEN execute_at
                                                 ELSE CURRENT_TIMESTAMP + INTERVAL '30 seconds' END
                           WHERE id = $1""",
                        job["id"],
                        str(exc),
                    )
        return processed

    async def _resume_job(self, job: Dict[str, Any]) -> None:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT r.id AS run_id, r.event_id, r.conversation_id, r.lead_id,
                          r.status AS run_status,
                          r.context, f.id, f.user_id, f.name, f.trigger_type,
                          f.trigger_config, f.definition
                   FROM automation_runs r
                   JOIN automation_flows f ON f.id = r.flow_id
                   WHERE r.id = $1 AND r.user_id = $2""",
                job["run_id"],
                job["user_id"],
            )
        if not row:
            raise ValueError("automation run no longer exists")
        data = dict(row)
        if data["run_status"] in {"completed", "cancelled", "suppressed"}:
            return
        flow = {
            "id": data["id"],
            "user_id": data["user_id"],
            "name": data["name"],
            "trigger_type": data["trigger_type"],
            "trigger_config": as_dict(data["trigger_config"]),
            "definition": as_dict(data["definition"], {"steps": []}),
        }
        await self.engine.execute_flow(
            flow=flow,
            event={},
            event_row_id=data["event_id"],
            conversation_id=data["conversation_id"],
            lead_id=data["lead_id"],
            start_step=job["step_index"] + 1,
            run_id=data["run_id"],
            context=as_dict(data["context"]),
        )


automation_job_worker = AutomationJobWorker()
