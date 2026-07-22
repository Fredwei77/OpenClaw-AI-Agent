from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field
from typing import Any, Optional, List
from datetime import datetime
import json
import logging
from backend.email_utils import sanitize_lead_email
from .auth import get_db_pool, get_current_user, UserResponse

logger = logging.getLogger(__name__)
MAX_REASONABLE_FOLLOWERS = 10_000_000_000

router = APIRouter()

VALID_PLATFORMS = {
    "instagram", "tiktok", "x", "facebook", "youtube", "linkedin",
    "shopify", "google", "duckduckgo", "directory",
}
VALID_LEAD_STATUSES = {"new", "contacted", "qualified", "converted", "lost"}


class LeadCreate(BaseModel):
    platform: str
    username: str = Field(..., min_length=1, max_length=255)
    profile_url: Optional[str] = None
    email: Optional[str] = None
    followers: int = Field(default=0, ge=0, le=MAX_REASONABLE_FOLLOWERS)
    tags: List[str] = Field(default_factory=list)


class LeadUpdate(BaseModel):
    platform: Optional[str] = None
    username: Optional[str] = None
    profile_url: Optional[str] = None
    email: Optional[str] = None
    followers: Optional[int] = Field(default=None, ge=0, le=MAX_REASONABLE_FOLLOWERS)
    tags: Optional[List[str]] = None
    status: Optional[str] = None


class LeadResponse(BaseModel):
    id: int
    platform: str
    username: str
    profile_url: Optional[str]
    email: Optional[str]
    followers: int
    tags: List[str]
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    quality_score: int = 0
    user_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class LeadListResponse(BaseModel):
    leads: List[LeadResponse]
    total: int
    page: int
    page_size: int


class MarketingMessageResponse(BaseModel):
    id: int
    channel: str
    subject: str
    body: str
    cta: str
    sequence_step: int
    status: str
    personalization_evidence: List[str] = Field(default_factory=list)
    quality_score: int = 0
    risk_flags: List[str] = Field(default_factory=list)
    generation_provider: str = "local"
    generation_model: str = ""
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


class LeadDetailResponse(LeadResponse):
    marketing_messages: List[MarketingMessageResponse] = Field(default_factory=list)


def _to_marketing_message(row) -> MarketingMessageResponse:
    data = dict(row)
    for field in ("personalization_evidence", "risk_flags"):
        if isinstance(data.get(field), str):
            data[field] = json.loads(data[field])
    return MarketingMessageResponse(**data)


def _to_lead_response(row) -> LeadResponse:
    metadata = row['metadata'] or {}
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    return LeadResponse(
        id=row['id'],
        platform=row['platform'],
        username=row['username'],
        profile_url=row['profile_url'],
        email=sanitize_lead_email(row['email']),
        followers=row['followers'],
        tags=row['tags'] or [],
        status=row['status'] or 'new',
        metadata=metadata,
        quality_score=row['quality_score'] or 0,
        user_id=row['user_id'],
        created_at=row['created_at'],
    )


@router.get("/", response_model=LeadListResponse)
async def get_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status_filter: Optional[str] = Query(None, alias="status"),
    platform: Optional[str] = None,
    search: Optional[str] = Query(None, max_length=255),
    min_followers: Optional[int] = Query(None, ge=0),
    max_followers: Optional[int] = Query(None, ge=0),
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get paginated list of leads with optional filters."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            conditions = []
            params = []
            param_idx = 1

            # Always filter by user_id
            conditions.append(f"user_id = ${param_idx}")
            params.append(current_user.id)
            param_idx += 1

            if status_filter:
                if status_filter not in VALID_LEAD_STATUSES:
                    raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of {VALID_LEAD_STATUSES}")
                conditions.append(f"status = ${param_idx}")
                params.append(status_filter)
                param_idx += 1

            if platform:
                if platform not in VALID_PLATFORMS:
                    raise HTTPException(status_code=400, detail=f"Invalid platform. Must be one of {VALID_PLATFORMS}")
                conditions.append(f"platform = ${param_idx}")
                params.append(platform)
                param_idx += 1

            if search:
                # Simple escape - just escape special chars for LIKE
                escaped = search.replace("%", "\\%").replace("_", "\\_")
                conditions.append(f"(username ILIKE ${param_idx} OR email ILIKE ${param_idx + 1})")
                params.append(f"%{escaped}%")
                params.append(f"%{escaped}%")
                param_idx += 2

            if min_followers is not None:
                conditions.append(f"followers >= ${param_idx}")
                params.append(min_followers)
                param_idx += 1

            if max_followers is not None:
                conditions.append(f"followers <= ${param_idx}")
                params.append(max_followers)
                param_idx += 1

            if tags:
                tag_list = [t.strip() for t in tags.split(",") if t.strip()]
                for tag in tag_list:
                    conditions.append(f"${param_idx} = ANY(tags)")
                    params.append(tag)
                    param_idx += 1

            where_clause = "WHERE " + " AND ".join(conditions)

            # Get total count
            count_query = f"SELECT COUNT(*) as count FROM leads {where_clause}"
            total = await conn.fetchval(count_query, *params)

            # Get paginated results
            offset = (page - 1) * page_size
            query = f"""
                SELECT id, platform, username, profile_url, email, followers, tags, status, metadata, quality_score, user_id, created_at
                FROM leads
                {where_clause}
                ORDER BY
                    CASE
                        WHEN metadata->>'asset_source' = 'keyword_company_search'
                             OR 'company_asset' = ANY(tags) THEN 0
                        WHEN email IS NOT NULL
                             OR metadata ? 'website'
                             OR metadata ? 'linkedin_url' THEN 1
                        ELSE 2
                    END ASC,
                    created_at DESC,
                    id DESC
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """
            params.extend([page_size, offset])

            rows = await conn.fetch(query, *params)

            leads = [
                _to_lead_response(row)
                for row in rows
            ]

            return LeadListResponse(
                leads=leads,
                total=total,
                page=page,
                page_size=page_size
            )
        except HTTPException:
            raise
        except Exception:
            logger.exception("Error fetching leads")
            raise HTTPException(status_code=500, detail="Database error")


