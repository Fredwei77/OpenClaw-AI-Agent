from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from agents.chat_agent import ChatAgent
from agents.chat_agent.channel_adapters import EmailChannelAdapter, WebhookChannelAdapter
from agents.chat_agent.follow_up import build_follow_up_copy
from agents.chat_agent.validators import validate_message
from backend.email_utils import sanitize_lead_email
from .optimization import apply_template_or_experiment, estimate_message_cost
from automation.settings import get_automation_settings, get_delivery_secret
from scheduler.task_queue import TaskPriority, get_task_queue
from .auth import UserResponse, get_current_user, get_db_pool


router = APIRouter()
agent = ChatAgent()

MESSAGE_SELECT = """SELECT m.id, m.lead_id, m.campaign_id, m.channel,
                           COALESCE(m.subject, '') AS subject, m.body,
                           COALESCE(m.cta, '') AS cta, m.sequence_step, m.status,
                           m.personalization_evidence, m.quality_score, m.risk_flags,
                           m.generation_provider, m.generation_model, m.approved_by,
                           m.approved_at, m.scheduled_at, m.sent_at, m.provider,
                           m.provider_message_id, m.idempotency_key, m.attempts,
                           m.last_error, m.delivery_task_id, m.follow_up_sequence_id,
                           m.template_version_id, m.ab_experiment_id, m.ab_variant_id,
                           m.estimated_cost_usd,
                           m.created_at, m.updated_at
                    FROM marketing_messages m"""


class ChatGenerateRequest(BaseModel):
    lead_ids: list[int] = Field(..., min_length=1, max_length=100)
    product_context: str = Field(default="", max_length=4000)
    language: Literal["en", "zh"] = "en"
    channels: Optional[list[Literal[
        "email",
        "linkedin_dm",
        "twitter_dm",
        "facebook_dm",
        "instagram_dm",
        "tiktok_dm",
    ]]] = None
    campaign_id: Optional[int] = Field(default=None, ge=1)
    template_version_id: Optional[int] = Field(default=None, ge=1)
    ab_experiment_id: Optional[int] = Field(default=None, ge=1)


class ChatMessageUpdate(BaseModel):
    subject: Optional[str] = Field(default=None, max_length=500)
    body: Optional[str] = Field(default=None, min_length=1, max_length=10000)
    cta: Optional[str] = Field(default=None, max_length=500)


class ChatRegenerateRequest(BaseModel):
    product_context: str = Field(default="", max_length=4000)
    language: Literal["en", "zh"] = "en"


class ChatSendRequest(BaseModel):
    provider: Literal["auto", "email", "social", "webhook"] = "auto"
    dry_run: bool = False


class FollowUpSequenceRequest(BaseModel):
    delays_hours: list[int] = Field(default=[72, 168, 336], min_length=1, max_length=5)
    language: Literal["en", "zh"] = "en"
    stop_on_reply: bool = True


class FollowUpSequenceResponse(BaseModel):
    id: int
    source_message_id: int
    lead_id: int
    channel: str
    status: str
    stop_on_reply: bool
    message_ids: list[int]


class ChatMessageResponse(BaseModel):
    id: int
    lead_id: Optional[int]
    campaign_id: Optional[int]
    channel: str
    subject: str
    body: str
    cta: str
    sequence_step: int
    status: str
    personalization_evidence: list[str]
    quality_score: int
    risk_flags: list[str]
    generation_provider: str
    generation_model: str
    approved_by: Optional[int]
    approved_at: Optional[datetime]
    scheduled_at: Optional[datetime]
    sent_at: Optional[datetime]
    provider: Optional[str]
    provider_message_id: Optional[str]
    idempotency_key: Optional[str]
    attempts: int
    last_error: Optional[str]
    delivery_task_id: Optional[int]
    follow_up_sequence_id: Optional[int]
    template_version_id: Optional[int]
    ab_experiment_id: Optional[int]
    ab_variant_id: Optional[int]
    estimated_cost_usd: float = 0
    created_at: datetime
    updated_at: datetime


