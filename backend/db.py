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
