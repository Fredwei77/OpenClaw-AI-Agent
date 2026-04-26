import os
import asyncpg
from typing import List, Dict, Optional
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Database connection pool
_db_pool: Optional[asyncpg.Pool] = None


async def get_db_pool() -> asyncpg.Pool:
    """Get or create database connection pool."""
    global _db_pool
    if _db_pool is None:
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:openclaw@localhost:5432/openclaw_db")
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

    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:openclaw@localhost:5432/openclaw_db")

    try:
        pool = await get_db_pool()
    except Exception as e:
        print(f"[DB Error] Cannot connect to database: {e}")
        return 0

    inserted_count = 0

    try:
        async with pool.acquire() as conn:
            # Use UPSERT (INSERT ... ON CONFLICT DO UPDATE) for deduplication
            query = """
                INSERT INTO leads (user_id, platform, username, profile_url, email, followers, tags, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, 'new')
                ON CONFLICT (platform, username)
                DO UPDATE SET
                    profile_url = EXCLUDED.profile_url,
                    email = COALESCE(EXCLUDED.email, leads.email),
                    followers = EXCLUDED.followers,
                    tags = leads.tags || EXCLUDED.tags,
                    created_at = CURRENT_TIMESTAMP
            """

            async with conn.transaction():
                for lead in leads:
                    result = await conn.execute(
                        query,
                        user_id,
                        lead.get('platform', ''),
                        lead.get('username', ''),
                        lead.get('profile_url', ''),
                        lead.get('email', None),
                        lead.get('followers', 0),
                        lead.get('tags', [])
                    )
                    if result.endswith('1'):
                        inserted_count += 1

            print(f"[DB] Successfully upserted {inserted_count} leads to the database.")
    except Exception as e:
        print(f"[DB Error] Failed to save leads: {e}")

    return inserted_count


async def save_leads_batch(leads: List[Dict], user_id: int = None) -> int:
    """
    高性能批量插入线索（使用 executemany 但保留 UPSERT 语义）。
    适用于大量数据的批量导入场景。
    """
    if not leads:
        return 0

    pool = await get_db_pool()
    inserted_count = 0

    try:
        async with pool.acquire() as conn:
            query = """
                INSERT INTO leads (user_id, platform, username, profile_url, email, followers, tags, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, 'new')
                ON CONFLICT (platform, username)
                DO UPDATE SET
                    profile_url = EXCLUDED.profile_url,
                    email = COALESCE(EXCLUDED.email, leads.email),
                    followers = GREATEST(EXCLUDED.followers, leads.followers),
                    tags = leads.tags || EXCLUDED.tags
            """

            # Convert to tuple list for executemany
            values = [
                (
                    user_id,
                    lead.get('platform', ''),
                    lead.get('username', ''),
                    lead.get('profile_url', ''),
                    lead.get('email', None),
                    lead.get('followers', 0),
                    lead.get('tags', [])
                )
                for lead in leads
            ]

            async with conn.transaction():
                results = await conn.executemany(query, values)
                inserted_count = sum(1 for r in results if r.endswith('1'))

            print(f"[DB] Batch upserted {inserted_count}/{len(leads)} leads.")
    except Exception as e:
        print(f"[DB Error] Batch save failed: {e}")

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
