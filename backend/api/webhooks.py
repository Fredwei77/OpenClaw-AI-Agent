import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from automation.engine import AutomationEngine
from automation.intelligence import analyze_message
from .auth import UserResponse, get_current_user, get_db_pool

router = APIRouter()


class SimulatedContact(BaseModel):
    external_id: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class SimulatedMessage(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)


class WebhookSimulationRequest(BaseModel):
    event_id: Optional[str] = Field(default=None, max_length=255)
    event_type: str = "inbound_message"
    channel: str = "webhook"
    contact: SimulatedContact
    message: SimulatedMessage
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WebhookSimulationResponse(BaseModel):
    event_id: str
    event_row_id: int
    duplicate: bool
    lead_id: int
    conversation_id: int
    run_ids: List[int]


@router.post("/simulate", response_model=WebhookSimulationResponse)
async def simulate_webhook(
    request: WebhookSimulationRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    if not request.contact.external_id.strip():
        raise HTTPException(status_code=400, detail="contact.external_id cannot be blank")
    if not request.contact.name.strip():
        raise HTTPException(status_code=400, detail="contact.name cannot be blank")
    if not request.message.content.strip():
        raise HTTPException(status_code=400, detail="message.content cannot be blank")
    pool = await get_db_pool()
    event_id = request.event_id or f"sim-{uuid.uuid4()}"
    payload = request.model_dump()
    payload["event_id"] = event_id
    intelligence = analyze_message(request.message.content, request.contact.model_dump())
    payload["intelligence"] = intelligence

    async with pool.acquire() as conn:
        try:
            async with conn.transaction():
                event_row_id = await conn.fetchval(
                    """INSERT INTO webhook_events
                       (user_id, event_id, event_type, channel, payload)
                       VALUES ($1, $2, $3, $4, $5::jsonb)
                       RETURNING id""",
                    current_user.id,
                    event_id,
                    request.event_type,
                    request.channel,
                    json.dumps(payload, ensure_ascii=False),
                )
                lead_id = await conn.fetchval(
                    """INSERT INTO leads
                       (user_id, platform, username, email, followers, tags, status, metadata)
                       VALUES ($1, $2, $3, $4, 0, $5, 'new', $6::jsonb)
                       ON CONFLICT (user_id, platform, username)
                       DO UPDATE SET
                           email = COALESCE(EXCLUDED.email, leads.email),
                           tags = ARRAY(
                               SELECT DISTINCT value
                               FROM unnest(COALESCE(leads.tags, '{}'::text[]) || EXCLUDED.tags) AS value
                           ),
                           metadata = leads.metadata || EXCLUDED.metadata
                       RETURNING id""",
                    current_user.id,
                    request.channel,
                    request.contact.external_id,
                    request.contact.email,
                    request.contact.tags,
                    json.dumps(
                        {"display_name": request.contact.name, **request.metadata},
                        ensure_ascii=False,
                    ),
                )
                conversation_id = await conn.fetchval(
                    """INSERT INTO conversations
                       (user_id, lead_id, channel, external_id, metadata, last_message_at)
                       VALUES ($1, $2, $3, $4, $5::jsonb, CURRENT_TIMESTAMP)
                       ON CONFLICT (user_id, channel, external_id)
                       WHERE external_id IS NOT NULL
                       DO UPDATE SET
                           lead_id = EXCLUDED.lead_id,
                           metadata = conversations.metadata || EXCLUDED.metadata,
                           unread_count = conversations.unread_count + 1,
                           last_message_at = CURRENT_TIMESTAMP,
                           updated_at = CURRENT_TIMESTAMP
                       RETURNING id""",
                    current_user.id,
                    lead_id,
                    request.channel,
                    request.contact.external_id,
                    json.dumps({"contact_name": request.contact.name}, ensure_ascii=False),
                )
                await conn.execute(
                    """UPDATE leads
                       SET quality_score = $1,
                           metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb
                       WHERE id = $3 AND user_id = $4""",
                    intelligence["score"],
                    json.dumps(
                        {
                            "intent": intelligence["intent"],
                            "temperature": intelligence["temperature"],
                            "intelligence": intelligence,
                        },
                        ensure_ascii=False,
                    ),
                    lead_id,
                    current_user.id,
                )
                await conn.execute(
                    """UPDATE conversations
                       SET intent = $1, intent_confidence = $2, ai_summary = $3,
                           priority = $4, unread_count = GREATEST(unread_count, 1)
                       WHERE id = $5 AND user_id = $6""",
                    intelligence["intent"],
                    intelligence["confidence"],
                    intelligence["summary"],
                    intelligence["priority"],
                    conversation_id,
                    current_user.id,
                )
                await conn.execute(
                    """INSERT INTO conversation_messages
                       (conversation_id, user_id, direction, message_type, content, status, metadata)
                       VALUES ($1, $2, 'inbound', 'text', $3, 'received', $4::jsonb)""",
                    conversation_id,
                    current_user.id,
                    request.message.content,
                    json.dumps({"event_id": event_id}, ensure_ascii=False),
                )
                await conn.execute(
                    """UPDATE webhook_events
                       SET lead_id = $1, conversation_id = $2
                       WHERE id = $3 AND user_id = $4""",
                    lead_id,
                    conversation_id,
                    event_row_id,
                    current_user.id,
                )
        except asyncpg.UniqueViolationError:
            existing = await conn.fetchrow(
                """SELECT e.id AS event_row_id,
                          COALESCE(e.conversation_id, c.id) AS conversation_id,
                          COALESCE(e.lead_id, c.lead_id) AS lead_id
                   FROM webhook_events e
                   LEFT JOIN conversations c
                     ON c.user_id = e.user_id
                    AND c.channel = e.channel
                    AND c.external_id = e.payload #>> '{contact,external_id}'
                   WHERE e.user_id = $1 AND e.event_id = $2""",
                current_user.id,
                event_id,
            )
            if not existing or existing["conversation_id"] is None or existing["lead_id"] is None:
                raise
            return WebhookSimulationResponse(
                event_id=event_id,
                event_row_id=existing["event_row_id"],
                duplicate=True,
                lead_id=existing["lead_id"],
                conversation_id=existing["conversation_id"],
                run_ids=[],
            )

    try:
        engine = AutomationEngine()
        run_ids = await engine.process_event(
            user_id=current_user.id,
            event_row_id=event_row_id,
            event=payload,
            conversation_id=conversation_id,
            lead_id=lead_id,
        )
        async with pool.acquire() as conn:
            await conn.execute(
                """UPDATE webhook_events
                   SET status = 'processed', processed_at = CURRENT_TIMESTAMP
                   WHERE id = $1 AND user_id = $2""",
                event_row_id,
                current_user.id,
            )
    except Exception as exc:
        async with pool.acquire() as conn:
            await conn.execute(
                """UPDATE webhook_events
                   SET status = 'failed', error = $2, processed_at = CURRENT_TIMESTAMP
                   WHERE id = $1 AND user_id = $3""",
                event_row_id,
                str(exc),
                current_user.id,
            )
        raise
    return WebhookSimulationResponse(
        event_id=event_id,
        event_row_id=event_row_id,
        duplicate=False,
        lead_id=lead_id,
        conversation_id=conversation_id,
        run_ids=run_ids,
    )
