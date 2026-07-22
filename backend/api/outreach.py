import json
from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .auth import UserResponse, get_current_user, get_db_pool

router = APIRouter()


class MarketingMessageResponse(BaseModel):
    id: int
    lead_id: Optional[int]
    channel: str
    subject: str
    body: str
    cta: str
    sequence_step: int
    status: str
    personalization_evidence: List[str] = Field(default_factory=list)
    quality_score: int = 0
    risk_flags: List[str] = Field(default_factory=list)
    approved_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    provider: Optional[str] = None
    attempts: int = 0
    last_error: Optional[str] = None
    delivery_task_id: Optional[int] = None
    follow_up_sequence_id: Optional[int] = None
    template_version_id: Optional[int] = None
    ab_experiment_id: Optional[int] = None
    ab_variant_id: Optional[int] = None
    estimated_cost_usd: float = 0
    created_at: datetime


class MarketingMessageListResponse(BaseModel):
    messages: List[MarketingMessageResponse]
    total: int


class MarketingMessageUpdate(BaseModel):
    status: Literal["draft", "approved", "sent", "archived"]


class MarketingCampaignResponse(BaseModel):
    id: int
    name: str
    product_context: str
    lead_count: int
    generation_mode: str
    total_messages: int
    draft_messages: int
    approved_messages: int
    sent_messages: int
    archived_messages: int
    status: Literal["queued", "running", "done"]
    progress: int
    created_at: datetime
    updated_at: datetime


class MarketingCampaignListResponse(BaseModel):
    campaigns: List[MarketingCampaignResponse]
    total: int


class OutreachReviewItem(BaseModel):
    id: int
    campaign_id: Optional[int]
    campaign_name: str
    lead_id: int
    lead_name: str
    lead_email: Optional[str]
    channel: str
    subject: str
    body: str
    status: str
    quality_score: int
    risk_flags: List[str] = Field(default_factory=list)
    scheduled_at: Optional[datetime]
    sent_at: Optional[datetime]
    follow_up_sequence_id: Optional[int]
    last_error: Optional[str]
    created_at: datetime


class OutreachReviewQueueResponse(BaseModel):
    messages: List[OutreachReviewItem]
    total: int


def _to_marketing_message(row) -> MarketingMessageResponse:
    data = dict(row)
    for field in ("personalization_evidence", "risk_flags"):
        if isinstance(data.get(field), str):
            data[field] = json.loads(data[field])
    return MarketingMessageResponse(**data)


def _to_review_item(row) -> OutreachReviewItem:
    data = dict(row)
    if isinstance(data.get("risk_flags"), str):
        data["risk_flags"] = json.loads(data["risk_flags"])
    return OutreachReviewItem(**data)


@router.get("/review-queue", response_model=OutreachReviewQueueResponse)
async def get_outreach_review_queue(
    limit: int = Query(100, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),
):
    """Return outbound drafts and their delivery/follow-up lifecycle."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            """SELECT COUNT(*)
               FROM marketing_messages m
               JOIN leads l ON l.id = m.lead_id AND l.user_id = m.user_id
               WHERE m.user_id = $1 AND m.status <> 'archived'
                 AND (m.channel <> 'email' OR NULLIF(BTRIM(l.email), '') IS NOT NULL)""",
            current_user.id,
        )
        rows = await conn.fetch(
            """SELECT m.id, m.campaign_id,
                      COALESCE(c.name, 'Direct outreach') AS campaign_name,
                      m.lead_id, COALESCE(l.username, 'Unknown lead') AS lead_name,
                      l.email AS lead_email, m.channel,
                      COALESCE(m.subject, '') AS subject, m.body, m.status,
                      m.quality_score, m.risk_flags, m.scheduled_at, m.sent_at,
                      m.follow_up_sequence_id, m.last_error, m.created_at
               FROM marketing_messages m
               JOIN leads l ON l.id = m.lead_id AND l.user_id = m.user_id
               LEFT JOIN marketing_campaigns c
                 ON c.id = m.campaign_id AND c.user_id = m.user_id
               WHERE m.user_id = $1 AND m.status <> 'archived'
                 AND (m.channel <> 'email' OR NULLIF(BTRIM(l.email), '') IS NOT NULL)
               ORDER BY
                   CASE m.status
                       WHEN 'draft' THEN 0 WHEN 'failed' THEN 1
                       WHEN 'approved' THEN 2 WHEN 'sent' THEN 3 ELSE 4
                   END,
                   m.created_at DESC, m.id DESC
               LIMIT $2""",
            current_user.id,
            limit,
        )
    return OutreachReviewQueueResponse(
        messages=[_to_review_item(row) for row in rows],
        total=total,
    )


def _campaign_stage(total: int, draft: int, approved: int, sent: int, archived: int) -> tuple[str, int]:
    """Compute a product-facing campaign stage from editable draft lifecycle counts."""
    if total <= 0:
        return "queued", 0
    processed = approved + sent + archived
    if processed >= total and draft == 0:
        return "done", 100
    if processed > 0:
        return "running", min(99, round(processed / total * 100))
    return "queued", 0


@router.get("/campaigns", response_model=MarketingCampaignListResponse)
async def get_marketing_campaigns(
    limit: int = Query(10, ge=1, le=50),
    current_user: UserResponse = Depends(get_current_user),
):
    """List recent persisted marketing pipeline batches for the current user."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM marketing_campaigns WHERE user_id = $1",
            current_user.id,
        )
        rows = await conn.fetch(
            """SELECT c.id, c.name, COALESCE(c.product_context, '') AS product_context,
                      c.lead_count, c.generation_mode, c.created_at, c.updated_at,
                      COUNT(m.id)::int AS total_messages,
                      COUNT(m.id) FILTER (WHERE m.status = 'draft')::int AS draft_messages,
                      COUNT(m.id) FILTER (WHERE m.status = 'approved')::int AS approved_messages,
                      COUNT(m.id) FILTER (WHERE m.status = 'sent')::int AS sent_messages,
                      COUNT(m.id) FILTER (WHERE m.status = 'archived')::int AS archived_messages
               FROM marketing_campaigns c
               LEFT JOIN marketing_messages m
                 ON m.campaign_id = c.id AND m.user_id = c.user_id
               WHERE c.user_id = $1
               GROUP BY c.id
               ORDER BY c.created_at DESC, c.id DESC
               LIMIT $2""",
            current_user.id,
            limit,
        )
    campaigns = []
    for row in rows:
        item = dict(row)
        item["status"], item["progress"] = _campaign_stage(
            item["total_messages"],
            item["draft_messages"],
            item["approved_messages"],
            item["sent_messages"],
            item["archived_messages"],
        )
        campaigns.append(MarketingCampaignResponse(**item))
    return MarketingCampaignListResponse(campaigns=campaigns, total=total)


