import os
import sys
import asyncio
import logging
from contextlib import asynccontextmanager

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 修复 Windows 平台下 Uvicorn 默认选用 SelectorEventLoop 导致 Playwright 无法启动 Subprocess 的缺陷
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from dotenv import load_dotenv

# 确保能读到根目录级别的自定义包（修复 Electron 作为外部工作目录拉起时的 ModuleNotFoundError）
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env variables from the project root .env file
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import ValidationError
from api import auth, agents, tasks, leads, products, analytics
from middleware import GlobalResponseMiddleware, http_exception_handler, validation_exception_handler, generic_exception_handler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown lifecycle."""
    # Startup
    from db import get_db_pool
    try:
        await get_db_pool()
        logger.info("Database pool initialized")
    except Exception as e:
        logger.error(f"Database pool initialization failed: {e}")

    try:
        from browser_cluster.manager.browser_pool import init_browser_pool
        await init_browser_pool()
        logger.info("Browser pool initialized")
    except Exception as e:
        logger.error(f"Browser pool initialization failed: {e}")

    try:
        from scheduler.task_queue import init_task_queue
        await init_task_queue()
        logger.info("Task queue initialized")
    except Exception as e:
        logger.error(f"Task queue initialization failed: {e}")

    # Initialize browser-harness (optional, non-fatal)
    try:
        from browser_cluster.manager.browser_harness_manager import init_harness_manager
        harness_ok = await init_harness_manager()
        if harness_ok:
            logger.info("Browser harness initialized")
        else:
            logger.info("Browser harness not available (Chrome not running with debug port)")
    except Exception as e:
        logger.info(f"Browser harness not available: {e}")

    yield

    # Shutdown
    from db import close_db_pool
    try:
        await close_db_pool()
        logger.info("Database pool closed")
    except Exception as e:
        logger.error(f"Database pool cleanup failed: {e}")

    try:
        from browser_cluster.manager.browser_pool import shutdown_browser_pool
        await shutdown_browser_pool()
        logger.info("Browser pool closed")
    except Exception as e:
        logger.error(f"Browser pool cleanup failed: {e}")

    try:
        from browser_cluster.manager.browser_harness_manager import shutdown_harness_manager
        await shutdown_harness_manager()
        logger.info("Browser harness closed")
    except Exception as e:
        logger.error(f"Browser harness cleanup failed: {e}")

    try:
        from scheduler.task_queue import shutdown_task_queue
        await shutdown_task_queue()
        logger.info("Task queue closed")
    except Exception as e:
        logger.error(f"Task queue cleanup failed: {e}")

    try:
        from scheduler.task_queue import close_redis_client
        await close_redis_client()
        logger.info("Redis client closed")
    except Exception as e:
        logger.error(f"Redis client cleanup failed: {e}")


app = FastAPI(title="OpenClaw AI Agent API", version="1.0.0", description="Backend API for Cross-Border Ecommerce Agents", lifespan=lifespan)

# CORS configuration - configurable via environment variables
# For production, set ALLOWED_ORIGINS to specific domains
_allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173")
allowed_origins = [origin.strip() for origin in _allowed_origins.split(",") if origin.strip()]

# Development mode allows more permissive CORS if not configured
environment = os.getenv("ENVIRONMENT", "development")
if environment == "development" and "*" not in _allowed_origins:
    # In dev mode, also allow the frontend dev server
    _dev_origins = {
        "http://localhost:5173", "http://localhost:3000",
        "http://127.0.0.1:5173", "http://127.0.0.1:3000",
    }
    allowed_origins = list(set(allowed_origins) | _dev_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add global response middleware
app.add_middleware(GlobalResponseMiddleware)

# Register exception handlers
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(ValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(leads.router, prefix="/api/leads", tags=["leads"])
app.include_router(products.router, prefix="/api/products", tags=["products"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])


@app.get("/")
async def root():
    return {"message": "OpenClaw AI Agent Backend API is running."}


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development")
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    from monitoring.metrics import get_metrics_collector

    collector = get_metrics_collector()

    # Update browser pool metrics if available
    try:
        from browser_cluster.manager.browser_pool import get_browser_pool
        pool = get_browser_pool()
        status = await pool.get_pool_status()
        collector.update_browser_pool(
            browsers=status.get("total_browsers", 0),
            contexts=status.get("total_contexts", 0)
        )
    except Exception as e:
        logger.warning(f"Failed to update browser pool metrics: {e}")

    return Response(
        content=collector.get_metrics(),
        media_type=collector.get_content_type()
    )


if __name__ == "__main__":
    import uvicorn
    # 关闭 reload 防止其生成隔离的 watchdog 线程覆写 asyncio 事件循环的 policy 导致 playwright 无法调度子进程
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
