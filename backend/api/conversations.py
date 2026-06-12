import json
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from automation.engine import as_dict
from .auth import UserResponse, get_current_user, get_db_pool

router = APIRouter()


class ConversationResponse(BaseModel):
    id: int
    lead_id: Optional[int]
    channel: str
    external_id: Optional[str]
    contact_name: str
    status: str
    mode: str
    priority: str
    unread_count: int
    intent: Optional[str]
    intent_confidence: Optional[float]
    ai_summary: Optional[str]
    handoff_reason: Optional[str]
    assigned_to: Optional[int]
    quality_score: int = 0
    last_message: Optional[str] = None
    last_message_at: Optional[datetime]
    updated_at: datetime


class ConversationMessageResponse(BaseModel):
    id: int
    direction: str
    message_type: str
    content: str
    status: str
    metadata: Dict[str, Any]
    created_at: datetime


class ConversationEventResponse(BaseModel):
    id: int
    event_type: str
    actor_type: str
    actor_id: Optional[int]
    payload: Dict[str, Any]
    created_at: datetime


class ConversationUpdate(BaseModel):
    status: Optional[Literal["open", "pending", "resolved", "closed"]] = None
    priority: Optional[Literal["normal", "high", "urgent"]] = None


class ManualReplyRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)


class HandoffRequest(BaseModel):
    reason: str = Field(default="Manually assigned for human follow-up.", max_length=1000)


def _to_conversation(row) -> ConversationResponse:
    data = dict(row)
    if data.get("intent_confidence") is not None:
        data["intent_confidence"] = float(data["intent_confidence"])
    return ConversationResponse(**data)


