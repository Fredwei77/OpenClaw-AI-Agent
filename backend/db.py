import os
import json
import re
import asyncpg
from typing import List, Dict, Optional
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv(os.getenv("OPENCLAW_ENV_FILE") or os.path.join(os.path.dirname(__file__), '..', '.env'))

# Database connection pool
_db_pool: Optional[asyncpg.Pool] = None
MAX_REASONABLE_FOLLOWERS = 10_000_000_000


def normalize_followers(value) -> int:
    """Normalize scraped follower counts and cap obviously invalid values."""
    if value is None or isinstance(value, bool):
        return 0
    try:
        if isinstance(value, str):
            match = re.fullmatch(r"\s*([\d,]+(?:\.\d+)?)\s*([KMB])?\s*", value, re.IGNORECASE)
            if not match:
                return 0
            number = float(match.group(1).replace(",", ""))
            suffix = (match.group(2) or "").upper()
            multiplier = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[suffix]
            value = number * multiplier
        count = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return min(max(count, 0), MAX_REASONABLE_FOLLOWERS)


async def get_db_pool() -> asyncpg.Pool:
    """Get or create database connection pool."""
    global _db_pool
    if _db_pool is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL environment variable is not set. Please configure it in .env")
        _db_pool = await asyncpg.create_pool(
            database_url,
            min_size=5,
            max_size=20,
            command_timeout=60
        )
    return _db_pool


async def close_db_pool():
    """Close the database connection pool."""
    global _db_pool
    if _db_pool:
        await _db_pool.close()
        _db_pool = None


