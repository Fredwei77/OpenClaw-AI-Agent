from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from .auth import UserResponse, get_current_user, get_db_pool

router = APIRouter()

MODEL_COST_PER_1K = {
    "local": 0.0,
    "local-chat-v1": 0.0,
    "local_fallback": 0.0,
    "local-intelligence-v1": 0.0,
    "qwen/qwen3-30b-a3b-instruct-2507": 0.0008,
    "meta-llama/llama-3-8b-instruct": 0.0003,
}


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    channel: Literal["email", "linkedin_dm", "twitter_dm"]


class TemplateVersionCreate(BaseModel):
    subject: str = Field(default="", max_length=500)
    body: str = Field(..., min_length=1, max_length=10000)
    cta: str = Field(default="", max_length=500)
    prompt: str = Field(default="", max_length=12000)
    model: str = Field(default="", max_length=255)
    status: Literal["draft", "active", "archived"] = "active"


class ExperimentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    campaign_id: Optional[int] = Field(default=None, ge=1)
    goal: Literal["reply_rate", "conversion_rate"] = "reply_rate"
    traffic_split: int = Field(default=100, ge=1, le=100)
    variants: list[dict[str, Any]] = Field(..., min_length=2, max_length=5)


class PromptEvaluationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    prompt: str = Field(..., min_length=1, max_length=12000)
    model: str = Field(default="", max_length=255)
    score: int = Field(..., ge=0, le=100)
    criteria: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)


class TemplateResponse(BaseModel):
    id: int
    name: str
    channel: str
    status: str
    created_at: datetime


class TemplateVersionResponse(BaseModel):
    id: int
    template_id: int
    version: int
    subject: str
    body: str
    cta: str
    prompt: str
    model: str
    status: str
    created_at: datetime


class ExperimentResponse(BaseModel):
    id: int
    name: str
    campaign_id: Optional[int]
    status: str
    goal: str
    traffic_split: int
    variants: list[dict[str, Any]]
    created_at: datetime


def estimate_message_cost(model: str, provider: str, messages: list[dict[str, Any]]) -> float:
    if provider.startswith("local") or model.startswith("local"):
        return 0.0
    body = json.dumps(messages, ensure_ascii=False, default=str)
    approximate_tokens = max(1, round(len(body) / 4))
    cost_per_1k = MODEL_COST_PER_1K.get(model, 0.001)
    return round((approximate_tokens / 1000) * cost_per_1k, 6)


def render_template_text(value: str, lead: dict[str, Any], research: dict[str, Any]) -> str:
    context = {
        "username": lead.get("username") or "",
        "platform": lead.get("platform") or "",
        "email": lead.get("email") or "",
        "industry": research.get("industry") or "",
        "quality_score": research.get("quality_score") or "",
    }

    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        return str(context.get(key, ""))

    return re.sub(r"\{\{\s*([^{}]+?)\s*\}\}", replace, value or "")


