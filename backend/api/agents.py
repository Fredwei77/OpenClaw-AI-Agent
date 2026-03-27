from fastapi import APIRouter
import os
from pydantic import BaseModel
from openai import AsyncOpenAI

router = APIRouter()

# OpenRouter 的专用配置
API_KEY = os.getenv("OPENROUTER_API_KEY", "sk-or-v1-your-key-here")
BASE_URL = "https://openrouter.ai/api/v1"

class ChatRequest(BaseModel):
    prompt: str

@router.post("/test-llm")
async def test_llm(request: ChatRequest):
    """通过 OpenRouter 测试 LLM 连通性"""
    try:
        # OpenRouter 完全兼容 OpenAI 的 SDK 客户端
        client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
        
        response = await client.chat.completions.create(
            # OpenRouter 上免费或者常用的测试模型，建议使用 google/gemini-2.5-flash 或 meta-llama/llama-3.1-8b-instruct
            # 您可以换成任何 OpenRouter 支持的模型 ID
            model="google/gemini-2.5-flash",
            messages=[
                {"role": "system", "content": "You are a helpful assistant for cross-border e-commerce."},
                {"role": "user", "content": request.prompt}
            ],
            # OpenRouter 专属 headers 建议设置（可选，用于在后台统计标识）
            extra_headers={
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "OpenClaw AI Agent",
            }
        )
        return {"status": "success", "reply": response.choices[0].message.content}
    except Exception as e:
        return {"status": "error", "message": f"OpenRouter API call failed: {str(e)}"}

@router.get("/")
async def get_agents():
    return {"message": "List of available agents"}

# 为了正确引入外部包
import sys
from browser_cluster.manager.browser_manager import BrowserManager
from agents.lead_agent.lead_agent import LeadAgent

class ScrapeRequest(BaseModel):
    keyword: str = "fitness equipment"
    platform: str = "x"

@router.post("/test-scraper")
async def test_scraper(request: ScrapeRequest):
    """触发 LeadAgent 进行真实的自动化爬取抓取测试"""
    try:
        if sys.platform == "win32":
            import asyncio
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
        user_data_dir = os.getenv("CHROME_USER_DATA_DIR")
        proxy_url = os.getenv("SCRAPER_PROXY")
        proxy_config = None
        if proxy_url:
            # Assuming format: http://user:pass@host:port or http://host:port
            proxy_config = {"host": proxy_url}
            
        # 初始化浏览器管理器，注入用户目录和代理配置
        manager = BrowserManager(user_data_dir=user_data_dir, proxy=proxy_config)
        await manager.start()
        
        # 修正: BaseAgent 需要明确传递 name 参数
        agent = LeadAgent(name="LeadAgent", browser_manager=manager, db=None)
        
        task_payload = {
            "id": "test_scrape_1",
            "keyword": request.keyword,
            "platform": request.platform
        }
        
        # 执行爬虫逻辑并在内部完成入库
        results = await agent.run(task_payload)
        
        # 修正: BrowserManager 的资源释放应调用 close()
        await manager.close()
        
        return {"status": "success", "leads_found": len(results), "data": results}
    except Exception as e:
        import traceback
        err_str = traceback.format_exc()
        try:
            with open("error.log", "w", encoding="utf-8") as f:
                f.write(err_str)
        except:
            pass
        return {"status": "error", "message": f"Scraping workflow failed: {repr(e)}"}
