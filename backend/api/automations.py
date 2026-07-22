import json
import ipaddress
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from automation.engine import SUPPORTED_TRIGGER_TYPES, as_dict, validate_definition
from automation.delivery import enqueue_delivery
from automation.providers import DEFAULT_MODEL, automation_ai_provider
from automation.settings import (
    encrypt_secret,
    get_automation_settings,
)
from .auth import UserResponse, get_current_user, get_db_pool

router = APIRouter()


class FlowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    trigger_type: str = "inbound_message"
    trigger_config: Dict[str, Any] = Field(default_factory=dict)
    definition: Dict[str, Any] = Field(default_factory=lambda: {"steps": []})
    status: Literal["draft", "active", "paused"] = "draft"


class FlowUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    trigger_type: Optional[str] = None
    trigger_config: Optional[Dict[str, Any]] = None
    definition: Optional[Dict[str, Any]] = None
    status: Optional[Literal["draft", "active", "paused"]] = None


class FlowResponse(BaseModel):
    id: int
    name: str
    description: str
    trigger_type: str
    trigger_config: Dict[str, Any]
    definition: Dict[str, Any]
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class FlowListResponse(BaseModel):
    flows: List[FlowResponse]
    total: int


class RunResponse(BaseModel):
    id: int
    flow_id: int
    flow_name: str
    status: str
    conversation_id: Optional[int]
    lead_id: Optional[int]
    current_step: int
    error: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    parent_run_id: Optional[int] = None


class RunStepResponse(BaseModel):
    id: int
    step_index: int
    step_type: str
    status: str
    input: Dict[str, Any]
    output: Dict[str, Any]
    error: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]


class RunDetailResponse(RunResponse):
    context: Dict[str, Any]
    steps: List[RunStepResponse]


class AutomationSummary(BaseModel):
    total_runs: int
    completed_runs: int
    failed_runs: int
    waiting_runs: int
    suppressed_runs: int
    success_rate: float
    automated_messages: int
    human_handoffs: int
    average_lead_score: float


class DailyRunMetric(BaseModel):
    date: str
    total: int
    completed: int
    failed: int


class FlowMetric(BaseModel):
    flow_id: int
    flow_name: str
    total: int
    completed: int
    failed: int
    success_rate: float


class IntentMetric(BaseModel):
    intent: str
    count: int


class AutomationAnalyticsResponse(BaseModel):
    days: int
    summary: AutomationSummary
    daily_runs: List[DailyRunMetric]
    flow_performance: List[FlowMetric]
    intent_distribution: List[IntentMetric]


class AutomationSettingsUpdate(BaseModel):
    ai_provider: Literal["local", "hybrid", "openrouter"] = "hybrid"
    ai_model: str = Field(default="", max_length=255)
    reply_mode: Literal["draft", "review", "automatic"] = "review"
    min_confidence: float = Field(default=0.65, ge=0, le=1)
    handoff_score: int = Field(default=85, ge=0, le=100)
    max_auto_replies_per_hour: int = Field(default=5, ge=1, le=100)
    blocked_terms: List[str] = Field(default_factory=list, max_length=100)
    outbound_webhook_enabled: bool = False
    outbound_webhook_url: str = Field(default="", max_length=2000)
    outbound_webhook_secret: Optional[str] = Field(default=None, max_length=500)


class AutomationSettingsResponse(BaseModel):
    ai_provider: str
    ai_model: str
    reply_mode: str
    min_confidence: float
    handoff_score: int
    max_auto_replies_per_hour: int
    blocked_terms: List[str]
    outbound_webhook_enabled: bool
    outbound_webhook_url: str
    webhook_secret_configured: bool
    openrouter_configured: bool
    default_model: str


class AICallResponse(BaseModel):
    id: int
    run_id: Optional[int]
    conversation_id: Optional[int]
    provider: str
    model: str
    status: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    output: Dict[str, Any]
    error: Optional[str]
    created_at: datetime


class DeliveryResponse(BaseModel):
    id: int
    message_id: int
    callback_url: str
    status: str
    attempts: int
    response_status: Optional[int]
    error: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]


