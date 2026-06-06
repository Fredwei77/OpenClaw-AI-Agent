"""Authenticated runtime status for the single-machine workbench."""

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from browser_cluster.manager.browser_pool import get_browser_pool
from scheduler.task_queue import get_task_queue

from .agents import API_KEY, MARKETING_MODEL, _marketing_model_candidates
from .auth import UserResponse, get_current_user, get_db_pool

router = APIRouter()


async def _database_is_ready() -> bool:
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval("SELECT 1") == 1
    except Exception:
        return False


@router.get("/status")
async def get_runtime_status(
    current_user: UserResponse = Depends(get_current_user),
):
    """Return a safe operational snapshot without exposing local secrets."""
    del current_user

    database_ready = await _database_is_ready()
    browser_pool = await get_browser_pool().get_pool_status()
    task_queue = await get_task_queue().get_status()
    browser_ready = bool(getattr(get_browser_pool(), "_started", False))
    queue_ready = bool(task_queue.get("running"))
    healthy = database_ready and browser_ready and queue_ready

    return {
        "status": "healthy" if healthy else "degraded",
        "version": "1.1.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "components": {
            "database": database_ready,
            "browser_pool": browser_ready,
            "task_queue": queue_ready,
        },
        "browser_pool": {
            "total_browsers": browser_pool["total_browsers"],
            "max_browsers": browser_pool["max_browsers"],
            "total_contexts": browser_pool["total_contexts"],
            "active_references": browser_pool["active_references"],
        },
        "task_queue": {
            "running": queue_ready,
            "queue_size": task_queue["queue_size"],
            "active_tasks": task_queue["active_tasks"],
            "max_concurrent": task_queue["max_concurrent"],
            "use_redis": task_queue["use_redis"],
        },
        "ai": {
            "provider": "OpenRouter",
            "configured": bool(API_KEY),
            "marketing_model": MARKETING_MODEL,
            "fallback_models": _marketing_model_candidates()[1:],
            "mode": "online" if API_KEY else "local_fallback",
        },
        "configuration": {
            "database_url": bool(os.getenv("DATABASE_URL")),
            "jwt_secret": bool(os.getenv("JWT_SECRET_KEY")),
            "openrouter_api_key": bool(API_KEY),
            "chrome_user_data_dir": bool(os.getenv("CHROME_USER_DATA_DIR")),
            "scraper_proxy": bool(os.getenv("SCRAPER_PROXY")),
            "demo_mode": os.getenv("DEMO_MODE", "false").lower() == "true",
        },
    }