class ChatGenerateResponse(BaseModel):
    messages: list[ChatMessageResponse]
    total: int


class ChatMessageEventResponse(BaseModel):
    id: int
    event_type: str
    actor_id: Optional[int]
    payload: dict[str, Any]
    created_at: datetime


def _json_value(value: Any, default: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value if value is not None else default


def _message_response(row) -> ChatMessageResponse:
    data = dict(row)
    data["personalization_evidence"] = _json_value(data["personalization_evidence"], [])
    data["risk_flags"] = _json_value(data["risk_flags"], [])
    return ChatMessageResponse(**data)


def _clean_lead_row(row) -> dict[str, Any]:
    lead = dict(row)
    lead["email"] = sanitize_lead_email(lead.get("email"))
    lead["tags"] = list(lead.get("tags") or [])
    return lead


async def _record_event(conn, message_id: int, user_id: int, event_type: str, actor_id: int, payload: dict) -> None:
    await conn.execute(
        """INSERT INTO marketing_message_events
           (message_id, user_id, event_type, actor_id, payload)
           VALUES ($1, $2, $3, $4, $5::jsonb)""",
        message_id,
        user_id,
        event_type,
        actor_id,
        json.dumps(payload, ensure_ascii=False, default=str),
    )


async def _owned_message(conn, message_id: int, user_id: int, for_update: bool = False):
    suffix = " FOR UPDATE" if for_update else ""
    return await conn.fetchrow(
        f"{MESSAGE_SELECT} WHERE m.id = $1 AND m.user_id = $2{suffix}",
        message_id,
        user_id,
    )


async def _owned_lead(conn, lead_id: int, user_id: int):
    return await conn.fetchrow(
        """SELECT id, platform, username, profile_url, email, followers, tags,
                  metadata, quality_score, status
           FROM leads WHERE id = $1 AND user_id = $2""",
        lead_id,
        user_id,
    )


@router.post("/generate", response_model=ChatGenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_messages(
    request: ChatGenerateRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    lead_ids = list(dict.fromkeys(request.lead_ids))
    async with pool.acquire() as conn:
        if request.campaign_id is not None:
            owned_campaign = await conn.fetchval(
                "SELECT 1 FROM marketing_campaigns WHERE id = $1 AND user_id = $2",
                request.campaign_id,
                current_user.id,
            )
            if not owned_campaign:
                raise HTTPException(status_code=404, detail="Campaign not found")
        rows = await conn.fetch(
            """SELECT id, platform, username, profile_url, email, followers, tags,
                      metadata, quality_score, status
               FROM leads
               WHERE user_id = $1 AND id = ANY($2::int[])
               ORDER BY id""",
            current_user.id,
            lead_ids,
        )
    if len(rows) != len(lead_ids):
        raise HTTPException(status_code=404, detail="One or more leads were not found")

    generated_batches: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for row in rows:
        lead = _clean_lead_row(row)
        research = _json_value(lead.pop("metadata", {}), {})
        try:
            result = await agent.run(
                {
                    "lead": lead,
                    "research": research,
                    "product_context": request.product_context,
                    "language": request.language,
                    "channels": request.channels,
                }
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=409,
                detail={"message": str(exc), "lead_id": lead["id"]},
            ) from exc
        generated_batches.append((lead, research, result))

    created_ids: list[int] = []
    async with pool.acquire() as conn:
        async with conn.transaction():
            for lead, research, result in generated_batches:
                messages, template_id, experiment_id, variant_id = await apply_template_or_experiment(
                    conn,
                    current_user.id,
                    lead,
                    research,
                    result["messages"],
                    request.template_version_id,
                    request.ab_experiment_id,
                )
                cost = estimate_message_cost(result["model"], result["provider"], messages)
                per_message_cost = round(cost / max(1, len(messages)), 6)
                for message in messages:
                    message_id = await conn.fetchval(
                        """INSERT INTO marketing_messages
                           (lead_id, user_id, campaign_id, channel, subject, body, cta,
                            sequence_step, status, personalization_evidence,
                            quality_score, risk_flags, generation_provider,
                            generation_model, template_version_id, ab_experiment_id,
                            ab_variant_id, estimated_cost_usd, updated_at)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, 1, 'draft',
                                   $8::jsonb, $9, $10::jsonb, $11, $12, $13,
                                   $14, $15, $16,
                                   CURRENT_TIMESTAMP)
                           RETURNING id""",
                        lead["id"],
                        current_user.id,
                        request.campaign_id,
                        message["channel"],
                        message["subject"],
                        message["body"],
                        message["cta"],
                        json.dumps(message["personalization_evidence"], ensure_ascii=False),
                        message["quality_score"],
                        json.dumps(message["risk_flags"], ensure_ascii=False),
                        result["provider"],
                        result["model"],
                        template_id,
                        experiment_id,
                        variant_id,
                        per_message_cost,
                    )
                    created_ids.append(message_id)
                    await _record_event(
                        conn,
                        message_id,
                        current_user.id,
                        "generated",
                        current_user.id,
                        {
                            "provider": result["provider"],
                            "model": result["model"],
                            "template_version_id": template_id,
                            "ab_experiment_id": experiment_id,
                            "ab_variant_id": variant_id,
                            "estimated_cost_usd": per_message_cost,
                        },
                    )

    async with pool.acquire() as conn:
        messages = await conn.fetch(
            f"{MESSAGE_SELECT} WHERE m.user_id = $1 AND m.id = ANY($2::int[]) ORDER BY m.id",
            current_user.id,
            created_ids,
        )
    return ChatGenerateResponse(
        messages=[_message_response(row) for row in messages],
        total=len(messages),
    )


@router.post("/messages/{message_id}/regenerate", response_model=ChatMessageResponse)
async def regenerate_message(
    message_id: int,
    request: ChatRegenerateRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await _owned_message(conn, message_id, current_user.id)
        if not row:
            raise HTTPException(status_code=404, detail="Message not found")
        if row["status"] not in {"draft", "failed"}:
            raise HTTPException(status_code=409, detail="Only draft or failed messages can be regenerated")
        lead_row = await _owned_lead(conn, row["lead_id"], current_user.id)
    if not lead_row:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead = _clean_lead_row(lead_row)
    research = _json_value(lead.pop("metadata", {}), {})
    try:
        result = await agent.run(
            {
                "lead": lead,
                "research": research,
                "product_context": request.product_context,
                "language": request.language,
                "channels": [row["channel"]],
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    generated = result["messages"][0]
    async with pool.acquire() as conn:
        async with conn.transaction():
            updated = await conn.fetchrow(
                """UPDATE marketing_messages
                   SET subject = $1, body = $2, cta = $3, status = 'draft',
                       personalization_evidence = $4::jsonb, quality_score = $5,
                       risk_flags = $6::jsonb, generation_provider = $7,
                       generation_model = $8, approved_by = NULL,
                       approved_at = NULL, last_error = NULL,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = $9 AND user_id = $10
                   RETURNING id""",
                generated["subject"],
                generated["body"],
                generated["cta"],
                json.dumps(generated["personalization_evidence"], ensure_ascii=False),
                generated["quality_score"],
                json.dumps(generated["risk_flags"], ensure_ascii=False),
                result["provider"],
                result["model"],
                message_id,
                current_user.id,
            )
            await _record_event(
                conn,
                message_id,
                current_user.id,
                "regenerated",
                current_user.id,
                {"provider": result["provider"], "model": result["model"]},
            )
            row = await _owned_message(conn, updated["id"], current_user.id)
    return _message_response(row)


@router.patch("/messages/{message_id}", response_model=ChatMessageResponse)
async def edit_message(
    message_id: int,
    request: ChatMessageUpdate,
    current_user: UserResponse = Depends(get_current_user),
):
    changes = request.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No message changes supplied")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await _owned_message(conn, message_id, current_user.id, for_update=True)
            if not row:
                raise HTTPException(status_code=404, detail="Message not found")
            if row["status"] not in {"draft", "failed"}:
                raise HTTPException(status_code=409, detail="Only draft or failed messages can be edited")
            message = dict(row)
            message.update(changes)
            evidence = _json_value(message["personalization_evidence"], [])
            quality_score, risk_flags = validate_message(message, evidence)
            updated = await conn.fetchrow(
                """UPDATE marketing_messages
                   SET subject = $1, body = $2, cta = $3, status = 'draft',
                       quality_score = $4, risk_flags = $5::jsonb,
                       approved_by = NULL, approved_at = NULL, last_error = NULL,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = $6 AND user_id = $7
                   RETURNING id""",
                message["subject"],
                message["body"],
                message["cta"],
                quality_score,
                json.dumps(risk_flags, ensure_ascii=False),
                message_id,
                current_user.id,
            )
            await _record_event(
                conn,
                message_id,
                current_user.id,
                "edited",
                current_user.id,
                {"fields": sorted(changes)},
            )
            row = await _owned_message(conn, updated["id"], current_user.id)
    return _message_response(row)


@router.post("/messages/{message_id}/approve", response_model=ChatMessageResponse)
async def approve_message(
    message_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await _owned_message(conn, message_id, current_user.id, for_update=True)
            if not row:
                raise HTTPException(status_code=404, detail="Message not found")
            if row["status"] == "approved":
                return _message_response(row)
            if row["status"] != "draft":
                raise HTTPException(status_code=409, detail="Only draft messages can be approved")
            evidence = _json_value(row["personalization_evidence"], [])
            quality_score, risk_flags = validate_message(dict(row), evidence)
            blocking_flags = {
                "unsupported_channel",
                "empty_body",
                "channel_length_exceeded",
                "unsupported_guarantee",
                "invented_discount",
                "forbidden_greeting",
                "upfront_pricing",
            }
            if quality_score < 60 or blocking_flags.intersection(risk_flags):
                raise HTTPException(
                    status_code=409,
                    detail={"message": "Message failed quality review", "risk_flags": risk_flags},
                )
            await conn.execute(
                """UPDATE marketing_messages
                   SET status = 'approved', quality_score = $1, risk_flags = $2::jsonb,
                       approved_by = $3, approved_at = CURRENT_TIMESTAMP,
                       last_error = NULL, updated_at = CURRENT_TIMESTAMP
                   WHERE id = $4 AND user_id = $3""",
                quality_score,
                json.dumps(risk_flags, ensure_ascii=False),
                current_user.id,
                message_id,
            )
            await _record_event(
                conn,
                message_id,
                current_user.id,
                "approved",
                current_user.id,
                {"quality_score": quality_score, "risk_flags": risk_flags},
            )
            row = await _owned_message(conn, message_id, current_user.id)
    return _message_response(row)


@router.post("/messages/{message_id}/send", response_model=ChatMessageResponse)
async def send_message(
    message_id: int,
    request: ChatSendRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    selected_provider = request.provider
    social_task: Optional[dict[str, Any]] = None
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await _owned_message(conn, message_id, current_user.id, for_update=True)
            if not row:
                raise HTTPException(status_code=404, detail="Message not found")
            if row["status"] == "sent":
                return _message_response(row)
            if row["status"] not in {"approved", "failed"} or row["approved_by"] is None:
                raise HTTPException(status_code=409, detail="Message must be approved before sending")
            lead = await _owned_lead(conn, row["lead_id"], current_user.id)
            if not lead:
                raise HTTPException(status_code=404, detail="Lead not found")
            lead = _clean_lead_row(lead)
            if selected_provider == "auto":
                selected_provider = {
                    "email": "email",
                    "linkedin_dm": "social",
                    "twitter_dm": "social",
                }.get(row["channel"], "webhook")
            if request.dry_run and selected_provider != "social":
                raise HTTPException(status_code=400, detail="Dry run is supported only for social delivery")
            idempotency_key = row["idempotency_key"] or f"chat-message-{message_id}"
            if selected_provider == "social":
                platform = "linkedin" if row["channel"] == "linkedin_dm" else "x"
                payload = {
                    "message_id": message_id,
                    "platform": platform,
                    "dry_run": request.dry_run,
                }
                task_id = await conn.fetchval(
                    """INSERT INTO tasks
                       (agent_name, task_type, payload, status, user_id)
                       VALUES ('ChatDeliveryAgent', 'message', $1::jsonb, 'pending', $2)
                       RETURNING id""",
                    json.dumps(payload),
                    current_user.id,
                )
                await conn.execute(
                    """UPDATE marketing_messages
                       SET status = 'queued', idempotency_key = $1,
                           delivery_task_id = $2, last_error = NULL,
                           updated_at = CURRENT_TIMESTAMP
                       WHERE id = $3 AND user_id = $4""",
                    idempotency_key,
                    task_id,
                    message_id,
                    current_user.id,
                )
                await _record_event(
                    conn,
                    message_id,
                    current_user.id,
                    "social_dry_run_queued" if request.dry_run else "queued",
                    current_user.id,
                    {
                        "provider": "social",
                        "platform": platform,
                        "task_id": task_id,
                        "idempotency_key": idempotency_key,
                    },
                )
                social_task = {
                    "task_id": task_id,
                    "payload": payload,
                    "platform": platform,
                }
            else:
                await conn.execute(
                    """UPDATE marketing_messages
                       SET status = 'sending', idempotency_key = $1,
                           attempts = attempts + 1, last_error = NULL,
                           updated_at = CURRENT_TIMESTAMP
                       WHERE id = $2 AND user_id = $3""",
                    idempotency_key,
                    message_id,
                    current_user.id,
                )
                await _record_event(
                    conn,
                    message_id,
                    current_user.id,
                    "sending",
                    current_user.id,
                    {"provider": selected_provider, "idempotency_key": idempotency_key},
                )

    if social_task is not None:
        queued = await get_task_queue().submit_task(
            task_id=social_task["task_id"],
            user_id=current_user.id,
            agent_name="ChatDeliveryAgent",
            task_type="message",
            payload=social_task["payload"],
            priority=TaskPriority.HIGH,
            platform=social_task["platform"],
        )
        if not queued:
            async with pool.acquire() as conn:
                await conn.execute(
                    """UPDATE marketing_messages
                       SET status = 'failed', last_error = 'Task queue rejected social delivery',
                           updated_at = CURRENT_TIMESTAMP
                       WHERE id = $1 AND user_id = $2""",
                    message_id,
                    current_user.id,
                )
        async with pool.acquire() as conn:
            queued_row = await _owned_message(conn, message_id, current_user.id)
        return _message_response(queued_row)

    message = dict(row)
    lead_data = dict(lead)
    try:
        if selected_provider == "email":
            if row["channel"] != "email":
                raise ValueError("Email provider can only send email-channel messages")
            delivery_result = await EmailChannelAdapter().send(lead_data, message, idempotency_key)
        else:
            settings = await get_automation_settings(current_user.id)
            secret = await get_delivery_secret(current_user.id)
            if not (
                settings["outbound_webhook_enabled"]
                and settings["outbound_webhook_url"]
                and secret
            ):
                raise RuntimeError("Outbound webhook is not fully configured")
            delivery_result = await WebhookChannelAdapter(
                settings["outbound_webhook_url"],
                secret,
            ).send(lead_data, message, idempotency_key)
    except Exception as exc:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """UPDATE marketing_messages
                       SET status = 'failed', provider = $1, last_error = $2,
                           updated_at = CURRENT_TIMESTAMP
                       WHERE id = $3 AND user_id = $4""",
                    selected_provider,
                    str(exc)[:2000],
                    message_id,
                    current_user.id,
                )
                await _record_event(
                    conn,
                    message_id,
                    current_user.id,
                    "failed",
                    current_user.id,
                    {"provider": selected_provider, "error": str(exc)[:2000]},
                )
                failed = await _owned_message(conn, message_id, current_user.id)
        raise HTTPException(
            status_code=502,
            detail={"message": "Message delivery failed", "error": str(exc), "status": _message_response(failed).model_dump(mode="json")},
        ) from exc

    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """UPDATE marketing_messages
                   SET status = 'sent', provider = $1, provider_message_id = $2,
                       sent_at = CURRENT_TIMESTAMP, last_error = NULL,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = $3 AND user_id = $4""",
                delivery_result["provider"],
                delivery_result["provider_message_id"],
                message_id,
                current_user.id,
            )
            await _record_event(
                conn,
                message_id,
                current_user.id,
                "sent",
                current_user.id,
                delivery_result,
            )
            sent = await _owned_message(conn, message_id, current_user.id)
    return _message_response(sent)


@router.post(
    "/messages/{message_id}/follow-ups",
    response_model=FollowUpSequenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_follow_up_sequence(
    message_id: int,
    request: FollowUpSequenceRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    delays = request.delays_hours
    if any(delay < 1 or delay > 24 * 90 for delay in delays):
        raise HTTPException(status_code=400, detail="Follow-up delays must be between 1 hour and 90 days")
    if delays != sorted(set(delays)):
        raise HTTPException(status_code=400, detail="Follow-up delays must be unique and ascending")

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            source = await _owned_message(conn, message_id, current_user.id, for_update=True)
            if not source:
                raise HTTPException(status_code=404, detail="Message not found")
            if source["status"] != "sent":
                raise HTTPException(status_code=409, detail="Send the initial message before starting follow-ups")
            if source["follow_up_sequence_id"] is not None:
                raise HTTPException(status_code=409, detail="A follow-up message cannot start another sequence")
            existing = await conn.fetchval(
                """SELECT id FROM follow_up_sequences
                   WHERE source_message_id = $1 AND user_id = $2 AND status = 'active'""",
                message_id,
                current_user.id,
            )
            if existing:
                raise HTTPException(status_code=409, detail="An active follow-up sequence already exists")

            sequence_id = await conn.fetchval(
                """INSERT INTO follow_up_sequences
                   (user_id, lead_id, source_message_id, channel, stop_on_reply)
                   VALUES ($1, $2, $3, $4, $5)
                   RETURNING id""",
                current_user.id,
                source["lead_id"],
                message_id,
                source["channel"],
                request.stop_on_reply,
            )
            await conn.execute(
                """UPDATE marketing_messages
                   SET follow_up_sequence_id = $1, updated_at = CURRENT_TIMESTAMP
                   WHERE id = $2 AND user_id = $3""",
                sequence_id,
                message_id,
                current_user.id,
            )
            evidence = _json_value(source["personalization_evidence"], [])
            message_ids: list[int] = []
            for step, delay in enumerate(delays, start=1):
                copy = build_follow_up_copy(dict(source), step, request.language)
                quality_score, risk_flags = validate_message(
                    {
                        "channel": source["channel"],
                        "subject": copy["subject"],
                        "body": copy["body"],
                        "cta": copy["cta"],
                    },
                    evidence,
                )
                blocking_flags = {
                    "unsupported_channel",
                    "empty_body",
                    "channel_length_exceeded",
                    "unsupported_guarantee",
                    "invented_discount",
                    "forbidden_greeting",
                    "upfront_pricing",
                }
                if blocking_flags.intersection(risk_flags):
                    raise HTTPException(
                        status_code=409,
                        detail={"message": "Generated follow-up failed quality review", "risk_flags": risk_flags},
                    )
                follow_up_id = await conn.fetchval(
                    """INSERT INTO marketing_messages
                       (lead_id, user_id, campaign_id, channel, subject, body, cta,
                        sequence_step, status, personalization_evidence,
                        quality_score, risk_flags, generation_provider,
                        generation_model, approved_by, approved_at, scheduled_at,
                        idempotency_key, follow_up_sequence_id, updated_at)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'scheduled',
                               $9::jsonb, $10, $11::jsonb, 'follow_up',
                               'follow-up-v1', $2, CURRENT_TIMESTAMP,
                               CURRENT_TIMESTAMP + ($12 * INTERVAL '1 hour'),
                               $13, $14, CURRENT_TIMESTAMP)
                       RETURNING id""",
                    source["lead_id"],
                    current_user.id,
                    source["campaign_id"],
                    source["channel"],
                    copy["subject"],
                    copy["body"],
                    copy["cta"],
                    step + 1,
                    json.dumps(evidence, ensure_ascii=False),
                    quality_score,
                    json.dumps(risk_flags, ensure_ascii=False),
                    delay,
                    f"follow-up-sequence-{sequence_id}-step-{step}",
                    sequence_id,
                )
                message_ids.append(follow_up_id)
                await _record_event(
                    conn,
                    follow_up_id,
                    current_user.id,
                    "follow_up_scheduled",
                    current_user.id,
                    {"sequence_id": sequence_id, "delay_hours": delay, "step": step},
                )
            await _record_event(
                conn,
                message_id,
                current_user.id,
                "follow_up_sequence_started",
                current_user.id,
                {"sequence_id": sequence_id, "message_ids": message_ids},
            )
    return FollowUpSequenceResponse(
        id=sequence_id,
        source_message_id=message_id,
        lead_id=source["lead_id"],
        channel=source["channel"],
        status="active",
        stop_on_reply=request.stop_on_reply,
        message_ids=message_ids,
    )


@router.post("/follow-ups/{sequence_id}/stop", response_model=FollowUpSequenceResponse)
async def stop_follow_up_sequence(
    sequence_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            sequence = await conn.fetchrow(
                """UPDATE follow_up_sequences
                   SET status = 'stopped', stopped_at = CURRENT_TIMESTAMP,
                       stop_reason = 'manual', updated_at = CURRENT_TIMESTAMP
                   WHERE id = $1 AND user_id = $2 AND status = 'active'
                   RETURNING id, source_message_id, lead_id, channel,
                             status, stop_on_reply""",
                sequence_id,
                current_user.id,
            )
            if not sequence:
                raise HTTPException(status_code=404, detail="Active follow-up sequence not found")
            cancelled = await conn.fetch(
                """UPDATE marketing_messages
                   SET status = 'cancelled', last_error = 'Follow-up stopped manually',
                       updated_at = CURRENT_TIMESTAMP
                   WHERE follow_up_sequence_id = $1 AND user_id = $2
                     AND status IN ('scheduled', 'scheduling', 'queued', 'approved')
                   RETURNING id, delivery_task_id""",
                sequence_id,
                current_user.id,
            )
            task_ids = [row["delivery_task_id"] for row in cancelled if row["delivery_task_id"]]
            if task_ids:
                await conn.execute(
                    """UPDATE tasks
                       SET status = 'cancelled', completed_at = CURRENT_TIMESTAMP,
                           error = 'Follow-up stopped manually'
                       WHERE user_id = $1 AND id = ANY($2::int[])
                         AND status IN ('pending', 'running')""",
                    current_user.id,
                    task_ids,
                )
            for row in cancelled:
                await _record_event(
                    conn,
                    row["id"],
                    current_user.id,
                    "follow_up_cancelled",
                    current_user.id,
                    {"sequence_id": sequence_id, "reason": "manual"},
                )
            message_ids = await conn.fetch(
                """SELECT id FROM marketing_messages
                   WHERE follow_up_sequence_id = $1 AND user_id = $2
                   ORDER BY sequence_step""",
                sequence_id,
                current_user.id,
            )
    return FollowUpSequenceResponse(
        **dict(sequence),
        message_ids=[row["id"] for row in message_ids],
    )


@router.get("/messages/{message_id}/events", response_model=list[ChatMessageEventResponse])
async def message_events(
    message_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        owned = await conn.fetchval(
            "SELECT 1 FROM marketing_messages WHERE id = $1 AND user_id = $2",
            message_id,
            current_user.id,
        )
        if not owned:
            raise HTTPException(status_code=404, detail="Message not found")
        rows = await conn.fetch(
            """SELECT id, event_type, actor_id, payload, created_at
               FROM marketing_message_events
               WHERE message_id = $1 AND user_id = $2
               ORDER BY created_at, id""",
            message_id,
            current_user.id,
        )
    return [
        ChatMessageEventResponse(
            **{**dict(row), "payload": _json_value(row["payload"], {})}
        )
        for row in rows
    ]