def _validate_callback_url(value: str) -> str:
    url = value.strip()
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=400, detail="Outbound webhook URL must be HTTP or HTTPS")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="Webhook URL cannot contain credentials")
    hostname = parsed.hostname.lower()
    if parsed.scheme == "http" and hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise HTTPException(status_code=400, detail="Non-local webhook URLs must use HTTPS")
    try:
        address = ipaddress.ip_address(hostname)
        if address.is_link_local or address.is_multicast or address.is_unspecified:
            raise HTTPException(status_code=400, detail="Webhook URL address is not allowed")
    except ValueError:
        pass
    return url


def _validate_flow(
    trigger_type: str,
    definition: Dict[str, Any],
    trigger_config: Optional[Dict[str, Any]] = None,
) -> None:
    if trigger_type not in SUPPORTED_TRIGGER_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported trigger type: {trigger_type}")
    config = trigger_config or {}
    channel = config.get("channel")
    if channel is not None and (not isinstance(channel, str) or not channel.strip() or len(channel) > 50):
        raise HTTPException(status_code=400, detail="trigger_config.channel must be 1-50 characters")
    keywords = config.get("keywords", [])
    if not isinstance(keywords, list):
        raise HTTPException(status_code=400, detail="trigger_config.keywords must be a list")
    if len(keywords) > 50 or any(
        not isinstance(keyword, str) or not keyword.strip() or len(keyword) > 100
        for keyword in keywords
    ):
        raise HTTPException(
            status_code=400,
            detail="trigger_config.keywords supports up to 50 non-empty strings of 100 characters",
        )
    if config.get("keyword_match", "any") not in {"any", "all"}:
        raise HTTPException(status_code=400, detail="trigger_config.keyword_match must be any or all")
    try:
        validate_definition(definition)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _to_flow_response(row) -> FlowResponse:
    data = dict(row)
    data["trigger_config"] = as_dict(data.get("trigger_config"))
    data["definition"] = as_dict(data.get("definition"), {"steps": []})
    return FlowResponse(**data)


@router.get("/", response_model=FlowListResponse)
async def list_flows(current_user: UserResponse = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, name, COALESCE(description, '') AS description, trigger_type,
                      trigger_config, definition, status, version, created_at, updated_at
               FROM automation_flows
               WHERE user_id = $1 AND status <> 'archived'
               ORDER BY updated_at DESC, id DESC""",
            current_user.id,
        )
    flows = [_to_flow_response(row) for row in rows]
    return FlowListResponse(flows=flows, total=len(flows))


@router.post("/", response_model=FlowResponse, status_code=status.HTTP_201_CREATED)
async def create_flow(
    request: FlowCreate,
    current_user: UserResponse = Depends(get_current_user),
):
    if not request.name.strip():
        raise HTTPException(status_code=400, detail="Flow name cannot be blank")
    _validate_flow(request.trigger_type, request.definition, request.trigger_config)
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO automation_flows
               (user_id, name, description, trigger_type, trigger_config, definition, status)
               VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7)
               RETURNING id, name, description, trigger_type, trigger_config, definition,
                         status, version, created_at, updated_at""",
            current_user.id,
            request.name,
            request.description,
            request.trigger_type,
            json.dumps(request.trigger_config, ensure_ascii=False),
            json.dumps(request.definition, ensure_ascii=False),
            request.status,
        )
    return _to_flow_response(row)


@router.post("/templates/welcome", response_model=FlowResponse, status_code=status.HTTP_201_CREATED)
async def create_welcome_template(current_user: UserResponse = Depends(get_current_user)):
    request = FlowCreate(
        name="Webhook welcome and qualification",
        description="Reply to a new inbound message, tag the lead, and mark it qualified.",
        trigger_type="inbound_message",
        trigger_config={"channel": "webhook", "keywords": [], "keyword_match": "any"},
        definition={
            "steps": [
                {
                    "type": "send_message",
                    "config": {
                        "content": "Hi {{contact.name}}, thanks for reaching out. We received: {{message.content}}"
                    },
                },
                {"type": "add_tag", "config": {"tag": "webhook-inbound"}},
                {"type": "update_lead_status", "config": {"status": "qualified"}},
                {"type": "end", "config": {}},
            ]
        },
        status="active",
    )
    return await create_flow(request, current_user)


