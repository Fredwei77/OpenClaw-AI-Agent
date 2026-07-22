from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from acquisition.runner import acquisition_task_worker
from .auth import UserResponse, get_current_user, get_db_pool

router = APIRouter()


class PlatformTarget(BaseModel):
    platform: Literal[
        "x", "twitter", "linkedin", "instagram", "facebook", "tiktok",
        "shopify", "google", "duckduckgo", "directory",
    ]
    priority: int = Field(default=1, ge=0, le=3)


class AcquisitionTaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    keyword: str = Field(..., min_length=1, max_length=255)
    platforms: list[PlatformTarget] = Field(..., min_length=1, max_length=10)
    product_context: str = Field(default="", max_length=2000)
    max_results_per_platform: int = Field(default=25, ge=1, le=200)
    max_outreach_leads: int = Field(default=20, ge=1, le=20)
    approval_mode: Literal["review", "automatic"] = "review"
    delivery_mode: Literal["dry_run", "live"] = "dry_run"
    schedule_at: Optional[datetime] = None
    interval_hours: Optional[int] = Field(default=None, ge=1, le=24 * 30)


class AcquisitionTaskResponse(BaseModel):
    id: int
    name: str
    keyword: str
    platforms: list[dict[str, Any]]
    product_context: str
    status: str
    approval_mode: str
    delivery_mode: str
    max_results_per_platform: int
    max_outreach_leads: int
    interval_hours: Optional[int]
    next_run_at: Optional[datetime]
    last_run_at: Optional[datetime]
    run_count: int
    last_error: Optional[str]
    created_at: datetime
    updated_at: datetime


def _task_response(row) -> AcquisitionTaskResponse:
    data = dict(row)
    if isinstance(data.get("platforms"), str):
        data["platforms"] = json.loads(data["platforms"])
    return AcquisitionTaskResponse(**data)


@router.post("/", response_model=AcquisitionTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    request: AcquisitionTaskCreate,
    current_user: UserResponse = Depends(get_current_user),
):
    if request.approval_mode == "review" and request.delivery_mode == "live":
        raise HTTPException(status_code=400, detail="Live delivery requires automatic approval mode")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO acquisition_tasks
               (user_id, name, keyword, platforms, product_context,
                max_results_per_platform, max_outreach_leads,
                approval_mode, delivery_mode, status, next_run_at, interval_hours)
               VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9, 'active',
                       COALESCE($10, CURRENT_TIMESTAMP), $11)
               RETURNING *""",
            current_user.id, request.name.strip(), request.keyword.strip(),
            json.dumps([item.model_dump() for item in request.platforms]),
            request.product_context.strip(), request.max_results_per_platform,
            request.max_outreach_leads, request.approval_mode,
            request.delivery_mode, request.schedule_at, request.interval_hours,
        )
    return _task_response(row)


@router.get("/", response_model=list[AcquisitionTaskResponse])
async def list_tasks(
    limit: int = Query(50, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM acquisition_tasks WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
            current_user.id, limit,
        )
    return [_task_response(row) for row in rows]


@router.get("/{task_id}/runs")
async def get_runs(task_id: int, current_user: UserResponse = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        owned = await conn.fetchval(
            "SELECT 1 FROM acquisition_tasks WHERE id = $1 AND user_id = $2",
            task_id, current_user.id,
        )
        if not owned:
            raise HTTPException(status_code=404, detail="Acquisition task not found")
        runs = await conn.fetch(
            """SELECT id, status, result, error, started_at, completed_at
               FROM acquisition_task_runs WHERE task_id = $1 AND user_id = $2
               ORDER BY started_at DESC LIMIT 20""",
            task_id, current_user.id,
        )
        output = []
        for run in runs:
            item = dict(run)
            steps = await conn.fetch(
                """SELECT id, step_type, status, input, output, error, started_at, completed_at
                   FROM acquisition_task_run_steps WHERE run_id = $1 ORDER BY id""",
                run["id"],
            )
            item["steps"] = [dict(step) for step in steps]
            output.append(item)
    return output


async def _transition(task_id: int, user_id: int, action: str):
    transitions = {
        "pause": ("paused", {"active", "failed", "completed"}),
        "resume": ("active", {"paused", "failed", "completed"}),
        "retry": ("active", {"failed", "completed"}),
    }
    target, allowed = transitions[action]
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """UPDATE acquisition_tasks SET status = $1,
                      next_run_at = CASE WHEN $1 = 'active' THEN CURRENT_TIMESTAMP ELSE next_run_at END,
                      last_error = CASE WHEN $1 = 'active' THEN NULL ELSE last_error END,
                      updated_at = CURRENT_TIMESTAMP
               WHERE id = $2 AND user_id = $3 AND status = ANY($4::text[])
               RETURNING *""",
            target, task_id, user_id, list(allowed),
        )
    if not row:
        raise HTTPException(status_code=409, detail=f"Task cannot {action} from its current state")
    return _task_response(row)


@router.post("/{task_id}/pause", response_model=AcquisitionTaskResponse)
async def pause_task(task_id: int, current_user: UserResponse = Depends(get_current_user)):
    return await _transition(task_id, current_user.id, "pause")


@router.post("/{task_id}/resume", response_model=AcquisitionTaskResponse)
async def resume_task(task_id: int, current_user: UserResponse = Depends(get_current_user)):
    return await _transition(task_id, current_user.id, "resume")


@router.post("/{task_id}/retry", response_model=AcquisitionTaskResponse)
async def retry_task(task_id: int, current_user: UserResponse = Depends(get_current_user)):
    return await _transition(task_id, current_user.id, "retry")


@router.post("/{task_id}/run-now", response_model=AcquisitionTaskResponse)
async def run_now(task_id: int, current_user: UserResponse = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """UPDATE acquisition_tasks SET status = 'running', next_run_at = CURRENT_TIMESTAMP,
                      last_error = NULL, updated_at = CURRENT_TIMESTAMP
               WHERE id = $1 AND user_id = $2 AND status <> 'running' RETURNING *""",
            task_id, current_user.id,
        )
    if not row:
        raise HTTPException(status_code=409, detail="Running task cannot be started again")
    asyncio.create_task(acquisition_task_worker.execute(dict(row)))
    return _task_response(row)
