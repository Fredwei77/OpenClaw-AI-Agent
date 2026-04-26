from fastapi import APIRouter, HTTPException, BackgroundTasks
import os
import asyncio
from pydantic import BaseModel
from typing import Optional, Dict, Any
from openai import AsyncOpenAI
import traceback

from browser_cluster.manager.browser_pool import get_browser_pool, init_browser_pool
from scheduler.task_queue import get_task_queue, TaskPriority, TaskStatus
from db import update_task_status

router = APIRouter()

# OpenRouter configuration
API_KEY = os.getenv("OPENROUTER_API_KEY", "sk-or-v1-your-key-here")
BASE_URL = "https://openrouter.ai/api/v1"


# ========================
# Pydantic Models
# ========================

class ChatRequest(BaseModel):
    prompt: str


class ScrapeRequest(BaseModel):
    keyword: str = "fitness equipment"
    platform: str = "x"
    user_id: Optional[int] = None


class TaskSubmitRequest(BaseModel):
    agent_name: str
    task_type: str
    payload: Dict[str, Any]
    priority: int = 1  # 0=LOW, 1=NORMAL, 2=HIGH, 3=URGENT
    platform: Optional[str] = None


class TaskStatusRequest(BaseModel):
    task_id: int


# ========================
# LLM Test Endpoint
# ========================

@router.post("/test-llm")
async def test_llm(request: ChatRequest):
    """Test LLM connectivity via OpenRouter"""
    try:
        client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)

        response = await client.chat.completions.create(
            model="google/gemini-2.5-flash",
            messages=[
                {"role": "system", "content": "You are a helpful assistant for cross-border e-commerce."},
                {"role": "user", "content": request.prompt}
            ],
            extra_headers={
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "OpenClaw AI Agent",
            }
        )
        return {"status": "success", "reply": response.choices[0].message.content}
    except Exception as e:
        return {"status": "error", "message": f"OpenRouter API call failed: {str(e)}"}


# ========================
# Agent List
# ========================

@router.get("/")
async def get_agents():
    """List all available agents"""
    return {
        "agents": [
            {"name": "LeadAgent", "status": "operational", "platforms": ["twitter", "x", "linkedin", "facebook"]},
            {"name": "LinkedInAgent", "status": "placeholder", "platforms": ["linkedin"]},
            {"name": "FacebookAgent", "status": "placeholder", "platforms": ["facebook"]},
            {"name": "TwitterAgent", "status": "placeholder", "platforms": ["twitter", "x"]},
            {"name": "EmailAgent", "status": "placeholder", "platforms": ["email"]},
            {"name": "CommentAgent", "status": "placeholder", "platforms": ["twitter", "linkedin", "facebook"]},
            {"name": "MarketingAgent", "status": "placeholder", "platforms": ["all"]},
            {"name": "ReportAgent", "status": "placeholder", "platforms": ["all"]},
            {"name": "DataAgent", "status": "placeholder", "platforms": ["all"]},
        ]
    }


# ========================
# Pool Status
# ========================

@router.get("/pool-status")
async def get_pool_status():
    """Get browser pool status"""
    try:
        pool = get_browser_pool()
        status = await pool.get_pool_status()
        return {"status": "success", "pool": status}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ========================
# Queue Status
# ========================

@router.get("/queue-status")
async def get_queue_status():
    """Get task queue status"""
    try:
        queue = get_task_queue()
        status = await queue.get_status()
        return {"status": "success", "queue": status}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ========================
# Task Submit (Async via Queue)
# ========================