@router.post("/templates/ai-qualification", response_model=FlowResponse, status_code=status.HTTP_201_CREATED)
async def create_ai_qualification_template(current_user: UserResponse = Depends(get_current_user)):
    request = FlowCreate(
        name="AI intent qualification and handoff",
        description="Score inbound intent, generate a contextual reply, and hand high-intent contacts to a human.",
        trigger_type="inbound_message",
        trigger_config={"channel": "webhook", "keywords": [], "keyword_match": "any"},
        definition={
            "steps": [
                {"type": "analyze_intent", "config": {}},
                {"type": "smart_reply", "config": {"language": "auto"}},
                {"type": "add_tag", "config": {"tag": "ai-qualified"}},
                {
                    "type": "handoff",
                    "config": {
                        "only_if_recommended": True,
                        "reason": "{{intelligence.handoff_reason}}",
                    },
                },
                {"type": "end", "config": {}},
            ]
        },
        status="active",
    )
    return await create_flow(request, current_user)


@router.get("/settings", response_model=AutomationSettingsResponse)
async def get_settings(current_user: UserResponse = Depends(get_current_user)):
    settings = await get_automation_settings(current_user.id)
    return AutomationSettingsResponse(
        **settings,
        openrouter_configured=automation_ai_provider.configured,
        default_model=DEFAULT_MODEL,
    )


@router.put("/settings", response_model=AutomationSettingsResponse)
async def update_settings(
    request: AutomationSettingsUpdate,
    current_user: UserResponse = Depends(get_current_user),
):
    terms = list(dict.fromkeys(term.strip() for term in request.blocked_terms if term.strip()))
    if len(terms) > 100 or any(len(term) > 100 for term in terms):
        raise HTTPException(status_code=400, detail="Blocked terms must be at most 100 items of 100 characters")
    callback_url = _validate_callback_url(request.outbound_webhook_url)
    if request.outbound_webhook_enabled and not callback_url:
        raise HTTPException(status_code=400, detail="Enable outbound webhook only after configuring its URL")
    if request.ai_provider == "openrouter" and not automation_ai_provider.configured:
        raise HTTPException(status_code=409, detail="OPENROUTER_API_KEY is not configured")

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        existing_secret = await conn.fetchval(
            "SELECT outbound_webhook_secret FROM automation_settings WHERE user_id = $1",
            current_user.id,
        )
        encrypted_secret = (
            encrypt_secret(request.outbound_webhook_secret.strip())
            if request.outbound_webhook_secret is not None
            else existing_secret
        )
        if request.outbound_webhook_enabled and not encrypted_secret:
            raise HTTPException(status_code=400, detail="Outbound webhook secret is required")
        await conn.execute(
            """INSERT INTO automation_settings
               (user_id, ai_provider, ai_model, reply_mode, min_confidence,
                handoff_score, max_auto_replies_per_hour, blocked_terms,
                outbound_webhook_enabled, outbound_webhook_url,
                outbound_webhook_secret)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
               ON CONFLICT (user_id)
               DO UPDATE SET
                   ai_provider = EXCLUDED.ai_provider,
                   ai_model = EXCLUDED.ai_model,
                   reply_mode = EXCLUDED.reply_mode,
                   min_confidence = EXCLUDED.min_confidence,
                   handoff_score = EXCLUDED.handoff_score,
                   max_auto_replies_per_hour = EXCLUDED.max_auto_replies_per_hour,
                   blocked_terms = EXCLUDED.blocked_terms,
                   outbound_webhook_enabled = EXCLUDED.outbound_webhook_enabled,
                   outbound_webhook_url = EXCLUDED.outbound_webhook_url,
                   outbound_webhook_secret = EXCLUDED.outbound_webhook_secret,
                   updated_at = CURRENT_TIMESTAMP""",
            current_user.id,
            request.ai_provider,
            request.ai_model.strip(),
            request.reply_mode,
            request.min_confidence,
            request.handoff_score,
            request.max_auto_replies_per_hour,
            terms,
            request.outbound_webhook_enabled,
            callback_url,
            encrypted_secret,
        )
    return await get_settings(current_user)