@router.get("/{lead_id}", response_model=LeadDetailResponse)
async def get_lead(
    lead_id: int,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get a specific lead by ID."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                "SELECT id, platform, username, profile_url, email, followers, tags, status, metadata, quality_score, user_id, created_at FROM leads WHERE id = $1 AND user_id = $2",
                lead_id, current_user.id
            )
            if not row:
                raise HTTPException(status_code=404, detail="Lead not found")
            messages = await conn.fetch(
                """SELECT id, channel, COALESCE(subject, '') AS subject, body,
                          COALESCE(cta, '') AS cta, sequence_step, status,
                          personalization_evidence, quality_score, risk_flags,
                          generation_provider, generation_model, approved_at,
                          scheduled_at, sent_at, provider, attempts, last_error,
                          delivery_task_id, follow_up_sequence_id,
                          template_version_id, ab_experiment_id, ab_variant_id,
                          estimated_cost_usd, created_at
                   FROM marketing_messages
                   WHERE lead_id = $1 AND user_id = $2
                   ORDER BY created_at DESC, id DESC""",
                lead_id, current_user.id
            )
            return LeadDetailResponse(
                **_to_lead_response(row).model_dump(),
                marketing_messages=[_to_marketing_message(message) for message in messages]
            )
        except HTTPException:
            raise
        except Exception:
            logger.exception("Error fetching lead")
            raise HTTPException(status_code=500, detail="Database error")


@router.post("/", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    lead: LeadCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a new lead."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            if lead.platform not in VALID_PLATFORMS:
                raise HTTPException(status_code=400, detail=f"Invalid platform. Must be one of {VALID_PLATFORMS}")

            row = await conn.fetchrow(
                """INSERT INTO leads (platform, username, profile_url, email, followers, tags, status, user_id)
                   VALUES ($1, $2, $3, $4, $5, $6, 'new', $7)
                   RETURNING id, platform, username, profile_url, email, followers, tags, status, metadata, quality_score, user_id, created_at""",
                lead.platform, lead.username, lead.profile_url, sanitize_lead_email(lead.email),
                lead.followers, lead.tags, current_user.id
            )
            return _to_lead_response(row)
        except HTTPException:
            raise
        except Exception:
            logger.exception("Error creating lead")
            raise HTTPException(status_code=500, detail="Database error")


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: int,
    update: LeadUpdate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Update a lead."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow("SELECT id, user_id FROM leads WHERE id = $1 AND user_id = $2", lead_id, current_user.id)
            if not row:
                raise HTTPException(status_code=404, detail="Lead not found")

            updates = []
            params = []
            param_idx = 1

            if update.platform is not None:
                if update.platform not in VALID_PLATFORMS:
                    raise HTTPException(status_code=400, detail=f"Invalid platform. Must be one of {VALID_PLATFORMS}")
                updates.append(f"platform = ${param_idx}")
                params.append(update.platform)
                param_idx += 1

            if update.username is not None:
                updates.append(f"username = ${param_idx}")
                params.append(update.username)
                param_idx += 1

            if update.profile_url is not None:
                updates.append(f"profile_url = ${param_idx}")
                params.append(update.profile_url)
                param_idx += 1

            if update.email is not None:
                updates.append(f"email = ${param_idx}")
                params.append(sanitize_lead_email(update.email))
                param_idx += 1

            if update.followers is not None:
                updates.append(f"followers = ${param_idx}")
                params.append(update.followers)
                param_idx += 1

            if update.tags is not None:
                updates.append(f"tags = ${param_idx}")
                params.append(update.tags)
                param_idx += 1

            if update.status is not None:
                if update.status not in VALID_LEAD_STATUSES:
                    raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of {VALID_LEAD_STATUSES}")
                updates.append(f"status = ${param_idx}")
                params.append(update.status)
                param_idx += 1

            if not updates:
                raise HTTPException(status_code=400, detail="No fields to update")

            params.extend([lead_id, current_user.id])
            query = f"""
                UPDATE leads SET {', '.join(updates)}
                WHERE id = ${param_idx} AND user_id = ${param_idx + 1}
                RETURNING id, platform, username, profile_url, email, followers, tags, status, metadata, quality_score, user_id, created_at
            """

            row = await conn.fetchrow(query, *params)
            return _to_lead_response(row)
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: int,
    current_user: UserResponse = Depends(get_current_user)
):
    """Delete a lead."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow("SELECT id, user_id FROM leads WHERE id = $1 AND user_id = $2", lead_id, current_user.id)
            if not row:
                raise HTTPException(status_code=404, detail="Lead not found")
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM marketing_messages WHERE lead_id = $1 AND user_id = $2",
                    lead_id, current_user.id
                )
                await conn.execute("DELETE FROM leads WHERE id = $1 AND user_id = $2", lead_id, current_user.id)
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        return None
