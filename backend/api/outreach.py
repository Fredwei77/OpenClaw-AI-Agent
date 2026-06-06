from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

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
    status_filter: Optional[Literal["draft", "approved", "sent", "archived"]] = Query(None, alias="status"),
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
            f"""SELECT id, lead_id, channel, subject, body, cta, sequence_step, status, created_at
                FROM marketing_messages
                WHERE {where_clause}
                ORDER BY created_at DESC, id DESC""",
            *params,
        )
    return MarketingMessageListResponse(
        messages=[MarketingMessageResponse(**dict(row)) for row in rows],
        total=total,
    )


@router.patch("/{message_id}", response_model=MarketingMessageResponse)
async def update_marketing_message(
    message_id: int,
    update: MarketingMessageUpdate,
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """UPDATE marketing_messages
               SET status = $1
               WHERE id = $2 AND user_id = $3
               RETURNING id, lead_id, channel, subject, body, cta, sequence_step, status, created_at""",
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
    return MarketingMessageResponse(**dict(row))