@router.get("/", response_model=MarketingMessageListResponse)
async def get_marketing_messages(
    lead_id: Optional[int] = Query(None, ge=1),
    status_filter: Optional[Literal[
        "draft", "approved", "scheduled", "scheduling", "queued",
        "sending", "sent", "failed", "cancelled", "archived",
    ]] = Query(None, alias="status"),
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    conditions = ["user_id = $1"]
    params = [current_user.id]
    if lead_id is not None:
        conditions.append(f"lead_id = ${len(params) + 1}")
        params.append(lead_id)
    if status_filter is not None:
        conditions.append(f"status = ${len(params) + 1}")
        params.append(status_filter)
    where_clause = " AND ".join(conditions)
    async with pool.acquire() as conn:
        total = await conn.fetchval(f"SELECT COUNT(*) FROM marketing_messages WHERE {where_clause}", *params)
        rows = await conn.fetch(
            f"""SELECT id, lead_id, channel, COALESCE(subject, '') AS subject,
                       body, COALESCE(cta, '') AS cta, sequence_step, status,
                       personalization_evidence, quality_score, risk_flags,
                       approved_at, scheduled_at, sent_at, provider, attempts, last_error,
                       delivery_task_id, follow_up_sequence_id,
                       template_version_id, ab_experiment_id, ab_variant_id,
                       estimated_cost_usd, created_at
                FROM marketing_messages
                WHERE {where_clause}
                ORDER BY created_at DESC, id DESC""",
            *params,
        )
    return MarketingMessageListResponse(
        messages=[_to_marketing_message(row) for row in rows],
        total=total,
    )


@router.patch("/{message_id}", response_model=MarketingMessageResponse)
async def update_marketing_message(
    message_id: int,
    update: MarketingMessageUpdate,
    current_user: UserResponse = Depends(get_current_user),
):
    if update.status in {"approved", "sent"}:
        raise HTTPException(
            status_code=409,
            detail="Use the Chat Agent approval and send endpoints for this transition",
        )
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """UPDATE marketing_messages
               SET status = $1
               WHERE id = $2 AND user_id = $3
               RETURNING id, lead_id, channel, COALESCE(subject, '') AS subject,
                         body, COALESCE(cta, '') AS cta, sequence_step, status,
                         personalization_evidence, quality_score, risk_flags,
                         approved_at, scheduled_at, sent_at, provider, attempts, last_error,
                         delivery_task_id, follow_up_sequence_id,
                         template_version_id, ab_experiment_id, ab_variant_id,
                         estimated_cost_usd, created_at""",
            update.status, message_id, current_user.id,
        )
        if row:
            await conn.execute(
                """UPDATE marketing_campaigns c
                   SET updated_at = CURRENT_TIMESTAMP
                   FROM marketing_messages m
                   WHERE m.id = $1 AND m.campaign_id = c.id AND c.user_id = $2""",
                message_id,
                current_user.id,
            )
    if not row:
        raise HTTPException(status_code=404, detail="Marketing message not found")
    return _to_marketing_message(row)