@router.get("/ai-calls/recent", response_model=List[AICallResponse])
async def recent_ai_calls(
    limit: int = Query(20, ge=1, le=100),
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, run_id, conversation_id, provider, model, status,
                      prompt_tokens, completion_tokens, latency_ms, output,
                      error, created_at
               FROM automation_ai_calls
               WHERE user_id = $1
               ORDER BY created_at DESC, id DESC
               LIMIT $2""",
            current_user.id,
            limit,
        )
    return [
        AICallResponse(**{**dict(row), "output": as_dict(row["output"])})
        for row in rows
    ]


@router.get("/deliveries/recent", response_model=List[DeliveryResponse])
async def recent_deliveries(
    limit: int = Query(20, ge=1, le=100),
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, message_id, callback_url, status, attempts,
                      response_status, error, created_at, completed_at
               FROM outbound_deliveries
               WHERE user_id = $1
               ORDER BY created_at DESC, id DESC
               LIMIT $2""",
            current_user.id,
            limit,
        )
    return [DeliveryResponse(**dict(row)) for row in rows]


@router.post("/messages/{message_id}/approve", response_model=DeliveryResponse)
async def approve_message(
    message_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    settings = await get_automation_settings(current_user.id)
    if not (
        settings["outbound_webhook_enabled"]
        and settings["outbound_webhook_url"]
        and settings["webhook_secret_configured"]
    ):
        raise HTTPException(status_code=409, detail="Outbound webhook is not fully configured")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT m.id, m.content, m.metadata, m.conversation_id,
                      c.external_id, c.metadata AS conversation_metadata
               FROM conversation_messages m
               JOIN conversations c ON c.id = m.conversation_id AND c.user_id = m.user_id
               WHERE m.id = $1 AND m.user_id = $2
                 AND m.direction = 'outbound'
                 AND m.status IN ('draft', 'pending_review', 'failed')""",
            message_id,
            current_user.id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Reviewable message not found")
        await conn.execute(
            "UPDATE conversation_messages SET status = 'queued' WHERE id = $1",
            message_id,
        )
    metadata = as_dict(row["metadata"])
    conversation_metadata = as_dict(row["conversation_metadata"])
    delivery_id = await enqueue_delivery(
        current_user.id,
        message_id,
        settings["outbound_webhook_url"],
        {
            "event": "automation.message.approved",
            "message_id": message_id,
            "conversation_id": row["conversation_id"],
            "external_id": row["external_id"],
            "contact_name": conversation_metadata.get("contact_name"),
            "content": row["content"],
            "run_id": metadata.get("run_id"),
            "step_index": metadata.get("step_index"),
        },
    )
    async with pool.acquire() as conn:
        delivery = await conn.fetchrow(
            """SELECT id, message_id, callback_url, status, attempts,
                      response_status, error, created_at, completed_at
               FROM outbound_deliveries
               WHERE id = $1 AND user_id = $2""",
            delivery_id,
            current_user.id,
        )
    return DeliveryResponse(**dict(delivery))


@router.post("/deliveries/{delivery_id}/retry", response_model=DeliveryResponse)
async def retry_delivery(
    delivery_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """UPDATE outbound_deliveries
               SET status = 'pending', attempts = 0, next_attempt_at = CURRENT_TIMESTAMP,
                   locked_at = NULL, error = NULL, completed_at = NULL
               WHERE id = $1 AND user_id = $2 AND status = 'failed'
               RETURNING id, message_id, callback_url, status, attempts,
                         response_status, error, created_at, completed_at""",
            delivery_id,
            current_user.id,
        )
        if not row:
            raise HTTPException(status_code=409, detail="Only failed deliveries can be retried")
        await conn.execute(
            "UPDATE conversation_messages SET status = 'queued' WHERE id = $1",
            row["message_id"],
        )
    return DeliveryResponse(**dict(row))


@router.patch("/{flow_id}", response_model=FlowResponse)
async def update_flow(
    flow_id: int,
    request: FlowUpdate,
    current_user: UserResponse = Depends(get_current_user),
):
    changes = request.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No automation flow changes supplied")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            """SELECT trigger_type, trigger_config, definition
               FROM automation_flows
               WHERE id = $1 AND user_id = $2 AND status <> 'archived'""",
            flow_id,
            current_user.id,
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Automation flow not found")

        trigger_type = (
            request.trigger_type
            if request.trigger_type is not None
            else existing["trigger_type"]
        )
        trigger_config = (
            request.trigger_config
            if request.trigger_config is not None
            else as_dict(existing["trigger_config"])
        )
        definition = (
            request.definition
            if request.definition is not None
            else as_dict(existing["definition"], {"steps": []})
        )
        if request.name is not None and not request.name.strip():
            raise HTTPException(status_code=400, detail="Flow name cannot be blank")
        _validate_flow(trigger_type, definition, trigger_config)

        updates, values = [], []
        for field, value in changes.items():
            values.append(value)
            placeholder = f"${len(values)}"
            if field in {"trigger_config", "definition"}:
                values[-1] = json.dumps(value, ensure_ascii=False)
                placeholder += "::jsonb"
            updates.append(f"{field} = {placeholder}")
        updates.extend(["version = version + 1", "updated_at = CURRENT_TIMESTAMP"])
        values.extend([flow_id, current_user.id])
        row = await conn.fetchrow(
            f"""UPDATE automation_flows
                SET {", ".join(updates)}
                WHERE id = ${len(values) - 1} AND user_id = ${len(values)}
                RETURNING id, name, description, trigger_type, trigger_config, definition,
                          status, version, created_at, updated_at""",
            *values,
        )
    return _to_flow_response(row)


@router.delete("/{flow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow(
    flow_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            archived = await conn.fetchval(
                """UPDATE automation_flows
                   SET status = 'archived', updated_at = CURRENT_TIMESTAMP
                   WHERE id = $1 AND user_id = $2 AND status <> 'archived'
                   RETURNING id""",
                flow_id,
                current_user.id,
            )
            if not archived:
                raise HTTPException(status_code=404, detail="Automation flow not found")
            await conn.execute(
                """UPDATE automation_jobs j
                   SET status = 'cancelled', completed_at = CURRENT_TIMESTAMP
                   FROM automation_runs r
                   WHERE j.run_id = r.id
                     AND r.flow_id = $1
                     AND r.user_id = $2
                     AND j.status IN ('pending', 'running')""",
                flow_id,
                current_user.id,
            )
            await conn.execute(
                """UPDATE automation_runs
                   SET status = 'cancelled', completed_at = CURRENT_TIMESTAMP,
                       error = 'Flow archived before execution completed'
                   WHERE flow_id = $1 AND user_id = $2
                     AND status IN ('running', 'waiting')""",
                flow_id,
                current_user.id,
            )
    return None


@router.get("/runs/recent", response_model=List[RunResponse])
async def recent_runs(
    limit: int = Query(20, ge=1, le=100),
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT r.id, r.flow_id, f.name AS flow_name, r.status, r.conversation_id,
                      r.lead_id, r.current_step, r.error, r.started_at, r.completed_at
                      , r.parent_run_id
               FROM automation_runs r
               JOIN automation_flows f ON f.id = r.flow_id
               WHERE r.user_id = $1
               ORDER BY r.started_at DESC, r.id DESC
               LIMIT $2""",
            current_user.id,
            limit,
        )
    return [RunResponse(**dict(row)) for row in rows]