async def ensure_runtime_schema():
    """Apply additive schema upgrades required by local desktop updates."""
    pool = await get_db_pool()
    statements = [
        """CREATE TABLE IF NOT EXISTS marketing_campaigns (
               id SERIAL PRIMARY KEY,
               user_id INT NOT NULL,
               name VARCHAR(255) NOT NULL,
               product_context TEXT,
               lead_count INT DEFAULT 0,
               generation_mode VARCHAR(50) DEFAULT 'local_fallback',
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
               updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
           )""",
        "ALTER TABLE marketing_messages ADD COLUMN IF NOT EXISTS campaign_id INT",
        "CREATE INDEX IF NOT EXISTS idx_marketing_messages_campaign_id ON marketing_messages(campaign_id)",
        "CREATE INDEX IF NOT EXISTS idx_marketing_campaigns_user_created_at ON marketing_campaigns(user_id, created_at DESC)",
        """CREATE TABLE IF NOT EXISTS automation_flows (
               id SERIAL PRIMARY KEY,
               user_id INT NOT NULL,
               name VARCHAR(255) NOT NULL,
               description TEXT DEFAULT '',
               trigger_type VARCHAR(100) NOT NULL DEFAULT 'inbound_message',
               trigger_config JSONB NOT NULL DEFAULT '{}'::jsonb,
               definition JSONB NOT NULL DEFAULT '{"steps":[]}'::jsonb,
               status VARCHAR(20) NOT NULL DEFAULT 'draft',
               version INT NOT NULL DEFAULT 1,
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
               updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
           )""",
        """CREATE TABLE IF NOT EXISTS conversations (
               id SERIAL PRIMARY KEY,
               user_id INT NOT NULL,
               lead_id INT,
               channel VARCHAR(50) NOT NULL DEFAULT 'webhook',
               external_id VARCHAR(255),
               status VARCHAR(20) NOT NULL DEFAULT 'open',
               assigned_to INT,
               metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
               last_message_at TIMESTAMP,
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
               updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
           )""",
        """CREATE TABLE IF NOT EXISTS conversation_messages (
               id SERIAL PRIMARY KEY,
               conversation_id INT NOT NULL,
               user_id INT NOT NULL,
               direction VARCHAR(20) NOT NULL,
               message_type VARCHAR(30) NOT NULL DEFAULT 'text',
               content TEXT NOT NULL DEFAULT '',
               status VARCHAR(30) NOT NULL DEFAULT 'received',
               metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
           )""",
        """CREATE TABLE IF NOT EXISTS webhook_events (
               id SERIAL PRIMARY KEY,
               user_id INT NOT NULL,
               event_id VARCHAR(255) NOT NULL,
               event_type VARCHAR(100) NOT NULL,
               channel VARCHAR(50) NOT NULL DEFAULT 'webhook',
               lead_id INT,
               conversation_id INT,
               payload JSONB NOT NULL DEFAULT '{}'::jsonb,
               status VARCHAR(30) NOT NULL DEFAULT 'received',
               error TEXT,
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
               processed_at TIMESTAMP
           )""",
        """CREATE TABLE IF NOT EXISTS automation_runs (
               id SERIAL PRIMARY KEY,
               flow_id INT NOT NULL,
               user_id INT NOT NULL,
               event_id INT,
               conversation_id INT,
               lead_id INT,
               status VARCHAR(30) NOT NULL DEFAULT 'running',
               context JSONB NOT NULL DEFAULT '{}'::jsonb,
               current_step INT NOT NULL DEFAULT 0,
               error TEXT,
               started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
               completed_at TIMESTAMP
           )""",
        """CREATE TABLE IF NOT EXISTS automation_run_steps (
               id SERIAL PRIMARY KEY,
               run_id INT NOT NULL,
               step_index INT NOT NULL,
               step_type VARCHAR(100) NOT NULL,
               status VARCHAR(30) NOT NULL,
               input JSONB NOT NULL DEFAULT '{}'::jsonb,
               output JSONB NOT NULL DEFAULT '{}'::jsonb,
               error TEXT,
               started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
               completed_at TIMESTAMP
           )""",
        """CREATE TABLE IF NOT EXISTS automation_jobs (
               id SERIAL PRIMARY KEY,
               run_id INT NOT NULL,
               user_id INT NOT NULL,
               step_index INT NOT NULL,
               execute_at TIMESTAMP NOT NULL,
               payload JSONB NOT NULL DEFAULT '{}'::jsonb,
               status VARCHAR(30) NOT NULL DEFAULT 'pending',
               attempts INT NOT NULL DEFAULT 0,
               locked_at TIMESTAMP,
               error TEXT,
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
               completed_at TIMESTAMP
           )""",
        """CREATE TABLE IF NOT EXISTS conversation_events (
               id SERIAL PRIMARY KEY,
               conversation_id INT NOT NULL,
               user_id INT NOT NULL,
               event_type VARCHAR(50) NOT NULL,
               actor_type VARCHAR(30) NOT NULL DEFAULT 'system',
               actor_id INT,
               payload JSONB NOT NULL DEFAULT '{}'::jsonb,
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
           )""",
        """CREATE TABLE IF NOT EXISTS automation_settings (
               user_id INT PRIMARY KEY,
               ai_provider VARCHAR(30) NOT NULL DEFAULT 'hybrid',
               ai_model VARCHAR(255) NOT NULL DEFAULT '',
               reply_mode VARCHAR(30) NOT NULL DEFAULT 'review',
               min_confidence NUMERIC(5,4) NOT NULL DEFAULT 0.65,
               handoff_score INT NOT NULL DEFAULT 85,
               max_auto_replies_per_hour INT NOT NULL DEFAULT 5,
               blocked_terms TEXT[] NOT NULL DEFAULT '{}'::text[],
               outbound_webhook_enabled BOOLEAN NOT NULL DEFAULT FALSE,
               outbound_webhook_url TEXT NOT NULL DEFAULT '',
               outbound_webhook_secret TEXT,
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
               updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
           )""",
        """CREATE TABLE IF NOT EXISTS automation_ai_calls (
               id SERIAL PRIMARY KEY,
               user_id INT NOT NULL,
               run_id INT,
               conversation_id INT,
               provider VARCHAR(50) NOT NULL,
               model VARCHAR(255) NOT NULL,
               status VARCHAR(30) NOT NULL,
               prompt_tokens INT NOT NULL DEFAULT 0,
               completion_tokens INT NOT NULL DEFAULT 0,
               latency_ms INT NOT NULL DEFAULT 0,
               output JSONB NOT NULL DEFAULT '{}'::jsonb,
               error TEXT,
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
           )""",
        """CREATE TABLE IF NOT EXISTS outbound_deliveries (
               id SERIAL PRIMARY KEY,
               user_id INT NOT NULL,
               message_id INT NOT NULL,
               callback_url TEXT NOT NULL,
               payload JSONB NOT NULL DEFAULT '{}'::jsonb,
               status VARCHAR(30) NOT NULL DEFAULT 'pending',
               attempts INT NOT NULL DEFAULT 0,
               next_attempt_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
               locked_at TIMESTAMP,
               response_status INT,
               response_body TEXT,
               error TEXT,
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
               completed_at TIMESTAMP
           )""",
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS mode VARCHAR(20) NOT NULL DEFAULT 'automation'",
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS priority VARCHAR(20) NOT NULL DEFAULT 'normal'",
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS unread_count INT NOT NULL DEFAULT 0",
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS intent VARCHAR(50)",
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS intent_confidence NUMERIC(5,4)",
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS ai_summary TEXT",
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS handoff_reason TEXT",
        "ALTER TABLE automation_runs ADD COLUMN IF NOT EXISTS parent_run_id INT",
        "ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS lead_id INT",
        "ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS conversation_id INT",
        "ALTER TABLE automation_jobs ADD COLUMN IF NOT EXISTS locked_at TIMESTAMP",
        "CREATE INDEX IF NOT EXISTS idx_automation_flows_user_status ON automation_flows(user_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_conversations_user_updated_at ON conversations(user_id, updated_at DESC)",
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_user_channel_external
           ON conversations(user_id, channel, external_id) WHERE external_id IS NOT NULL""",
        """CREATE INDEX IF NOT EXISTS idx_conversation_messages_conversation_created
           ON conversation_messages(conversation_id, created_at)""",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_webhook_events_user_event ON webhook_events(user_id, event_id)",
        "CREATE INDEX IF NOT EXISTS idx_automation_runs_user_started ON automation_runs(user_id, started_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_automation_runs_flow_started ON automation_runs(flow_id, started_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_automation_run_steps_run ON automation_run_steps(run_id, step_index)",
        "CREATE INDEX IF NOT EXISTS idx_automation_jobs_due ON automation_jobs(status, execute_at)",
        "CREATE INDEX IF NOT EXISTS idx_conversations_user_mode_updated ON conversations(user_id, mode, updated_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_conversation_events_conversation_created ON conversation_events(conversation_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_automation_runs_parent ON automation_runs(parent_run_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_automation_jobs_run_step ON automation_jobs(run_id, step_index)",
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_automation_messages_run_step
           ON conversation_messages(user_id, (metadata->>'run_id'), (metadata->>'step_index'))
           WHERE metadata->>'source' = 'automation'
             AND metadata ? 'run_id'
             AND metadata ? 'step_index'""",
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_conversation_events_run_type
           ON conversation_events(user_id, event_type, (payload->>'run_id'))
           WHERE payload ? 'run_id'""",
        "CREATE INDEX IF NOT EXISTS idx_automation_ai_calls_user_created ON automation_ai_calls(user_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_outbound_deliveries_due ON outbound_deliveries(status, next_attempt_at)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_outbound_deliveries_message ON outbound_deliveries(message_id)",
    ]
    async with pool.acquire() as conn:
        async with conn.transaction():
            for statement in statements:
                await conn.execute(statement)


@asynccontextmanager
async def get_db_connection():
    """Context manager for database connections from pool."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        yield conn


async def save_leads(leads: List[Dict], user_id: int = None) -> int:
    """
    将采集到的线索批量存入数据库的 leads 表中。
    使用 UPSERT 逻辑根据 platform + username 去重。

    Returns:
        int: 实际新增或更新的线索数量
    """
    if not leads:
        return 0
    if user_id is None:
        raise ValueError("user_id is required when saving leads")

    pool = await get_db_pool()

    inserted_count = 0

    try:
        async with pool.acquire() as conn:
            # Use UPSERT (INSERT ... ON CONFLICT DO UPDATE) for deduplication
            query = """
                INSERT INTO leads (user_id, platform, username, profile_url, email, followers, tags, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, 'new')
                ON CONFLICT (user_id, platform, username)
                DO UPDATE SET
                    profile_url = EXCLUDED.profile_url,
                    email = COALESCE(EXCLUDED.email, leads.email),
                    followers = EXCLUDED.followers,
                    tags = COALESCE(leads.tags, '{}') || EXCLUDED.tags,
                    created_at = CURRENT_TIMESTAMP
            """

            values = [
                (
                    user_id,
                    lead.get('platform', ''),
                    lead.get('username', ''),
                    lead.get('profile_url', ''),
                    lead.get('email', None),
                    normalize_followers(lead.get('followers', 0)),
                    lead.get('tags', [])
                )
                for lead in leads
            ]

            async with conn.transaction():
                await conn.executemany(query, values)
                inserted_count = len(values)

            print(f"[DB] Successfully upserted {inserted_count} leads to the database.")
    except Exception as e:
        print(f"[DB Error] Failed to save leads: {e}")
        raise

    return inserted_count


async def save_leads_batch(leads: List[Dict], user_id: int = None) -> int:
    """
    高性能批量插入线索（使用 executemany 但保留 UPSERT 语义）。
    适用于大量数据的批量导入场景。
    """
    if not leads:
        return 0
    if user_id is None:
        raise ValueError("user_id is required when saving leads")

    pool = await get_db_pool()
    inserted_count = 0

    try:
        async with pool.acquire() as conn:
            query = """
                INSERT INTO leads (user_id, platform, username, profile_url, email, followers, tags, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, 'new')
                ON CONFLICT (user_id, platform, username)
                DO UPDATE SET
                    profile_url = EXCLUDED.profile_url,
                    email = COALESCE(EXCLUDED.email, leads.email),
                    followers = GREATEST(EXCLUDED.followers, leads.followers),
                    tags = COALESCE(leads.tags, '{}') || EXCLUDED.tags
            """

            # Convert to tuple list for executemany
            values = [
                (
                    user_id,
                    lead.get('platform', ''),
                    lead.get('username', ''),
                    lead.get('profile_url', ''),
                    lead.get('email', None),
                    normalize_followers(lead.get('followers', 0)),
                    lead.get('tags', [])
                )
                for lead in leads
            ]

            async with conn.transaction():
                await conn.executemany(query, values)
                inserted_count = len(values)

            print(f"[DB] Batch upserted {inserted_count}/{len(leads)} leads.")
    except Exception as e:
        print(f"[DB Error] Batch save failed: {e}")
        raise

    return inserted_count


async def update_task_status(task_id: int, status: str, result: Dict = None, error: str = None) -> bool:
    """更新任务状态和结果"""
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            query = """
                UPDATE tasks
                SET status = $2,
                    result = COALESCE($3, result),
                    error = $4,
                    completed_at = CASE WHEN $2 IN ('completed', 'failed') THEN CURRENT_TIMESTAMP ELSE completed_at END,
                    started_at = CASE WHEN $2 = 'running' AND started_at IS NULL THEN CURRENT_TIMESTAMP ELSE started_at END
                WHERE id = $1
            """
            await conn.execute(query, task_id, status, result, error)
            return True
    except Exception as e:
        print(f"[DB Error] Failed to update task {task_id}: {e}")
        return False


async def get_task(task_id: int) -> Optional[Dict]:
    """获取任务详情"""
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)
            if row:
                return dict(row)
            return None
    except Exception as e:
        print(f"[DB Error] Failed to get task {task_id}: {e}")
        return None