@router.get("/", response_model=List[ConversationResponse])
async def list_conversations(
    limit: int = Query(50, ge=1, le=200),
    mode: Optional[Literal["automation", "human"]] = None,
    conversation_status: Optional[Literal["open", "pending", "resolved", "closed"]] = Query(
        default=None,
        alias="status",
    ),
    unread_only: bool = False,
    current_user: UserResponse = Depends(get_current_user),
):
    conditions = ["c.user_id = $1"]
    values: list[Any] = [current_user.id]
    if mode:
        values.append(mode)
        conditions.append(f"c.mode = ${len(values)}")
    if conversation_status:
        values.append(conversation_status)
        conditions.append(f"c.status = ${len(values)}")
    if unread_only:
        conditions.append("c.unread_count > 0")
    values.append(limit)

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT c.id, c.lead_id, c.channel, c.external_id,
                       COALESCE(c.metadata->>'contact_name', c.external_id, 'Unknown') AS contact_name,
                       c.status, c.mode, c.priority, c.unread_count, c.intent,
                       c.intent_confidence, c.ai_summary, c.handoff_reason, c.assigned_to,
                       COALESCE(l.quality_score, 0) AS quality_score,
                       (
                           SELECT m.content
                           FROM conversation_messages m
                           WHERE m.conversation_id = c.id AND m.user_id = c.user_id
                           ORDER BY m.created_at DESC, m.id DESC
                           LIMIT 1
                       ) AS last_message,
                       c.last_message_at, c.updated_at
                FROM conversations c
                LEFT JOIN leads l ON l.id = c.lead_id AND l.user_id = c.user_id
                WHERE {" AND ".join(conditions)}
                ORDER BY
                    CASE c.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 ELSE 2 END,
                    c.updated_at DESC
                LIMIT ${len(values)}""",
            *values,
        )
    return [_to_conversation(row) for row in rows]


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: int,
    request: ConversationUpdate,
    current_user: UserResponse = Depends(get_current_user),
):
    updates = request.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No conversation changes supplied")

    assignments = []
    values: list[Any] = []
    for field, value in updates.items():
        values.append(value)
        assignments.append(f"{field} = ${len(values)}")
    values.extend([conversation_id, current_user.id])

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        updated = await conn.fetchval(
            f"""UPDATE conversations
                SET {", ".join(assignments)}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ${len(values) - 1} AND user_id = ${len(values)}
                RETURNING id""",
            *values,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Conversation not found")
        await _record_event(
            conn,
            conversation_id,
            current_user.id,
            "conversation_updated",
            "human",
            current_user.id,
            updates,
        )
        row = await _fetch_conversation(conn, conversation_id, current_user.id)
    return _to_conversation(row)


@router.get("/{conversation_id}/messages", response_model=List[ConversationMessageResponse])
async def list_messages(
    conversation_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await _require_conversation(conn, conversation_id, current_user.id)
        rows = await conn.fetch(
            """SELECT id, direction, message_type, content, status, metadata, created_at
               FROM conversation_messages
               WHERE conversation_id = $1 AND user_id = $2
               ORDER BY created_at, id""",
            conversation_id,
            current_user.id,
        )
    return [
        ConversationMessageResponse(**{**dict(row), "metadata": as_dict(row["metadata"])})
        for row in rows
    ]


@router.get("/{conversation_id}/events", response_model=List[ConversationEventResponse])
async def list_events(
    conversation_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await _require_conversation(conn, conversation_id, current_user.id)
        rows = await conn.fetch(
            """SELECT id, event_type, actor_type, actor_id, payload, created_at
               FROM conversation_events
               WHERE conversation_id = $1 AND user_id = $2
               ORDER BY created_at DESC, id DESC""",
            conversation_id,
            current_user.id,
        )
    return [
        ConversationEventResponse(**{**dict(row), "payload": as_dict(row["payload"])})
        for row in rows
    ]


@router.post(
    "/{conversation_id}/messages",
    response_model=ConversationMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_manual_reply(
    conversation_id: int,
    request: ManualReplyRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Reply content cannot be blank")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await _require_conversation(conn, conversation_id, current_user.id)
            row = await conn.fetchrow(
                """INSERT INTO conversation_messages
                   (conversation_id, user_id, direction, message_type, content, status, metadata)
                   VALUES ($1, $2, 'outbound', 'text', $3, 'simulated', $4::jsonb)
                   RETURNING id, direction, message_type, content, status, metadata, created_at""",
                conversation_id,
                current_user.id,
                content,
                json.dumps(
                    {"source": "human", "actor_id": current_user.id},
                    ensure_ascii=False,
                ),
            )
            await conn.execute(
                """UPDATE conversations
                   SET mode = 'human', assigned_to = $1, unread_count = 0,
                       last_message_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                   WHERE id = $2 AND user_id = $1""",
                current_user.id,
                conversation_id,
            )
            await _record_event(
                conn,
                conversation_id,
                current_user.id,
                "manual_reply_sent",
                "human",
                current_user.id,
                {"message_id": row["id"]},
            )
    return ConversationMessageResponse(**{**dict(row), "metadata": as_dict(row["metadata"])})


@router.post("/{conversation_id}/takeover", response_model=ConversationResponse)
async def takeover_conversation(
    conversation_id: int,
    request: HandoffRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row_id = await conn.fetchval(
            """UPDATE conversations
               SET mode = 'human', assigned_to = $1, handoff_reason = $2,
                   unread_count = 0, updated_at = CURRENT_TIMESTAMP
               WHERE id = $3 AND user_id = $1
               RETURNING id""",
            current_user.id,
            request.reason,
            conversation_id,
        )
        if not row_id:
            raise HTTPException(status_code=404, detail="Conversation not found")
        await _record_event(
            conn,
            conversation_id,
            current_user.id,
            "human_takeover",
            "human",
            current_user.id,
            {"reason": request.reason},
        )
        row = await _fetch_conversation(conn, conversation_id, current_user.id)
    return _to_conversation(row)


@router.post("/{conversation_id}/release", response_model=ConversationResponse)
async def release_conversation(
    conversation_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row_id = await conn.fetchval(
            """UPDATE conversations
               SET mode = 'automation', assigned_to = NULL, handoff_reason = NULL,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = $1 AND user_id = $2
               RETURNING id""",
            conversation_id,
            current_user.id,
        )
        if not row_id:
            raise HTTPException(status_code=404, detail="Conversation not found")
        await _record_event(
            conn,
            conversation_id,
            current_user.id,
            "automation_resumed",
            "human",
            current_user.id,
            {},
        )
        row = await _fetch_conversation(conn, conversation_id, current_user.id)
    return _to_conversation(row)


@router.post("/{conversation_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_conversation_read(
    conversation_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """UPDATE conversations
               SET unread_count = 0, updated_at = CURRENT_TIMESTAMP
               WHERE id = $1 AND user_id = $2""",
            conversation_id,
            current_user.id,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Conversation not found")
    return None


async def _require_conversation(conn, conversation_id: int, user_id: int) -> None:
    owned = await conn.fetchval(
        "SELECT 1 FROM conversations WHERE id = $1 AND user_id = $2",
        conversation_id,
        user_id,
    )
    if not owned:
        raise HTTPException(status_code=404, detail="Conversation not found")


async def _record_event(
    conn,
    conversation_id: int,
    user_id: int,
    event_type: str,
    actor_type: str,
    actor_id: Optional[int],
    payload: Dict[str, Any],
) -> None:
    await conn.execute(
        """INSERT INTO conversation_events
           (conversation_id, user_id, event_type, actor_type, actor_id, payload)
           VALUES ($1, $2, $3, $4, $5, $6::jsonb)""",
        conversation_id,
        user_id,
        event_type,
        actor_type,
        actor_id,
        json.dumps(payload, ensure_ascii=False),
    )


async def _fetch_conversation(conn, conversation_id: int, user_id: int):
    return await conn.fetchrow(
        """SELECT c.id, c.lead_id, c.channel, c.external_id,
                  COALESCE(c.metadata->>'contact_name', c.external_id, 'Unknown') AS contact_name,
                  c.status, c.mode, c.priority, c.unread_count, c.intent,
                  c.intent_confidence, c.ai_summary, c.handoff_reason, c.assigned_to,
                  COALESCE(l.quality_score, 0) AS quality_score,
                  (
                      SELECT m.content
                      FROM conversation_messages m
                      WHERE m.conversation_id = c.id AND m.user_id = c.user_id
                      ORDER BY m.created_at DESC, m.id DESC
                      LIMIT 1
                  ) AS last_message,
                  c.last_message_at, c.updated_at
           FROM conversations c
           LEFT JOIN leads l ON l.id = c.lead_id AND l.user_id = c.user_id
           WHERE c.id = $1 AND c.user_id = $2""",
        conversation_id,
        user_id,
    )
