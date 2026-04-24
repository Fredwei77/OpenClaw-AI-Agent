from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import asyncpg
import os
from .auth import get_db_pool, get_current_user, UserResponse

router = APIRouter()

VALID_PLATFORMS = {"instagram", "tiktok", "x", "facebook", "youtube", "linkedin"}
VALID_LEAD_STATUSES = {"new", "contacted", "qualified", "converted", "lost"}


class LeadCreate(BaseModel):
    platform: str
    username: str = Field(..., min_length=1, max_length=255)
    profile_url: Optional[str] = None
    email: Optional[str] = None
    followers: int = Field(default=0, ge=0)
    tags: List[str] = Field(default_factory=list)


class LeadUpdate(BaseModel):
    platform: Optional[str] = None
    username: Optional[str] = None
    profile_url: Optional[str] = None
    email: Optional[str] = None
    followers: Optional[int] = Field(default=None, ge=0)
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
    user_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class LeadListResponse(BaseModel):
    leads: List[LeadResponse]
    total: int
    page: int
    page_size: int


@router.get("/", response_model=LeadListResponse)
async def get_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
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
            conditions = ["user_id = $1"]
            params = [current_user.id]
            param_idx = 2

            if status_filter:
                if status_filter not in VALID_LEAD_STATUSES:
                    raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of {VALID_LEAD_STATUSES}")
                conditions.append(f"AND status = ${param_idx}")
                params.append(status_filter)
                param_idx += 1

            if platform:
                if platform not in VALID_PLATFORMS:
                    raise HTTPException(status_code=400, detail=f"Invalid platform. Must be one of {VALID_PLATFORMS}")
                conditions.append(f"AND platform = ${param_idx}")
                params.append(platform)
                param_idx += 1

            if search:
                escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                conditions.append(f"AND (username ILIKE ${param_idx} OR email ILIKE ${param_idx})")
                params.append(f"%{escaped}%")
                param_idx += 1

            if min_followers is not None:
                conditions.append(f"AND followers >= ${param_idx}")
                params.append(min_followers)
                param_idx += 1

            if max_followers is not None:
                conditions.append(f"AND followers <= ${param_idx}")
                params.append(max_followers)
                param_idx += 1

            if tags:
                tag_list = [t.strip() for t in tags.split(",") if t.strip()]
                for tag in tag_list:
                    conditions.append(f"AND ${param_idx} = ANY(tags)")
                    params.append(tag)
                    param_idx += 1

            where_clause = "WHERE " + " AND ".join(conditions)

            # Get total count
            count_query = f"SELECT COUNT(*) as count FROM leads {where_clause}"
            total = await conn.fetchval(count_query, *params)

            # Get paginated results
            offset = (page - 1) * page_size
            query = f"""
                SELECT id, platform, username, profile_url, email, followers, tags, status, user_id, created_at
                FROM leads
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """
            params.extend([page_size, offset])

            rows = await conn.fetch(query, *params)

            leads = [
                LeadResponse(
                    id=row['id'],
                    platform=row['platform'],
                    username=row['username'],
                    profile_url=row['profile_url'],
                    email=row['email'],
                    followers=row['followers'],
                    tags=row['tags'] or [],
                    status=getattr(row, 'status', 'new'),
                    user_id=row['user_id'],
                    created_at=row['created_at']
                )
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
        except Exception as e:
            raise HTTPException(status_code=500, detail="Database error")


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: int,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get a specific lead by ID."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                "SELECT id, platform, username, profile_url, email, followers, tags, status, user_id, created_at FROM leads WHERE id = $1",
                lead_id
            )
            if not row:
                raise HTTPException(status_code=404, detail="Lead not found")
            if row['user_id'] and row['user_id'] != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied")
            return LeadResponse(
                id=row['id'],
                platform=row['platform'],
                username=row['username'],
                profile_url=row['profile_url'],
                email=row['email'],
                followers=row['followers'],
                tags=row['tags'] or [],
                status=getattr(row, 'status', 'new'),
                user_id=row['user_id'],
                created_at=row['created_at']
            )
        except HTTPException:
            raise
        except Exception as e:
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
                   RETURNING id, platform, username, profile_url, email, followers, tags, status, user_id, created_at""",
                lead.platform, lead.username, lead.profile_url, lead.email,
                lead.followers, lead.tags, current_user.id
            )
            return LeadResponse(
                id=row['id'],
                platform=row['platform'],
                username=row['username'],
                profile_url=row['profile_url'],
                email=row['email'],
                followers=row['followers'],
                tags=row['tags'] or [],
                status=row['status'],
                user_id=row['user_id'],
                created_at=row['created_at']
            )
        except HTTPException:
            raise
        except Exception as e:
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
            row = await conn.fetchrow("SELECT id, user_id FROM leads WHERE id = $1", lead_id)
            if not row:
                raise HTTPException(status_code=404, detail="Lead not found")
            if row['user_id'] and row['user_id'] != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied")

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
                params.append(update.email)
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

            params.append(lead_id)
            query = f"""
                UPDATE leads SET {', '.join(updates)}
                WHERE id = ${param_idx}
                RETURNING id, platform, username, profile_url, email, followers, tags, status, user_id, created_at
            """

            row = await conn.fetchrow(query, *params)
            return LeadResponse(
                id=row['id'],
                platform=row['platform'],
                username=row['username'],
                profile_url=row['profile_url'],
                email=row['email'],
                followers=row['followers'],
                tags=row['tags'] or [],
                status=row['status'],
                user_id=row['user_id'],
                created_at=row['created_at']
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="Database error")


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: int,
    current_user: UserResponse = Depends(get_current_user)
):
    """Delete a lead."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow("SELECT id, user_id FROM leads WHERE id = $1", lead_id)
            if not row:
                raise HTTPException(status_code=404, detail="Lead not found")
            if row['user_id'] and row['user_id'] != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied")

            await conn.execute("DELETE FROM leads WHERE id = $1", lead_id)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="Database error")
        return None