async def save_lead_research(lead_id: int, user_id: int, metadata: dict, quality_score: int) -> bool:
    """Save research metadata and quality score to a lead."""
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """UPDATE leads
                   SET metadata = $3, quality_score = $4
                   WHERE id = $1 AND user_id = $2""",
                lead_id, user_id, json.dumps(metadata), quality_score
            )
            return True
    except Exception as e:
        print(f"[DB Error] Failed to save lead research for {lead_id}: {e}")
        return False


async def save_marketing_messages(messages: list) -> int:
    """Replace draft messages for the same lead/channel and insert fresh drafts."""
    if not messages:
        return 0
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            count = 0
            async with conn.transaction():
                for msg in messages:
                    if msg.get('campaign_id') is None:
                        await conn.execute(
                            """DELETE FROM marketing_messages
                               WHERE lead_id = $1 AND user_id = $2 AND channel = $3
                                 AND sequence_step = $4 AND status = 'draft' AND campaign_id IS NULL""",
                            msg.get('lead_id'), msg.get('user_id'), msg.get('channel'),
                            msg.get('sequence_step', 1),
                        )
                    await conn.execute(
                        """INSERT INTO marketing_messages (lead_id, user_id, campaign_id, channel, subject, body, cta, sequence_step, status)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                        msg.get('lead_id'), msg.get('user_id'), msg.get('campaign_id'),
                        msg.get('channel'), msg.get('subject', ''), msg.get('body', ''),
                        msg.get('cta', ''), msg.get('sequence_step', 1), msg.get('status', 'draft')
                    )
                    count += 1
            return count
    except Exception as e:
        print(f"[DB Error] Failed to save marketing messages: {e}")
        raise


async def create_marketing_campaign(
    user_id: int,
    name: str,
    product_context: str,
    lead_count: int,
    generation_mode: str,
) -> int:
    """Create a persisted pipeline batch for the recent campaigns workspace."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """INSERT INTO marketing_campaigns (user_id, name, product_context, lead_count, generation_mode)
               VALUES ($1, $2, $3, $4, $5)
               RETURNING id""",
            user_id,
            name,
            product_context,
            lead_count,
            generation_mode,
        )