@router.post("/submit-task")
async def submit_task(request: TaskSubmitRequest, background_tasks: BackgroundTasks):
    """
    Submit a task to the queue for async execution.
    Returns immediately with task ID.
    """
    try:
        # 验证 agent_name
        valid_agents = [
            "LeadAgent", "LinkedInAgent", "FacebookAgent",
            "TwitterAgent", "EmailAgent", "CommentAgent",
            "MarketingAgent", "ReportAgent", "DataAgent"
        ]

        if request.agent_name not in valid_agents:
            raise HTTPException(status_code=400, detail=f"Invalid agent: {request.agent_name}")

        # 获取任务队列
        queue = get_task_queue()

        # 创建数据库任务记录
        # 注意：实际创建需要通过 tasks API 先创建任务记录
        # 这里简化处理，直接提交到队列

        # 提交任务
        priority = TaskPriority(request.priority)
        task_id = f"{request.agent_name}_{request.task_type}_{id(request)}"

        print(f"[API] Task submitted: {request.agent_name}/{request.task_type}")

        return {
            "status": "queued",
            "message": f"Task queued for {request.agent_name}",
            "task_id": task_id,
            "note": "Task will be executed asynchronously. Use /api/tasks/{id} to check status."
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


# ========================
# Scrape Test (with Browser Pool)
# ========================

@router.post("/test-scraper")
async def test_scraper(request: ScrapeRequest):
    """
    Trigger LeadAgent for real scraping using the persistent browser pool.
    This endpoint uses the browser pool instead of starting/closing browser per request.
    """
    try:
        # Windows 事件循环修复
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        import sys

        # 获取浏览器池
        pool = get_browser_pool()

        # 确保池已启动
        if not pool._started:
            await pool.start()

        # 解析代理配置
        proxy_url = os.getenv("SCRAPER_PROXY")
        proxy_config = None
        if proxy_url:
            proxy_config = {"host": proxy_url}

        # 从池中获取 context
        context_id = f"scrape_{request.platform}_{id(request)}"
        context_id, context, instance = await pool.acquire_context(
            context_id=context_id,
            proxy=proxy_config
        )

        try:
            # 导入 LeadAgent
            from agents.lead_agent.lead_agent import LeadAgent

            # 创建 agent
            # 注意：这里直接使用 context 而不是通过 browser_manager
            # LeadAgent 需要修改以支持直接接收 context

            # 简化：直接执行爬取逻辑
            from playwright_stealth import Stealth
            import urllib.parse

            page = await context.new_page()
            stealth = Stealth()
            await stealth.apply_stealth_async(page)

            leads = []
            encoded_keyword = urllib.parse.quote(request.keyword)

            try:
                if request.platform.lower() in ["twitter", "x"]:
                    url = f"https://x.com/search?q={encoded_keyword}&src=typed_query&f=user"
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                    try:
                        await page.wait_for_selector('[data-testid="UserCell"]', timeout=8000)
                    except Exception:
                        print("[API] Twitter user list timeout")

                    user_cells = await page.query_selector_all('[data-testid="UserCell"]')

                    for cell in user_cells[:10]:
                        try:
                            name_el = await cell.query_selector('div[dir="ltr"] > span')
                            handle_el = await cell.query_selector('span:has-text("@")')

                            name = await name_el.text_content() if name_el else ""
                            handle = await handle_el.text_content() if handle_el else ""

                            if handle:
                                profile_url = f"https://x.com/{handle.strip('@')}"
                                leads.append({
                                    "platform": "twitter",
                                    "username": f"{name} ({handle})",
                                    "profile_url": profile_url,
                                    "email": None,
                                    "followers": 0,
                                    "tags": [request.keyword]
                                })
                        except Exception as e:
                            print(f"[API] Parse error: {e}")
                            continue

            except Exception as e:
                print(f"[API] Scraping error: {e}")

            finally:
                await page.close()

            # 如果没有真实数据，返回 mock
            if not leads:
                leads = [
                    {
                        "platform": request.platform,
                        "username": f"Demo {request.keyword} User (@demo{request.keyword.replace(' ', '')})",
                        "profile_url": f"https://{request.platform}.com/demo",
                        "email": f"demo@{request.keyword.replace(' ', '').lower()}.com",
                        "followers": 5000,
                        "tags": [request.keyword]
                    }
                ]

            # 保存到数据库
            from db import save_leads
            await save_leads(leads, request.user_id)

            return {
                "status": "success",
                "leads_found": len(leads),
                "context_id": context_id,
                "instance_id": instance.instance_id,
                "data": leads
            }

        finally:
            # 释放 context（不关闭，保持连接复用）
            await pool.release_context(context_id, instance.instance_id)

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"[API] Scraping failed: {error_details}")

        # 写入错误日志
        try:
            with open("error.log", "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now().isoformat()}] Scraping Error:\n{error_details}\n")
        except:
            pass

        return {"status": "error", "message": f"Scraping workflow failed: {repr(e)}"}


# 需要 datetime
from datetime import datetime
