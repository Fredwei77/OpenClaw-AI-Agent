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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import auth, agents, tasks, leads, products, analytics

app = FastAPI(title="OpenClaw AI Agent API", version="1.0.0", description="Backend API for Cross-Border Ecommerce Agents")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Dev only - allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(leads.router, prefix="/api/leads", tags=["leads"])
app.include_router(products.router, prefix="/api/products", tags=["products"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])

@app.get("/")
async def root():
    return {"message": "OpenClaw AI Agent Backend API is running."}

if __name__ == "__main__":
    import uvicorn
    # 关闭 reload 防止其生成隔离的 watchdog 线程覆写 asyncio 事件循环的 policy 导致 playwright 无法调度子进程
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
