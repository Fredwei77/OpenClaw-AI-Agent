from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import asyncpg
import os
from .auth import get_db_pool, get_current_user, UserResponse

router = APIRouter()

VALID_PLATFORMS = {"instagram", "tiktok", "x", "facebook", "youtube", "linkedin"}
VALID_TASK_TYPES = {"scrape", "comment", "like", "follow", "message", "analytics"}


class DashboardSummary(BaseModel):
    total_leads: int
    new_leads_this_week: int
    total_products: int
    active_tasks: int
    completed_tasks: int
    failed_tasks: int


class TaskStatusBreakdown(BaseModel):
    pending: int
    running: int
    completed: int
    failed: int
    cancelled: int


class LeadsByPlatform(BaseModel):
    platform: str
    count: int


class LeadsByStatus(BaseModel):
    status: str
    count: int


class RecentActivity(BaseModel):
    id: int
    type: str
    description: str
    created_at: datetime


class AnalyticsResponse(BaseModel):
    dashboard: DashboardSummary
    task_breakdown: TaskStatusBreakdown
    leads_by_platform: List[LeadsByPlatform]
    leads_by_status: List[LeadsByStatus]
    recent_activity: List[RecentActivity]


@router.get("/", response_model=AnalyticsResponse)
async def get_analytics(
    current_user: UserResponse = Depends(get_current_user)
):
    """Get analytics dashboard data."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)

        # Dashboard summary
        total_leads = await conn.fetchval(
            "SELECT COUNT(*) FROM leads WHERE user_id = $1", current_user.id
        )
        new_leads_this_week = await conn.fetchval(
            "SELECT COUNT(*) FROM leads WHERE user_id = $1 AND created_at >= $2",
            current_user.id, week_ago
        )
        total_products = await conn.fetchval(
            "SELECT COUNT(*) FROM products WHERE user_id = $1", current_user.id
        )

        # Task counts
        active_tasks = await conn.fetchval(
            "SELECT COUNT(*) FROM tasks WHERE user_id = $1 AND status IN ('pending', 'running')",
            current_user.id
        )
        completed_tasks = await conn.fetchval(
            "SELECT COUNT(*) FROM tasks WHERE user_id = $1 AND status = 'completed'",
            current_user.id
        )
        failed_tasks = await conn.fetchval(
            "SELECT COUNT(*) FROM tasks WHERE user_id = $1 AND status = 'failed'",
            current_user.id
        )

        dashboard = DashboardSummary(
            total_leads=total_leads or 0,
            new_leads_this_week=new_leads_this_week or 0,
            total_products=total_products or 0,
            active_tasks=active_tasks or 0,
            completed_tasks=completed_tasks or 0,
            failed_tasks=failed_tasks or 0
        )

        # Task status breakdown
        task_rows = await conn.fetch(
            "SELECT status, COUNT(*) as count FROM tasks WHERE user_id = $1 GROUP BY status",
            current_user.id
        )
        task_breakdown = TaskStatusBreakdown(
            pending=0, running=0, completed=0, failed=0, cancelled=0
        )
        for row in task_rows:
            if row['status'] == 'pending':
                task_breakdown.pending = row['count']
            elif row['status'] == 'running':
                task_breakdown.running = row['count']
            elif row['status'] == 'completed':
                task_breakdown.completed = row['count']
            elif row['status'] == 'failed':
                task_breakdown.failed = row['count']
            elif row['status'] == 'cancelled':
                task_breakdown.cancelled = row['count']

        # Leads by platform
        platform_rows = await conn.fetch(
            "SELECT platform, COUNT(*) as count FROM leads WHERE user_id = $1 GROUP BY platform",
            current_user.id
        )
        leads_by_platform = [
            LeadsByPlatform(platform=row['platform'], count=row['count'])
            for row in platform_rows
        ]

        # Leads by status
        status_rows = await conn.fetch(
            "SELECT status, COUNT(*) as count FROM leads WHERE user_id = $1 GROUP BY status",
            current_user.id
        )
        leads_by_status = [
            LeadsByStatus(status=row['status'] or 'new', count=row['count'])
            for row in status_rows
        ]

        # Recent activity (combine recent leads and tasks)
        recent_leads = await conn.fetch(
            """SELECT id, 'lead' as type, username as description, created_at
               FROM leads WHERE user_id = $1
               ORDER BY created_at DESC LIMIT 5""",
            current_user.id
        )
        recent_tasks = await conn.fetch(
            """SELECT id, 'task' as type, agent_name as description, created_at
               FROM tasks WHERE user_id = $1
               ORDER BY created_at DESC LIMIT 5""",
            current_user.id
        )

        # Combine and sort
        all_activity = []
        for row in recent_leads:
            all_activity.append(RecentActivity(
                id=row['id'],
                type='lead',
                description=f"New lead: {row['description']}",
                created_at=row['created_at']
            ))
        for row in recent_tasks:
            all_activity.append(RecentActivity(
                id=row['id'],
                type='task',
                description=f"Task: {row['description']}",
                created_at=row['created_at']
            ))
        all_activity.sort(key=lambda x: x.created_at, reverse=True)
        recent_activity = all_activity[:10]

        return AnalyticsResponse(
            dashboard=dashboard,
            task_breakdown=task_breakdown,
            leads_by_platform=leads_by_platform,
            leads_by_status=leads_by_status,
            recent_activity=recent_activity
        )


@router.get("/leads/summary")
async def get_leads_analytics(
    platform: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get leads analytics summary with optional platform filter."""
    if platform and platform not in VALID_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Invalid platform. Must be one of {VALID_PLATFORMS}")

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        base_query = "SELECT COUNT(*) as total, AVG(followers) as avg_followers FROM leads WHERE user_id = $1"
        params = [current_user.id]

        if platform:
            base_query += " AND platform = $2"
            params.append(platform)

        row = await conn.fetchrow(base_query, *params)

        return {
            "total_leads": row['total'] or 0,
            "avg_followers": float(row['avg_followers']) if row['avg_followers'] else 0,
            "platform": platform or "all"
        }


@router.get("/tasks/summary")
async def get_tasks_analytics(
    task_type: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get tasks analytics summary."""
    if task_type and task_type not in VALID_TASK_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid task type. Must be one of {VALID_TASK_TYPES}")

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        conditions = ["user_id = $1"]
        params = [current_user.id]

        if task_type:
            conditions.append("task_type = $2")
            params.append(task_type)

        where_clause = "WHERE " + " AND ".join(conditions)

        total = await conn.fetchval(f"SELECT COUNT(*) FROM tasks {where_clause}", *params)

        completed = await conn.fetchval(
            f"SELECT COUNT(*) FROM tasks {where_clause} AND status = 'completed'",
            *params
        )
        failed = await conn.fetchval(
            f"SELECT COUNT(*) FROM tasks {where_clause} AND status = 'failed'",
            *params
        )

        success_rate = (completed / total * 100) if total > 0 else 0

        return {
            "total_tasks": total or 0,
            "completed": completed or 0,
            "failed": failed or 0,
            "success_rate": round(success_rate, 2),
            "task_type": task_type or "all"
        }