async def apply_template_or_experiment(
    conn,
    user_id: int,
    lead: dict[str, Any],
    research: dict[str, Any],
    messages: list[dict[str, Any]],
    template_version_id: Optional[int],
    ab_experiment_id: Optional[int],
) -> tuple[list[dict[str, Any]], Optional[int], Optional[int], Optional[int]]:
    selected_template_id = template_version_id
    selected_experiment_id = ab_experiment_id
    selected_variant_id = None

    if ab_experiment_id is not None:
        rows = await conn.fetch(
            """SELECT v.id AS variant_id, v.template_version_id, v.weight,
                      tv.subject, tv.body, tv.cta, t.channel
               FROM ab_variants v
               JOIN ab_experiments e ON e.id = v.experiment_id AND e.user_id = v.user_id
               JOIN message_template_versions tv
                 ON tv.id = v.template_version_id AND tv.user_id = v.user_id
               JOIN message_templates t ON t.id = tv.template_id AND t.user_id = v.user_id
               WHERE e.id = $1 AND e.user_id = $2 AND e.status = 'active'
               ORDER BY v.id""",
            ab_experiment_id,
            user_id,
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Active A/B experiment or variants not found")
        total_weight = sum(max(1, row["weight"] or 1) for row in rows)
        bucket = int(lead["id"]) % total_weight
        running = 0
        selected = rows[0]
        for row in rows:
            running += max(1, row["weight"] or 1)
            if bucket < running:
                selected = row
                break
        selected_template_id = selected["template_version_id"]
        selected_variant_id = selected["variant_id"]

    if selected_template_id is None:
        return messages, None, selected_experiment_id, selected_variant_id

    template = await conn.fetchrow(
        """SELECT tv.id, tv.subject, tv.body, tv.cta, t.channel
           FROM message_template_versions tv
           JOIN message_templates t ON t.id = tv.template_id AND t.user_id = tv.user_id
           WHERE tv.id = $1 AND tv.user_id = $2 AND tv.status = 'active'""",
        selected_template_id,
        user_id,
    )
    if not template:
        raise HTTPException(status_code=404, detail="Active template version not found")

    rendered = {
        "channel": template["channel"],
        "subject": render_template_text(template["subject"], lead, research),
        "body": render_template_text(template["body"], lead, research),
        "cta": render_template_text(template["cta"], lead, research),
    }
    replaced = []
    used = False
    for message in messages:
        if message["channel"] == template["channel"]:
            replaced.append({**message, **rendered})
            used = True
        else:
            replaced.append(message)
    if not used:
        replaced.append(
            {
                **rendered,
                "personalization_evidence": messages[0].get("personalization_evidence", []) if messages else [],
                "quality_score": 100,
                "risk_flags": [],
            }
        )
    return replaced, selected_template_id, selected_experiment_id, selected_variant_id


@router.post("/templates", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    request: TemplateCreate,
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO message_templates (user_id, name, channel)
               VALUES ($1, $2, $3)
               RETURNING id, name, channel, status, created_at""",
            current_user.id,
            request.name,
            request.channel,
        )
    return TemplateResponse(**dict(row))


@router.post(
    "/templates/{template_id}/versions",
    response_model=TemplateVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_template_version(
    template_id: int,
    request: TemplateVersionCreate,
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        owned = await conn.fetchval(
            "SELECT 1 FROM message_templates WHERE id = $1 AND user_id = $2",
            template_id,
            current_user.id,
        )
        if not owned:
            raise HTTPException(status_code=404, detail="Template not found")
        version = await conn.fetchval(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM message_template_versions WHERE template_id = $1 AND user_id = $2",
            template_id,
            current_user.id,
        )
        row = await conn.fetchrow(
            """INSERT INTO message_template_versions
               (template_id, user_id, version, subject, body, cta, prompt, model, status)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
               RETURNING id, template_id, version, subject, body, cta, prompt, model, status, created_at""",
            template_id,
            current_user.id,
            version,
            request.subject,
            request.body,
            request.cta,
            request.prompt,
            request.model,
            request.status,
        )
    return TemplateVersionResponse(**dict(row))


@router.post("/experiments", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
async def create_experiment(
    request: ExperimentCreate,
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if request.campaign_id is not None:
            owned = await conn.fetchval(
                "SELECT 1 FROM marketing_campaigns WHERE id = $1 AND user_id = $2",
                request.campaign_id,
                current_user.id,
            )
            if not owned:
                raise HTTPException(status_code=404, detail="Campaign not found")
        async with conn.transaction():
            experiment = await conn.fetchrow(
                """INSERT INTO ab_experiments
                   (user_id, name, campaign_id, goal, traffic_split, status)
                   VALUES ($1, $2, $3, $4, $5, 'active')
                   RETURNING id, name, campaign_id, status, goal, traffic_split, created_at""",
                current_user.id,
                request.name,
                request.campaign_id,
                request.goal,
                request.traffic_split,
            )
            variants = []
            for index, variant in enumerate(request.variants):
                template_version_id = int(variant.get("template_version_id") or 0)
                label = str(variant.get("label") or chr(65 + index))[:50]
                weight = int(variant.get("weight") or 1)
                owned_template = await conn.fetchval(
                    "SELECT 1 FROM message_template_versions WHERE id = $1 AND user_id = $2",
                    template_version_id,
                    current_user.id,
                )
                if not owned_template:
                    raise HTTPException(status_code=404, detail=f"Template version {template_version_id} not found")
                row = await conn.fetchrow(
                    """INSERT INTO ab_variants
                       (experiment_id, user_id, label, template_version_id, weight, hypothesis)
                       VALUES ($1, $2, $3, $4, $5, $6)
                       RETURNING id, label, template_version_id, weight, hypothesis""",
                    experiment["id"],
                    current_user.id,
                    label,
                    template_version_id,
                    max(1, weight),
                    str(variant.get("hypothesis") or "")[:1000],
                )
                variants.append(dict(row))
    return ExperimentResponse(**dict(experiment), variants=variants)


@router.post("/prompt-evaluations", status_code=status.HTTP_201_CREATED)
async def create_prompt_evaluation(
    request: PromptEvaluationCreate,
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO prompt_evaluations
               (user_id, name, prompt, model, score, criteria, result)
               VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb)
               RETURNING id, name, model, score, created_at""",
            current_user.id,
            request.name,
            request.prompt,
            request.model,
            request.score,
            json.dumps(request.criteria, ensure_ascii=False),
            json.dumps(request.result, ensure_ascii=False),
        )
    return dict(row)


@router.get("/summary")
async def optimization_summary(
    days: int = Query(30, ge=1, le=365),
    current_user: UserResponse = Depends(get_current_user),
):
    pool = await get_db_pool()
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    async with pool.acquire() as conn:
        overview = await conn.fetchrow(
            """WITH sent_messages AS (
                   SELECT m.*
                   FROM marketing_messages m
                   WHERE m.user_id = $1 AND m.sent_at >= $2
               ),
               replied AS (
                   SELECT DISTINCT s.id
                   FROM sent_messages s
                   JOIN conversations c ON c.user_id = s.user_id AND c.lead_id = s.lead_id
                   JOIN conversation_messages cm
                     ON cm.conversation_id = c.id AND cm.user_id = c.user_id
                   WHERE cm.direction = 'inbound' AND cm.created_at >= s.sent_at
               )
               SELECT COUNT(s.id)::int AS sent,
                      COUNT(r.id)::int AS replies,
                      COUNT(DISTINCT s.lead_id) FILTER (WHERE l.status = 'converted')::int AS conversions,
                      COALESCE(SUM(s.estimated_cost_usd), 0)::float AS message_cost
               FROM sent_messages s
               LEFT JOIN replied r ON r.id = s.id
               LEFT JOIN leads l ON l.id = s.lead_id AND l.user_id = s.user_id""",
            current_user.id,
            since,
        )
        by_variant = await conn.fetch(
            """SELECT e.id AS experiment_id, e.name AS experiment_name,
                      v.label AS variant, COUNT(m.id)::int AS sent,
                      COUNT(DISTINCT cm.id)::int AS replies,
                      COUNT(DISTINCT m.lead_id) FILTER (WHERE l.status = 'converted')::int AS conversions
               FROM ab_experiments e
               JOIN ab_variants v ON v.experiment_id = e.id AND v.user_id = e.user_id
               LEFT JOIN marketing_messages m
                 ON m.ab_variant_id = v.id AND m.user_id = v.user_id AND m.sent_at >= $2
               LEFT JOIN leads l ON l.id = m.lead_id AND l.user_id = m.user_id
               LEFT JOIN conversations c ON c.user_id = m.user_id AND c.lead_id = m.lead_id
               LEFT JOIN conversation_messages cm
                 ON cm.conversation_id = c.id AND cm.user_id = c.user_id
                AND cm.direction = 'inbound' AND cm.created_at >= m.sent_at
               WHERE e.user_id = $1
               GROUP BY e.id, e.name, v.id, v.label
               ORDER BY e.created_at DESC, v.label""",
            current_user.id,
            since,
        )
        by_template = await conn.fetch(
            """SELECT tv.id AS template_version_id,
                      t.name || ' v' || tv.version AS template,
                      COUNT(m.id)::int AS sent,
                      COUNT(DISTINCT cm.id)::int AS replies
               FROM message_template_versions tv
               JOIN message_templates t ON t.id = tv.template_id AND t.user_id = tv.user_id
               LEFT JOIN marketing_messages m
                 ON m.template_version_id = tv.id AND m.user_id = tv.user_id AND m.sent_at >= $2
               LEFT JOIN conversations c ON c.user_id = m.user_id AND c.lead_id = m.lead_id
               LEFT JOIN conversation_messages cm
                 ON cm.conversation_id = c.id AND cm.user_id = c.user_id
                AND cm.direction = 'inbound' AND cm.created_at >= m.sent_at
               WHERE tv.user_id = $1
               GROUP BY tv.id, t.name, tv.version
               ORDER BY sent DESC, tv.created_at DESC
               LIMIT 20""",
            current_user.id,
            since,
        )
        by_model = await conn.fetch(
            """SELECT generation_model AS model, COUNT(*)::int AS messages,
                      COALESCE(SUM(estimated_cost_usd), 0)::float AS cost
               FROM marketing_messages
               WHERE user_id = $1 AND created_at >= $2
               GROUP BY generation_model
               ORDER BY cost DESC, messages DESC""",
            current_user.id,
            since,
        )
        ai_cost = await conn.fetchval(
            """SELECT COALESCE(SUM(
                   ((prompt_tokens + completion_tokens)::numeric / 1000)
                   * CASE
                       WHEN model LIKE 'local%' THEN 0
                       WHEN model = 'meta-llama/llama-3-8b-instruct' THEN 0.0003
                       ELSE 0.001
                     END
               ), 0)::float
               FROM automation_ai_calls
               WHERE user_id = $1 AND created_at >= $2""",
            current_user.id,
            since,
        )
        prompt_evaluations = await conn.fetch(
            """SELECT id, name, model, score, created_at
               FROM prompt_evaluations
               WHERE user_id = $1
               ORDER BY created_at DESC
               LIMIT 10""",
            current_user.id,
        )

    sent = overview["sent"] or 0
    replies = overview["replies"] or 0
    conversions = overview["conversions"] or 0
    return {
        "window_days": days,
        "overview": {
            "sent": sent,
            "replies": replies,
            "conversions": conversions,
            "reply_rate": round(replies / sent * 100, 2) if sent else 0,
            "conversion_rate": round(conversions / sent * 100, 2) if sent else 0,
            "estimated_model_cost_usd": round((overview["message_cost"] or 0) + (ai_cost or 0), 6),
        },
        "by_variant": [
            {
                **dict(row),
                "reply_rate": round((row["replies"] or 0) / row["sent"] * 100, 2) if row["sent"] else 0,
                "conversion_rate": round((row["conversions"] or 0) / row["sent"] * 100, 2) if row["sent"] else 0,
            }
            for row in by_variant
        ],
        "by_template": [
            {
                **dict(row),
                "reply_rate": round((row["replies"] or 0) / row["sent"] * 100, 2) if row["sent"] else 0,
            }
            for row in by_template
        ],
        "by_model": [dict(row) for row in by_model],
        "prompt_evaluations": [dict(row) for row in prompt_evaluations],
    }