@router.get("/analytics", response_model=AutomationAnalyticsResponse)
async def automation_analytics(
    days: int = Query(30, ge=1, le=365),
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        summary_row = await conn.fetchrow(
            """SELECT COUNT(*) AS total_runs,
                      COUNT(*) FILTER (WHERE status = 'completed') AS completed_runs,
                      COUNT(*) FILTER (WHERE status = 'failed') AS failed_runs,
                      COUNT(*) FILTER (WHERE status = 'waiting') AS waiting_runs,
                      COUNT(*) FILTER (WHERE status = 'suppressed') AS suppressed_runs
               FROM automation_runs
               WHERE user_id = $1
                 AND started_at >= CURRENT_TIMESTAMP - ($2 * INTERVAL '1 day')""",
            current_user.id,
            days,
        )
        automated_messages = await conn.fetchval(
            """SELECT COUNT(*)
               FROM conversation_messages
               WHERE user_id = $1
                 AND direction = 'outbound'
                 AND metadata->>'source' = 'automation'
                 AND created_at >= CURRENT_TIMESTAMP - ($2 * INTERVAL '1 day')""",
            current_user.id,
            days,
        )
        human_handoffs = await conn.fetchval(
            """SELECT COUNT(*)
               FROM conversation_events
               WHERE user_id = $1
                 AND event_type IN ('handoff_requested', 'human_takeover')
                 AND created_at >= CURRENT_TIMESTAMP - ($2 * INTERVAL '1 day')""",
            current_user.id,
            days,
        )
        average_lead_score = await conn.fetchval(
            """SELECT COALESCE(AVG(quality_score), 0)
               FROM leads
               WHERE user_id = $1
                 AND created_at >= CURRENT_TIMESTAMP - ($2 * INTERVAL '1 day')""",
            current_user.id,
            days,
        )
        daily_rows = await conn.fetch(
            """SELECT started_at::date AS date,
                      COUNT(*) AS total,
                      COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                      COUNT(*) FILTER (WHERE status = 'failed') AS failed
               FROM automation_runs
               WHERE user_id = $1
                 AND started_at >= CURRENT_TIMESTAMP - ($2 * INTERVAL '1 day')
               GROUP BY started_at::date
               ORDER BY started_at::date""",
            current_user.id,
            days,
        )
        flow_rows = await conn.fetch(
            """SELECT f.id AS flow_id, f.name AS flow_name, COUNT(r.id) AS total,
                      COUNT(r.id) FILTER (WHERE r.status = 'completed') AS completed,
                      COUNT(r.id) FILTER (WHERE r.status = 'failed') AS failed
               FROM automation_flows f
               LEFT JOIN automation_runs r
                 ON r.flow_id = f.id
                AND r.started_at >= CURRENT_TIMESTAMP - ($2 * INTERVAL '1 day')
               WHERE f.user_id = $1
               GROUP BY f.id, f.name
               ORDER BY COUNT(r.id) DESC, f.id""",
            current_user.id,
            days,
        )
        intent_rows = await conn.fetch(
            """SELECT COALESCE(intent, 'unknown') AS intent, COUNT(*) AS count
               FROM conversations
               WHERE user_id = $1
                 AND updated_at >= CURRENT_TIMESTAMP - ($2 * INTERVAL '1 day')
               GROUP BY COALESCE(intent, 'unknown')
               ORDER BY COUNT(*) DESC""",
            current_user.id,
            days,
        )

    total_runs = summary_row["total_runs"] or 0
    completed_runs = summary_row["completed_runs"] or 0
    failed_runs = summary_row["failed_runs"] or 0
    attempted_runs = completed_runs + failed_runs
    summary = AutomationSummary(
        total_runs=total_runs,
        completed_runs=completed_runs,
        failed_runs=failed_runs,
        waiting_runs=summary_row["waiting_runs"] or 0,
        suppressed_runs=summary_row["suppressed_runs"] or 0,
        success_rate=round(completed_runs / attempted_runs * 100, 2) if attempted_runs else 0,
        automated_messages=automated_messages or 0,
        human_handoffs=human_handoffs or 0,
        average_lead_score=round(float(average_lead_score or 0), 2),
    )
    flow_metrics = []
    for row in flow_rows:
        item = dict(row)
        item["success_rate"] = (
            round(item["completed"] / item["total"] * 100, 2) if item["total"] else 0
        )
        flow_metrics.append(FlowMetric(**item))
    return AutomationAnalyticsResponse(
        days=days,
        summary=summary,
        daily_runs=[
            DailyRunMetric(
                date=row["date"].isoformat(),
                total=row["total"],
                completed=row["completed"],
                failed=row["failed"],
            )
            for row in daily_rows
        ],
        flow_performance=flow_metrics,
        intent_distribution=[IntentMetric(**dict(row)) for row in intent_rows],
    )


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
async def get_run_detail(
    run_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT r.id, r.flow_id, f.name AS flow_name, r.status, r.conversation_id,
                      r.lead_id, r.current_step, r.error, r.started_at, r.completed_at,
                      r.parent_run_id, r.context
               FROM automation_runs r
               JOIN automation_flows f ON f.id = r.flow_id
               WHERE r.id = $1 AND r.user_id = $2""",
            run_id,
            current_user.id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Automation run not found")
        step_rows = await conn.fetch(
            """SELECT id, step_index, step_type, status, input, output, error,
                      started_at, completed_at
               FROM automation_run_steps
               WHERE run_id = $1
               ORDER BY step_index, id""",
            run_id,
        )
    data = dict(row)
    data["context"] = as_dict(data["context"])
    data["steps"] = [
        RunStepResponse(
            **{
                **dict(step),
                "input": as_dict(step["input"]),
                "output": as_dict(step["output"]),
            }
        )
        for step in step_rows
    ]
    return RunDetailResponse(**data)


@router.post("/runs/{run_id}/retry", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def retry_run(
    run_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    from automation.engine import AutomationEngine

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT r.id, r.flow_id, r.event_id, r.conversation_id, r.lead_id,
                      r.context, r.status, f.name, f.user_id, f.trigger_type,
                      f.trigger_config, f.definition
               FROM automation_runs r
               JOIN automation_flows f ON f.id = r.flow_id
               WHERE r.id = $1 AND r.user_id = $2""",
            run_id,
            current_user.id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Automation run not found")
        if row["status"] != "failed":
            raise HTTPException(status_code=409, detail="Only failed runs can be retried")
        if row["conversation_id"] is not None:
            conversation_mode = await conn.fetchval(
                "SELECT mode FROM conversations WHERE id = $1 AND user_id = $2",
                row["conversation_id"],
                current_user.id,
            )
            if conversation_mode == "human":
                raise HTTPException(
                    status_code=409,
                    detail="Release the human-owned conversation before retrying automation",
                )
        failed_step = await conn.fetchval(
            """SELECT MIN(step_index)
               FROM automation_run_steps
               WHERE run_id = $1 AND status = 'failed'""",
            run_id,
        )

    data = dict(row)
    flow = {
        "id": data["flow_id"],
        "user_id": data["user_id"],
        "name": data["name"],
        "trigger_type": data["trigger_type"],
        "trigger_config": as_dict(data["trigger_config"]),
        "definition": as_dict(data["definition"], {"steps": []}),
    }
    context = as_dict(data["context"])
    new_run_id = await AutomationEngine().execute_flow(
        flow=flow,
        event=context.get("event") or {},
        event_row_id=data["event_id"],
        conversation_id=data["conversation_id"],
        lead_id=data["lead_id"],
        start_step=int(failed_step or 0),
        context=context,
        parent_run_id=run_id,
    )
    async with pool.acquire() as conn:
        new_row = await conn.fetchrow(
            """SELECT r.id, r.flow_id, f.name AS flow_name, r.status, r.conversation_id,
                      r.lead_id, r.current_step, r.error, r.started_at, r.completed_at,
                      r.parent_run_id
               FROM automation_runs r
               JOIN automation_flows f ON f.id = r.flow_id
               WHERE r.id = $1 AND r.user_id = $2""",
            new_run_id,
            current_user.id,
        )
    return RunResponse(**dict(new_row))
