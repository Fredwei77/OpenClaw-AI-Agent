from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import datetime
import asyncpg
import json
import os
from .auth import get_db_pool, get_current_user, UserResponse

router = APIRouter()

# Valid task statuses and types
VALID_STATUSES = {"pending", "running", "completed", "failed", "cancelled"}
VALID_TASK_TYPES = {"scrape", "comment", "like", "follow", "message", "analytics"}


# Pydantic Models
class TaskCreate(BaseModel):
    agent_name: str = Field(..., min_length=1, max_length=255)
    task_type: Literal["scrape", "comment", "like", "follow", "message", "analytics"]
    payload: dict = Field(default_factory=dict)


class TaskUpdate(BaseModel):
    status: Optional[Literal["pending", "running", "completed", "failed", "cancelled"]] = None
    payload: Optional[dict] = None


class TaskResponse(BaseModel):
    id: int
    agent_name: str
    task_type: str
    payload: dict
    status: str
    created_at: datetime
    user_id: Optional[int] = None

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int
    page: int
    page_size: int


@router.get("/", response_model=TaskListResponse)
async def get_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    agent_name: Optional[str] = Query(None, max_length=255),
    task_type: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get paginated list of tasks with optional filters."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            # Build query conditions - users can only see their own tasks
            conditions = ["user_id = $1"]
            params = [current_user.id]
            param_idx = 2

            if status_filter:
                if status_filter not in VALID_STATUSES:
                    raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of {VALID_STATUSES}")
                conditions.append(f"AND status = ${param_idx}")
                params.append(status_filter)
                param_idx += 1

            if agent_name:
                # Escape special LIKE characters
                escaped = agent_name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                conditions.append(f"AND agent_name ILIKE ${param_idx}")
                params.append(f"%{escaped}%")
                param_idx += 1

            if task_type:
                if task_type not in VALID_TASK_TYPES:
                    raise HTTPException(status_code=400, detail=f"Invalid task type. Must be one of {VALID_TASK_TYPES}")
                conditions.append(f"AND task_type = ${param_idx}")
                params.append(task_type)
                param_idx += 1

            where_clause = "WHERE " + " AND ".join(conditions)

            # Get total count
            count_query = f"SELECT COUNT(*) as count FROM tasks {where_clause}"
            total = await conn.fetchval(count_query, *params)

            # Get paginated results
            offset = (page - 1) * page_size
            query = f"""
                SELECT id, agent_name, task_type, payload, status, created_at, user_id
                FROM tasks
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """
            params.extend([page_size, offset])

            rows = await conn.fetch(query, *params)

            def parse_payload(p):
                if isinstance(p, str):
                    return json.loads(p)
                return p or {}

            tasks = [
                TaskResponse(
                    id=row['id'],
                    agent_name=row['agent_name'],
                    task_type=row['task_type'],
                    payload=parse_payload(row['payload']),
                    status=row['status'],
                    created_at=row['created_at'],
                    user_id=row['user_id']
                )
                for row in rows
            ]

            return TaskListResponse(
                tasks=tasks,
                total=total,
                page=page,
                page_size=page_size
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="Database error")


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get a specific task by ID."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                "SELECT id, agent_name, task_type, payload, status, created_at, user_id FROM tasks WHERE id = $1",
                task_id
            )
            if not row:
                raise HTTPException(status_code=404, detail="Task not found")
            # Authorization: user can only view their own tasks
            if row['user_id'] and row['user_id'] != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied")
            return TaskResponse(
                id=row['id'],
                agent_name=row['agent_name'],
                task_type=row['task_type'],
                payload=parse_payload(row['payload']),
                status=row['status'],
                created_at=row['created_at'],
                user_id=row['user_id']
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="Database error")


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task: TaskCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a new task."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                """INSERT INTO tasks (agent_name, task_type, payload, status, user_id)
                   VALUES ($1, $2, $3, 'pending', $4)
                   RETURNING id, agent_name, task_type, payload, status, created_at, user_id""",
                task.agent_name, task.task_type, json.dumps(task.payload), current_user.id
            )

            def parse_payload(p):
                if isinstance(p, str):
                    return json.loads(p)
                return p or {}

            return TaskResponse(
                id=row['id'],
                agent_name=row['agent_name'],
                task_type=row['task_type'],
                payload=parse_payload(row['payload']),
                status=row['status'],
                created_at=row['created_at'],
                user_id=row['user_id']
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="Database error")


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    update: TaskUpdate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Update a task's status or payload."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            # Check if task exists and belongs to user
            row = await conn.fetchrow("SELECT id, user_id FROM tasks WHERE id = $1", task_id)
            if not row:
                raise HTTPException(status_code=404, detail="Task not found")
            # Authorization: user can only update their own tasks
            if row['user_id'] and row['user_id'] != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied")

            # Build update query dynamically
            updates = []
            params = []
            param_idx = 1

            if update.status:
                if update.status not in VALID_STATUSES:
                    raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of {VALID_STATUSES}")
                updates.append(f"status = ${param_idx}")
                params.append(update.status)
                param_idx += 1

            if update.payload is not None:
                updates.append(f"payload = ${param_idx}")
                params.append(json.dumps(update.payload))
                param_idx += 1

            if not updates:
                raise HTTPException(status_code=400, detail="No fields to update")

            params.append(task_id)
            query = f"""
                UPDATE tasks SET {', '.join(updates)}
                WHERE id = ${param_idx}
                RETURNING id, agent_name, task_type, payload, status, created_at, user_id
            """

            def parse_payload(p):
                if isinstance(p, str):
                    return json.loads(p)
                return p or {}

            row = await conn.fetchrow(query, *params)
            return TaskResponse(
                id=row['id'],
                agent_name=row['agent_name'],
                task_type=row['task_type'],
                payload=parse_payload(row['payload']),
                status=row['status'],
                created_at=row['created_at'],
                user_id=row['user_id']
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="Database error")


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    current_user: UserResponse = Depends(get_current_user)
):
    """Delete a task."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            # Check if task exists and belongs to user
            row = await conn.fetchrow("SELECT id, user_id FROM tasks WHERE id = $1", task_id)
            if not row:
                raise HTTPException(status_code=404, detail="Task not found")
            # Authorization: user can only delete their own tasks
            if row['user_id'] and row['user_id'] != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied")

            await conn.execute("DELETE FROM tasks WHERE id = $1", task_id)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="Database error")
        return None
