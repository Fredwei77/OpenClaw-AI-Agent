import os
import sys
import asyncio

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
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError
from api import auth, agents, tasks, leads, products, analytics
from middleware import GlobalResponseMiddleware, http_exception_handler, validation_exception_handler, generic_exception_handler

app = FastAPI(title="OpenClaw AI Agent API", version="1.0.0", description="Backend API for Cross-Border Ecommerce Agents")

# CORS configuration - configurable via environment variables
# For production, set ALLOWED_ORIGINS to specific domains
_allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173")
allowed_origins = [origin.strip() for origin in _allowed_origins.split(",") if origin.strip()]

# Development mode allows more permissive CORS if not configured
environment = os.getenv("ENVIRONMENT", "development")
if environment == "development" and "*" not in _allowed_origins:
    # In dev mode, also allow the frontend dev server
    allowed_origins.extend([
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000"
    ])
    allowed_origins = list(set(allowed_origins))  # Remove duplicates

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


@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup."""
    # Import and initialize database pool
    from db import get_db_pool
    try:
        await get_db_pool()
        print("[Startup] Database pool initialized")
    except Exception as e:
        print(f"[Startup] Warning: Database pool initialization failed: {e}")

    # Import and initialize browser pool
    try:
        from browser_cluster.manager.browser_pool import init_browser_pool
        await init_browser_pool()
        print("[Startup] Browser pool initialized")
    except Exception as e:
        print(f"[Startup] Warning: Browser pool initialization failed: {e}")

    # Import and initialize task queue
    try:
        from scheduler.task_queue import init_task_queue
        await init_task_queue()
        print("[Startup] Task queue initialized")
    except Exception as e:
        print(f"[Startup] Warning: Task queue initialization failed: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown."""
    from db import close_db_pool
    try:
        await close_db_pool()
        print("[Shutdown] Database pool closed")
    except Exception as e:
        print(f"[Shutdown] Warning: Database pool cleanup failed: {e}")

    # Close browser pool
    try:
        from browser_cluster.manager.browser_pool import shutdown_browser_pool
        await shutdown_browser_pool()
        print("[Shutdown] Browser pool closed")
    except Exception as e:
        print(f"[Shutdown] Warning: Browser pool cleanup failed: {e}")

    # Close task queue
    try:
        from scheduler.task_queue import shutdown_task_queue
        await shutdown_task_queue()
        print("[Shutdown] Task queue closed")
    except Exception as e:
        print(f"[Shutdown] Warning: Task queue cleanup failed: {e}")

    # Close Redis client
    try:
        from scheduler.task_queue import close_redis_client
        await close_redis_client()
        print("[Shutdown] Redis client closed")
    except Exception as e:
        print(f"[Shutdown] Warning: Redis client cleanup failed: {e}")


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
    except Exception:
        pass

    return Response(
        content=collector.get_metrics(),
        media_type=collector.get_content_type()
    )


if __name__ == "__main__":
    import uvicorn
    # 关闭 reload 防止其生成隔离的 watchdog 线程覆写 asyncio 事件循环的 policy 导致 playwright 无法调度子进程
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
