from fastapi import APIRouter, HTTPException, Depends
import os
import asyncio
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from openai import AsyncOpenAI
import traceback

from browser_cluster.manager.browser_pool import get_browser_pool
from scheduler.task_queue import get_task_queue, TaskPriority
from .auth import get_current_user

router = APIRouter()

# OpenRouter configuration
API_KEY = os.getenv("OPENROUTER_API_KEY", "")
BASE_URL = "https://openrouter.ai/api/v1"

# Module-level reusable client (created lazily on first use)
_llm_client: Optional[AsyncOpenAI] = None


def _get_llm_client() -> AsyncOpenAI:
    """Get or create a shared AsyncOpenAI client."""
    global _llm_client
    if _llm_client is None:
        if not API_KEY:
            raise RuntimeError("OPENROUTER_API_KEY not configured")
        _llm_client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    return _llm_client


# ========================
# Pydantic Models
# ========================

class ChatRequest(BaseModel):
    prompt: str
    language: str = "en"


class ScrapeRequest(BaseModel):
    keyword: str = "fitness equipment"
    platform: str = "x"
    user_id: Optional[int] = None
    # 高级选项
    use_proxy: bool = False  # 是否使用代理
    store_domain: Optional[str] = None  # Shopify 店铺域名（如 mystore.myshopify.com）
    cookies: Optional[Dict[str, str]] = None  # 可选的登录态 Cookie
    # 扩展过滤参数
    geography: str = "all"  # 目标地区: all, us, uk, ca, au, de, fr, jp, sg
    follower_range: str = "all"  # 粉丝规模: all, 0-1k, 1k-10k, 10k-50k, 50k-100k, 100k+
    content_type: str = "all"  # 账号类型: all, influencer, business, creator, reseller
    max_results: int = 50  # 最大结果数量


class TaskSubmitRequest(BaseModel):
    agent_name: str
    task_type: str
    payload: Dict[str, Any]
    priority: int = 1  # 0=LOW, 1=NORMAL, 2=HIGH, 3=URGENT
    platform: Optional[str] = None


class TaskStatusRequest(BaseModel):
    task_id: int


class MarketingPipelineRequest(BaseModel):
    leads: list
    product_context: str = ""
    language: str = "en"


# ========================
# LLM Test Endpoint
# ========================

@router.post("/test-llm")
async def test_llm(request: ChatRequest):
    """Test LLM connectivity via OpenRouter"""
    # 检查 API Key 是否配置
    if not API_KEY or API_KEY == "sk-or-v1-your-key-here":
        return {
            "status": "error",
            "message": "OpenRouter API key not configured. Please set OPENROUTER_API_KEY in .env file. Get your key at https://openrouter.ai/keys"
        }

    try:
        client = _get_llm_client()

        lang = request.language if request.language in ("zh", "en") else "en"
        system_prompt = (
            "You are a helpful assistant for cross-border e-commerce. "
            "Always respond in the same language as the user's message. "
            "Use clean plain text or markdown formatting. "
            "Do NOT translate the user's input into another language."
        )

        response = await client.chat.completions.create(
            model="meta-llama/llama-3-8b-instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.prompt}
            ],
            extra_headers={
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "OpenClaw AI Agent",
            }
        )
        return {"status": "success", "reply": response.choices[0].message.content}
    except Exception as e:
        error_str = str(e)
        # 提供更友好的错误提示
        if "401" in error_str or "authentication" in error_str.lower():
            return {
                "status": "error",
                "message": f"OpenRouter authentication failed. Please check your API key at https://openrouter.ai/keys. Error: {error_str}"
            }
        elif "connection" in error_str.lower() or "timeout" in error_str.lower():
            return {
                "status": "error",
                "message": f"Failed to connect to OpenRouter. Please check your internet connection. Error: {error_str}"
            }
        else:
            return {"status": "error", "message": f"OpenRouter API call failed: {error_str}"}


# ========================
# Agent List
# ========================

@router.get("/")
async def get_agents():
    """List all available agents"""
    return {
        "agents": [
            {"name": "LeadAgent", "status": "operational", "platforms": ["twitter", "x", "linkedin", "tiktok", "facebook", "instagram", "shopify"]},
            {"name": "LinkedInAgent", "status": "placeholder", "platforms": ["linkedin"]},
            {"name": "FacebookAgent", "status": "placeholder", "platforms": ["facebook"]},
            {"name": "TwitterAgent", "status": "placeholder", "platforms": ["twitter", "x"]},
            {"name": "TikTokAgent", "status": "operational", "platforms": ["tiktok"]},
            {"name": "EmailAgent", "status": "placeholder", "platforms": ["email"]},
            {"name": "CommentAgent", "status": "placeholder", "platforms": ["twitter", "linkedin", "facebook"]},
            {"name": "MarketingAgent", "status": "placeholder", "platforms": ["all"]},
            {"name": "ReportAgent", "status": "placeholder", "platforms": ["all"]},
            {"name": "DataAgent", "status": "placeholder", "platforms": ["all"]},
            {"name": "ShopifyAgent", "status": "placeholder", "platforms": ["shopify"]},
            {"name": "AdsAgent", "status": "placeholder", "platforms": ["facebook", "google"]},
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
async def submit_task(
    request: TaskSubmitRequest,
    current_user=Depends(get_current_user)
):
    """
    Submit a task to the queue for async execution.
    Creates a database record and enqueues for immediate execution.
    """
    import json

    valid_agents = [
        "LeadAgent", "LinkedInAgent", "FacebookAgent",
        "TwitterAgent", "EmailAgent", "CommentAgent",
        "MarketingAgent", "ReportAgent", "DataAgent",
        "HarnessAgent"
    ]

    if request.agent_name not in valid_agents:
        raise HTTPException(status_code=400, detail=f"Invalid agent: {request.agent_name}")

    try:
        from db import get_db_pool as _get_pool
        pool = await _get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO tasks (agent_name, task_type, payload, status, user_id)
                   VALUES ($1, $2, $3, 'pending', $4)
                   RETURNING id""",
                request.agent_name, request.task_type, json.dumps(request.payload), current_user.id
            )

        task_db_id = row['id']
        queue = get_task_queue()
        await queue.submit_task(
            task_id=task_db_id,
            user_id=current_user.id,
            agent_name=request.agent_name,
            task_type=request.task_type,
            payload=request.payload,
            priority=TaskPriority(request.priority),
            platform=request.platform
        )

        return {
            "status": "queued",
            "message": f"Task queued for {request.agent_name}",
            "task_id": task_db_id,
            "note": "Task will be executed asynchronously. Use /api/tasks/{id} to check status."
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit task: {str(e)}")


# ========================
# Scrape Test (with Browser Pool)
# ========================

def _match_geography(lead: dict, geo: str) -> bool:
    """根据地区过滤线索"""
    # 地区映射：关键词匹配
    geo_keywords = {
        "us": ["usa", "united states", "america", "us ", " u.s."],
        "uk": ["uk", "united kingdom", "britain", "london"],
        "ca": ["canada", "toronto", "vancouver"],
        "au": ["australia", "sydney", "melbourne"],
        "de": ["germany", "deutschland", "berlin"],
        "fr": ["france", "paris", "français"],
        "jp": ["japan", "tokyo", "日本語"],
        "sg": ["singapore", "sg", "singaporean"],
    }
    geo_tags = lead.get("tags", [])
    username = lead.get("username", "").lower()
    profile_url = lead.get("profile_url", "").lower()

    if geo not in geo_keywords:
        return True

    keywords = geo_keywords[geo]
    for tag in geo_tags:
        tag_lower = tag.lower()
        for kw in keywords:
            if kw in tag_lower:
                return True
    for kw in keywords:
        if kw in username or kw in profile_url:
            return True
    return False


def _match_follower_range(lead: dict, follower_range: str) -> bool:
    """根据粉丝规模过滤线索"""
    followers = lead.get("followers", 0)
    range_map = {
        "0-1k": (0, 1000),
        "1k-10k": (1000, 10000),
        "10k-50k": (10000, 50000),
        "50k-100k": (50000, 100000),
        "100k+": (100000, float("inf")),
    }
    if follower_range not in range_map:
        return True
    low, high = range_map[follower_range]
    return low <= followers < high


def _match_content_type(lead: dict, content_type: str) -> bool:
    """根据账号类型过滤线索"""
    if content_type == "all":
        return True
    tags = [t.lower() for t in lead.get("tags", [])]
    if content_type == "influencer":
        return any(t in tags for t in ["influencer", "kOL", "creator", "verified", "expert"])
    elif content_type == "business":
        return any(t in tags for t in ["business", "company", "brand", "store", "shop"])
    elif content_type == "creator":
        return any(t in tags for t in ["creator", "content", "youtuber", "streamer"])
    elif content_type == "reseller":
        return any(t in tags for t in ["reseller", "wholesale", "dropship", "supplier"])
    return True


async def _scrape_tiktok(page, keyword: str) -> list:
    """Scrape TikTok for user profiles matching keyword"""
    import urllib.parse
    leads = []
    encoded_keyword = urllib.parse.quote(keyword)

    try:
        url = f"https://www.tiktok.com/search/user?keyword={encoded_keyword}"
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)

        # Wait for results
        try:
            await page.wait_for_selector('[data-e2e="search-user-item"]', timeout=8000)
        except Exception:
            print("[API] TikTok: waiting for results timeout")

        # Extract user cards
        user_cells = await page.query_selector_all('[data-e2e="search-user-item"]')
        for cell in user_cells[:20]:
            try:
                username_elem = await cell.query_selector('a')
                name_elem = await cell.query_selector('[data-e2e="search-user-name"]')

                username = await username_elem.text_content() if username_elem else ""
                href = await username_elem.get_attribute('href') if username_elem else ""
                name = await name_elem.text_content() if name_elem else ""

                if username and href:
                    profile_url = href if href.startswith('http') else f"https://www.tiktok.com{href}"
                    username = username.strip().replace('@', '')

                    leads.append({
                        "platform": "tiktok",
                        "username": username or name,
                        "profile_url": profile_url,
                        "email": None,
                        "followers": 0,
                        "tags": [keyword, "tiktok"]
                    })
            except Exception:
                continue

        print(f"[API] TikTok: extracted {len(leads)} users")

    except Exception as e:
        print(f"[API] TikTok: error: {e}")

    return leads


async def _scrape_facebook(page, keyword: str) -> list:
    """Scrape Facebook for pages/groups matching keyword"""
    import urllib.parse
    leads = []
    encoded_keyword = urllib.parse.quote(keyword)

    try:
        # Search for pages
        url = f"https://www.facebook.com/search/pages?q={encoded_keyword}"
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)

        # Try to wait for results
        try:
            await page.wait_for_selector('[role="article"]', timeout=8000)
        except Exception:
            print("[API] Facebook: waiting for results timeout")

        # Extract page cards
        articles = await page.query_selector_all('[role="article"]')
        for article in articles[:20]:
            try:
                link_elem = await article.query_selector('a')
                name_elem = await article.query_selector('span')

                name = await name_elem.text_content() if name_elem else ""
                href = await link_elem.get_attribute('href') if link_elem else ""

                if name and href:
                    profile_url = href if href.startswith('http') else f"https://www.facebook.com{href}"

                    leads.append({
                        "platform": "facebook",
                        "username": name.strip(),
                        "profile_url": profile_url,
                        "email": None,
                        "followers": 0,
                        "tags": [keyword, "facebook", "page"]
                    })
            except Exception:
                continue

        print(f"[API] Facebook: extracted {len(leads)} pages")

    except Exception as e:
        print(f"[API] Facebook: error: {e}")

    return leads


async def _scrape_twitter(page, keyword: str) -> list:
    """Scrape Twitter/X for user profiles matching keyword"""
    import urllib.parse
    import re
    leads = []
    encoded_keyword = urllib.parse.quote(keyword)

    # 使用更精确的搜索语法：只搜索账号
    url = f"https://x.com/search?q=%40{encoded_keyword}&src=typed_query&f=user"
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)

    # 等待页面加载
    await asyncio.sleep(3)

    # 检测登录墙
    current_url = page.url
    if "login" in current_url or "i/flow/login" in current_url:
        print("[API] Twitter: login wall detected — search requires authentication")
        return []

    # 向下滚动几次加载更多真实用户
    for _ in range(3):
        await page.evaluate("window.scrollBy(0, 800)")
        await asyncio.sleep(1)

    # Wait for user cells with retry
    for attempt in range(3):
        try:
            await page.wait_for_selector('[data-testid="UserCell"]', timeout=10000)
            break
        except Exception:
            # Try scrolling to load more content
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(1)

    user_cells = await page.query_selector_all('[data-testid="UserCell"]')
    print(f"[API] Twitter: found {len(user_cells)} user cells")

    for cell in user_cells[:20]:
        try:
            # 获取所有文本内容进行调试
            all_texts = await cell.query_selector_all('span')
            text_contents = [await t.text_content() for t in all_texts if await t.text_content()]
            print(f"[API] Twitter cell texts: {text_contents[:5]}")

            # 查找 handle - 通常格式是 @username
            handle = ""
            name = ""

            for text in text_contents:
                text = text.strip()
                # 匹配 Twitter handle 格式
                if re.match(r'^@?[a-zA-Z0-9_]{1,15}$', text) and not text.startswith('@'):
                    # 这可能是用户名（不带@的）
                    if not handle:
                        handle = f"@{text}"
                elif text.startswith('@') and len(text) > 1:
                    handle = text
                    break

            # 查找显示名称（通常是比较长的文本）
            for text in text_contents:
                text = text.strip()
                if text and not text.startswith('@') and len(text) > 2 and len(text) < 50:
                    # 排除数字和短文本
                    if not re.match(r'^[0-9,]+$', text):
                        name = text
                        break

            # 验证 handle 格式
            if handle:
                clean_handle = handle.strip('@')
                # 验证是有效的 Twitter handle
                if re.match(r'^[a-zA-Z0-9_]{1,15}$', clean_handle):
                    profile_url = f"https://x.com/{clean_handle}"

                    # 提取粉丝数（如果能找到）
                    followers = 0
                    for text in text_contents:
                        # 匹配 "1.2M followers" 或 "12.5K" 格式
                        if 'followers' in text.lower() or 'M' in text or 'K' in text:
                            followers_text = text
                            # 提取数字
                            numbers = re.findall(r'[\d.]+', followers_text)
                            if numbers:
                                num = float(numbers[0])
                                if 'M' in followers_text:
                                    followers = int(num * 1000000)
                                elif 'K' in followers_text:
                                    followers = int(num * 1000)
                                else:
                                    followers = int(num)
                            break

                    leads.append({
                        "platform": "x",
                        "username": f"{name} ({handle})" if name else handle,
                        "profile_url": profile_url,
                        "email": None,
                        "followers": followers,
                        "tags": [keyword]
                    })
                    print(f"[API] Twitter: extracted @{clean_handle}, name={name}, followers={followers}")
        except Exception as e:
            print(f"[API] Twitter parse error: {e}")
            continue

    return leads


async def _scrape_linkedin(page, keyword: str) -> list:
    """Scrape LinkedIn for user profiles matching keyword"""
    import urllib.parse
    leads = []

    # LinkedIn search URL
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://www.linkedin.com/search/results/people/?keywords={encoded_keyword}&origin=GLOBAL_SEARCH_HEADER"

    await page.goto(url, wait_until="domcontentloaded", timeout=30000)

    # Wait and check for login wall
    await asyncio.sleep(3)

    # Check if redirected to login
    if "login" in page.url or " checkpoint" in page.url.lower():
        print("[API] LinkedIn requires login")
        return []

    # Try multiple selectors for LinkedIn search results
    selectors = [
        '.entity-result',
        '.search-result__occluded-item',
        '[data-test-id="people-search-result"]',
        '.reusable-search__result-container'
    ]

    user_cards = []
    for selector in selectors:
        user_cards = await page.query_selector_all(selector)
        if user_cards:
            print(f"[API] LinkedIn: found {len(user_cards)} cards with selector {selector}")
            break

    for card in user_cards[:15]:
        try:
            # Extract name - multiple selectors
            name = ""
            for name_sel in ['.entity-result__title-text a', '.search-result__info a', '[data-test-id="people-search-name"]']:
                name_el = await card.query_selector(name_sel)
                if name_el:
                    name = await name_el.text_content()
                    break

            # Extract title/subtitle
            title = ""
            for title_sel in ['.entity-result__primary-subtitle', '.search-result__snippet']:
                title_el = await card.query_selector(title_sel)
                if title_el:
                    title = await title_el.text_content()
                    break

            # Extract profile URL
            profile_url = ""
            for link_sel in ['.entity-result__title-text a', '.search-result__info a']:
                link_el = await card.query_selector(link_sel)
                if link_el:
                    profile_url = await link_el.get_attribute('href')
                    break

            if profile_url and not profile_url.startswith('http'):
                profile_url = 'https://www.linkedin.com' + profile_url

            if name:
                leads.append({
                    "platform": "linkedin",
                    "username": name.strip(),
                    "profile_url": profile_url,
                    "email": None,
                    "followers": 0,
                    "tags": [keyword],
                    "metadata": {
                        "title": title.strip() if title else None
                    }
                })
        except Exception as e:
            print(f"[API] LinkedIn parse error: {e}")
            continue

    return leads


async def _scrape_instagram(page, keyword: str) -> list:
    """Scrape Instagram for hashtags and user profiles matching keyword"""
    import urllib.parse
    leads = []

    # Instagram hashtag search
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://www.instagram.com/explore/tags/{encoded_keyword}/"
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)

    await asyncio.sleep(3)

    # Check for login wall
    if "login" in page.url or "checkpoint" in page.url.lower():
        print("[API] Instagram requires login")
        return []

    # Try to find post links
    post_links = await page.query_selector_all('a[href*="/p/"]')
    for link in post_links[:10]:
        try:
            href = await link.get_attribute('href')
            if href and '/p/' in href:
                leads.append({
                    "platform": "instagram",
                    "username": f"instagram_post_{keyword}",
                    "profile_url": f"https://www.instagram.com{href}",
                    "email": None,
                    "followers": 0,
                    "tags": [keyword]
                })
        except Exception:
            continue

    return leads[:10]


async def _scrape_shopify(page, keyword: str, store_domain: str = None) -> list:
    """Scrape Shopify stores for products matching keyword"""
    import urllib.parse
    leads = []

    # If specific store domain provided, scrape that store directly
    if store_domain:
        if not store_domain.startswith('http'):
            store_domain = f"https://{store_domain}"
        url = f"{store_domain}/search?q={urllib.parse.quote(keyword)}"
    else:
        # Try Shopify's store directory (may be blocked by Cloudflare)
        encoded_keyword = urllib.parse.quote(keyword)
        url = f"https://www.shopify.com/search?q={encoded_keyword}"

    print(f"[API] Shopify: navigating to {url}")
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        print(f"[API] Shopify: response status = {response.status}, url = {page.url}")

        await asyncio.sleep(3)

        # Check for Cloudflare or login redirect
        if response.status in [403, 429] or "challenge" in page.url.lower():
            print(f"[API] Shopify: blocked by Cloudflare/protection (status {response.status})")
            # Try to extract any visible links
            page_content = await page.content()
            if "Cloudflare" in page_content:
                return []
            # Fall through to try other selectors

        # Get page content for debugging
        title = await page.title()
        print(f"[API] Shopify: page title = {title}")

        # Try multiple selectors for product results
        product_selectors = [
            '[data-testid="product-card"]',
            '.product-card',
            '.search-results__product',
            'a[href*="/products/"]',
            '.product-item',
            '.grid__item',
            '.product-item__info'
        ]

        products = []
        for selector in product_selectors:
            found = await page.query_selector_all(selector)
            if found:
                print(f"[API] Shopify: found {len(found)} products with selector: {selector}")
                products = found
                break

        if not products:
            # Try to get any links to products
            all_links = await page.query_selector_all('a[href*="/products/"]')
            print(f"[API] Shopify: found {len(all_links)} product links")

            for link in all_links[:15]:
                try:
                    href = await link.get_attribute('href')
                    text = await link.text_content()
                    if href and '/products/' in href:
                        full_url = href if href.startswith('http') else f'https://shopify.com{href}'
                        leads.append({
                            "platform": "shopify",
                            "username": text.strip() if text else keyword,
                            "profile_url": full_url,
                            "email": None,
                            "followers": 0,
                            "tags": [keyword, "product"]
                        })
                except Exception:
                    continue
        else:
            for product in products[:15]:
                try:
                    # Extract product name
                    name = ""
                    for name_sel in ['h2', '.product-card__title', '[data-testid="product-title"]', '.product-item__title', '.product-title']:
                        name_el = await product.query_selector(name_sel)
                        if name_el:
                            name = await name_el.text_content()
                            break

                    # Extract product URL
                    product_url = ""
                    link_el = await product.query_selector('a[href*="/products/"]')
                    if not link_el:
                        link_el = await product.query_selector('a')
                    if link_el:
                        product_url = await link_el.get_attribute('href')
                    if product_url and not product_url.startswith('http'):
                        product_url = 'https://shopify.com' + product_url

                    if name:
                        leads.append({
                            "platform": "shopify",
                            "username": name.strip(),
                            "profile_url": product_url,
                            "email": None,
                            "followers": 0,
                            "tags": [keyword, "product"]
                        })
                except Exception as e:
                    print(f"[API] Shopify parse error: {e}")
                    continue

        print(f"[API] Shopify: extracted {len(leads)} leads")

    except Exception as e:
        print(f"[API] Shopify: navigation error: {e}")

    return leads


async def _scrape_google(page, keyword: str, suffix: str = "company") -> list:
    """Scrape Google search results for websites/companies matching keyword"""
    import urllib.parse
    from urllib.parse import urlparse
    leads = []

    # Google search URL
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://www.google.com/search?q={encoded_keyword}+{urllib.parse.quote(suffix)}&num=20" if suffix else f"https://www.google.com/search?q={encoded_keyword}&num=20"

    print(f"[API] Google: navigating to {url}")
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        print(f"[API] Google: response status = {response.status}, url = {page.url}")

        await asyncio.sleep(3)

        # Handle consent/cookie page (common in EU)
        try:
            consent_btn = await page.query_selector('button:has-text("Accept all"), button:has-text("Reject all"), button:has-text("I agree")')
            if consent_btn:
                await consent_btn.click()
                await asyncio.sleep(2)
        except Exception:
            pass

        # Check for robots/CAPTCHA check
        current_url = page.url.lower()
        page_text = (await page.content()).lower()
        if "sorry" in current_url or "search1972" in current_url or "captcha" in page_text or "unusual traffic" in page_text:
            print("[API] Google: blocked by CAPTCHA/robots check")
            return []

        # Extract search results — try multiple selectors
        results = []
        for selector in ['div.g', 'div[data-sokoban-container]', 'div.tF2Cxc', '.MjjYud']:
            results = await page.query_selector_all(selector)
            if results:
                print(f"[API] Google: found {len(results)} results with selector '{selector}'")
                break

        if not results:
            # Fallback: get all h3 elements (each is a search result title)
            h3s = await page.query_selector_all('h3')
            print(f"[API] Google: fallback found {len(h3s)} h3 elements")
            for h3 in h3s[:15]:
                try:
                    title = await h3.text_content()
                    # Walk up to find the parent <a> tag
                    link_el = await h3.evaluate_handle('el => el.closest("a")')
                    if link_el:
                        href = await link_el.get_attribute('href')
                        if title and href and href.startswith('http'):
                            domain = urlparse(href).netloc
                            leads.append({
                                "platform": "google",
                                "username": title.strip(),
                                "profile_url": href,
                                "email": None,
                                "followers": 0,
                                "tags": [keyword, domain]
                            })
                except Exception:
                    continue
            print(f"[API] Google: extracted {len(leads)} results via h3 fallback")
            return leads

        for result in results[:15]:
            try:
                title_el = await result.query_selector('h3')
                link_el = await result.query_selector('a')

                title = await title_el.text_content() if title_el else ""
                href = await link_el.get_attribute('href') if link_el else ""

                if title and href and href.startswith('http'):
                    domain = urlparse(href).netloc

                    leads.append({
                        "platform": "google",
                        "username": title.strip(),
                        "profile_url": href,
                        "email": None,
                        "followers": 0,
                        "tags": [keyword, domain]
                    })
            except Exception:
                continue

        print(f"[API] Google: extracted {len(leads)} results")

    except Exception as e:
        print(f"[API] Google: error: {e}")

    return leads


async def _scrape_duckduckgo(page, keyword: str) -> list:
    """Scrape DuckDuckGo search results — more headless-friendly than Google"""
    import urllib.parse
    from urllib.parse import urlparse
    leads = []

    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://html.duckduckgo.com/html/?q={encoded_keyword}"

    print(f"[API] DuckDuckGo: navigating to {url}")
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        print(f"[API] DuckDuckGo: response status = {response.status}, url = {page.url}")

        await asyncio.sleep(2)

        # DuckDuckGo HTML version has simple structure
        results = await page.query_selector_all('.result')
        if not results:
            results = await page.query_selector_all('.web-result')
        if not results:
            # Fallback: try result links directly
            results = await page.query_selector_all('.result__a')

        print(f"[API] DuckDuckGo: found {len(results)} result elements")

        for result in results[:15]:
            try:
                # Try to get title and link
                link_el = await result.query_selector('a.result__a, a.result__url, a')
                if not link_el:
                    continue

                title = await link_el.text_content()
                href = await link_el.get_attribute('href')

                if not href:
                    continue

                # DuckDuckGo sometimes uses redirect URLs
                if '/l/?uddg=' in href:
                    import re
                    match = re.search(r'uddg=([^&]+)', href)
                    if match:
                        href = urllib.parse.unquote(match.group(1))

                if title and href and href.startswith('http'):
                    domain = urlparse(href).netloc
                    leads.append({
                        "platform": "duckduckgo",
                        "username": title.strip(),
                        "profile_url": href,
                        "email": None,
                        "followers": 0,
                        "tags": [keyword, domain]
                    })
            except Exception:
                continue

        print(f"[API] DuckDuckGo: extracted {len(leads)} results")

    except Exception as e:
        print(f"[API] DuckDuckGo: error: {e}")

    return leads


async def _scrape_public_directory(page, keyword: str) -> list:
    """Scrape public business directories for leads"""
    import urllib.parse
    leads = []

    # Yellow Pages as example
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://www.yellowpages.com/search?search_terms={encoded_keyword}&geo_location_terms=USA"

    print(f"[API] Directory: navigating to {url}")
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        print(f"[API] Directory: status {response.status}")

        await asyncio.sleep(2)

        # Extract business listings
        listings = await page.query_selector_all('.result')

        for listing in listings[:15]:
            try:
                name_el = await listing.query_selector('.business-name')
                phone_el = await listing.query_selector('.phone')
                link_el = await listing.query_selector('a')

                name = await name_el.text_content() if name_el else ""
                phone = await phone_el.text_content() if phone_el else ""
                href = await link_el.get_attribute('href') if link_el else ""

                if name:
                    profile_url = href if href.startswith('http') else f'https://www.yellowpages.com{href}'
                    leads.append({
                        "platform": "directory",
                        "username": name.strip(),
                        "profile_url": profile_url,
                        "email": None,
                        "followers": 0,
                        "tags": [keyword, "business", phone.strip() if phone else ""]
                    })
            except Exception:
                continue

        print(f"[API] Directory: extracted {len(leads)} listings")

    except Exception as e:
        print(f"[API] Directory: error: {e}")

    return leads


@router.post("/test-scraper")
async def test_scraper(request: ScrapeRequest):
    """
    Trigger LeadAgent for real scraping using the persistent browser pool.
    Supports multiple platforms: x, twitter, linkedin, instagram, shopify
    This endpoint uses the browser pool instead of starting/closing browser per request.
    """
    try:
        import sys
        # Windows 事件循环修复
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

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

        # 读取 Chrome 用户数据目录（用于保持登录态）
        user_data_dir = os.getenv("CHROME_USER_DATA_DIR")

        # 读取 CDP URL（优先使用，保持登录态更稳定）
        cdp_url = os.getenv("CDP_URL")

        # 从池中获取 context
        context_id = f"scrape_{request.platform}_{id(request)}"
        context_id, context, instance = await pool.acquire_context(
            context_id=context_id,
            proxy=proxy_config,
            user_data_dir=user_data_dir,
            cdp_url=cdp_url
        )

        try:
            # 使用 Playwright Stealth 避免被检测
            from playwright_stealth import Stealth

            page = await context.new_page()
            stealth = Stealth()

            # 应用 stealth 配置，模拟真实浏览器
            await stealth.apply_stealth_async(page)

            # 设置更真实的浏览器属性
            await page.set_extra_http_headers({
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            })

            leads = []
            platform = request.platform.lower()
            scrape_source = platform
            print(f"[API] Starting scrape: platform={platform}, keyword={request.keyword}")

            # 根据平台选择爬取函数
            if platform in ["twitter", "x"]:
                leads = await _scrape_twitter(page, request.keyword)
            elif platform == "linkedin":
                leads = await _scrape_linkedin(page, request.keyword)
            elif platform == "instagram":
                leads = await _scrape_instagram(page, request.keyword)
            elif platform == "shopify":
                leads = await _scrape_shopify(page, request.keyword, request.store_domain)
            elif platform == "google":
                leads = await _scrape_google(page, request.keyword)
            elif platform == "directory":
                leads = await _scrape_public_directory(page, request.keyword)
            elif platform == "tiktok":
                leads = await _scrape_tiktok(page, request.keyword)
            elif platform == "facebook":
                leads = await _scrape_facebook(page, request.keyword)
            elif platform == "duckduckgo":
                leads = await _scrape_duckduckgo(page, request.keyword)
            else:
                # 未知平台，返回 mock
                pass

            # 平台直连爬取失败时，回退到 DuckDuckGo 搜索（无需登录，不封 headless）
            if not leads and platform not in ["google", "directory", "duckduckgo"]:
                print(f"[API] {platform} returned 0 leads, falling back to DuckDuckGo search")
                scrape_source = f"{platform}+ddg"
                leads = await _scrape_duckduckgo(page, f"{request.keyword} {platform}")
                # DuckDuckGo 也失败则尝试 Google
                if not leads:
                    print("[API] DuckDuckGo returned 0 leads, trying Google search")
                    scrape_source = f"{platform}+google"
                    leads = await _scrape_google(page, f"{request.keyword} {platform}", suffix="")

            await page.close()

            # 应用扩展参数过滤
            if request.geography != "all":
                leads = [l for l in leads if _match_geography(l, request.geography)]
            if request.follower_range != "all":
                leads = [l for l in leads if _match_follower_range(l, request.follower_range)]
            if request.content_type != "all":
                leads = [l for l in leads if _match_content_type(l, request.content_type)]
            if request.max_results > 0 and len(leads) > request.max_results:
                leads = leads[:request.max_results]

            # 保存真实数据到数据库（跳过空结果，不写入伪造数据）
            if leads:
                from db import save_leads
                await save_leads(leads, request.user_id)

            return {
                "status": "success",
                "leads_found": len(leads),
                "source": scrape_source,
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
        import logging
        _logger = logging.getLogger(__name__)
        _logger.error(f"Scraping Error:\n{error_details}")

        return {"status": "error", "message": f"Scraping workflow failed: {repr(e)}"}


# 需要 datetime


# ========================
# SerpAPI 搜索端点 (合规的搜索结果)
# ========================

class SerpSearchRequest(BaseModel):
    keyword: str = "fitness equipment"
    engine: str = "google"  # google, bing, yahoo, yandex, baidu, youtube, amazon, etc.
    num_results: int = 10


@router.post("/serp-search")
async def serpapi_search(request: SerpSearchRequest):
    """
    使用 SerpAPI 进行合规的搜索引擎结果爬取

    支持的引擎:
    - google: Google 搜索结果
    - bing: Bing 搜索结果
    - yahoo: Yahoo 搜索结果
    - yandex: Yandex 搜索结果
    - baidu: 百度搜索结果
    - youtube: YouTube 视频搜索
    - amazon: Amazon 产品搜索
    - ebay: eBay 产品搜索

    申请 SerpAPI Key: https://serpapi.com
    """
    serpapi_key = os.getenv("SERPAPI_KEY")

    if not serpapi_key:
        return {
            "status": "error",
            "message": "SerpAPI key not configured. Set SERPAPI_KEY in .env file. Get your key at https://serpapi.com"
        }

    try:
        from serpapi import GoogleSearch, BingSearch, EbaySearch, AmazonSearch, YoutubeSearch

        params = {
            "q": request.keyword,
            "num": request.num_results,
            "api_key": serpapi_key
        }

        leads = []
        search_results = None

        if request.engine == "google":
            search_results = GoogleSearch(params)
        elif request.engine == "bing":
            search_results = BingSearch(params)
        elif request.engine == "amazon":
            search_results = AmazonSearch(params)
        elif request.engine == "youtube":
            search_results = YoutubeSearch(params)
            params["search_query"] = params.pop("q")
        else:
            # Default to Google
            search_results = GoogleSearch(params)

        data = search_results.get_dict()

        # Parse results based on engine
        if request.engine == "google":
            if "organic_results" in data:
                for result in data["organic_results"][:request.num_results]:
                    leads.append({
                        "platform": "google",
                        "username": result.get("title", ""),
                        "profile_url": result.get("link", ""),
                        "email": None,
                        "followers": 0,
                        "tags": [request.keyword, result.get("displayed_link", "")],
                        "snippet": result.get("snippet", "")
                    })
        elif request.engine == "bing":
            if "organic_results" in data:
                for result in data["organic_results"][:request.num_results]:
                    leads.append({
                        "platform": "bing",
                        "username": result.get("title", ""),
                        "profile_url": result.get("link", ""),
                        "email": None,
                        "followers": 0,
                        "tags": [request.keyword],
                        "snippet": result.get("snippet", "")
                    })
        elif request.engine == "youtube":
            if "video_results" in data:
                for result in data["video_results"][:request.num_results]:
                    leads.append({
                        "platform": "youtube",
                        "username": result.get("title", ""),
                        "profile_url": result.get("link", ""),
                        "email": None,
                        "followers": int(result.get("views", "0").replace(",", "")) if result.get("views") else 0,
                        "tags": [request.keyword, result.get("channel", "")],
                        "duration": result.get("duration", "")
                    })
        elif request.engine == "amazon":
            if "organic_results" in data:
                for result in data["organic_results"][:request.num_results]:
                    leads.append({
                        "platform": "amazon",
                        "username": result.get("title", ""),
                        "profile_url": result.get("link", ""),
                        "email": None,
                        "followers": 0,
                        "tags": [request.keyword, result.get("price", ""), result.get("rating", "")],
                        "snippet": result.get("snippet", "")
                    })

        # Save to database
        if leads:
            from db import save_leads
            await save_leads(leads)

        return {
            "status": "success",
            "leads_found": len(leads),
            "engine": request.engine,
            "keyword": request.keyword,
            "data": leads
        }

    except ImportError:
        return {
            "status": "error",
            "message": "SerpAPI library not installed. Run: pip install google-search-results"
        }
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"[API] SerpAPI search failed: {error_details}")
        return {
            "status": "error",
            "message": f"SerpAPI search failed: {str(e)}"
        }


# ========================
# Browser Harness Endpoints
# ========================

class HarnessScrapeRequest(BaseModel):
    keyword: str = "fitness equipment"
    platform: str = "x"
    action: str = "scrape"  # scrape | follow | message | connect | profile
    username: Optional[str] = None
    message: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)
    dry_run: bool = False


@router.post("/harness-scrape")
async def harness_scrape(
    request: HarnessScrapeRequest,
    current_user=Depends(get_current_user)
):
    """
    Execute a browser-harness based task.
    Connects to the user's real Chrome browser for authenticated scraping and interaction.
    """
    from browser_cluster.manager.browser_harness_manager import get_harness_manager

    harness_mgr = await get_harness_manager()
    if not harness_mgr.is_connected:
        return {
            "status": "error",
            "message": "Browser harness not connected. Ensure Chrome is running with --remote-debugging-port=9222"
        }

    try:
        from agents.harness_agent.harness_agent import HarnessAgent
        agent = HarnessAgent(
            harness_manager=harness_mgr,
            db=None,
            dry_run=request.dry_run,
        )

        task = {
            "action": request.action,
            "platform": request.platform,
            "keyword": request.keyword,
            "username": request.username or "",
            "message": request.message or "",
            "limit": request.limit,
            "user_id": current_user.id,
        }

        result = await agent.run(task)

        # Save leads to database if scraping
        if result.get("status") == "success" and result.get("data"):
            try:
                from db import save_leads
                await save_leads(result["data"], current_user.id)
            except Exception as e:
                print(f"[API] Failed to save harness leads: {e}")

        return result

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"[API] Harness scrape failed: {error_details}")
        return {"status": "error", "message": str(e)}


@router.get("/harness-status")
async def harness_status(current_user=Depends(get_current_user)):
    """Get browser-harness connection status."""
    from browser_cluster.manager.browser_harness_manager import get_harness_manager
    from browser_cluster.harness_launcher import is_debug_port_open, get_ws_debug_url

    harness_mgr = await get_harness_manager()
    chrome_running = is_debug_port_open()

    return {
        "harness_connected": harness_mgr.is_connected,
        "chrome_debug_port": chrome_running,
        "ws_debug_url": get_ws_debug_url() if chrome_running else None,
    }


# ========================
# Marketing Pipeline (Research + Chat Agents)
# ========================

import json
import re as _re

_pipeline_semaphore = asyncio.Semaphore(3)

RESEARCH_SYSTEM_PROMPT = """You are a B2B lead research analyst for cross-border e-commerce. Analyze the given lead profile and return a JSON object with these fields:
- "industry": the lead's likely business type or industry (1-5 words, in English)
- "interests": array of 2-4 potential business interests or needs (in English)
- "best_channel": either "email" or "social_dm" based on which outreach method would be most effective
- "talking_points": array of 2-3 personalized conversation starters based on their profile (in English)
- "quality_score": integer 0-100 estimating lead quality (consider followers, profile completeness, relevance)
- "tier": "A" if quality_score >= 75, "B" if >= 50, "C" otherwise

IMPORTANT: All text values in the JSON must be written in English. Do not use Chinese or any other language.
Respond with ONLY valid JSON, no markdown, no explanation."""

CHAT_SYSTEM_PROMPT = """You are a B2B marketing copywriter for cross-border e-commerce. Given a lead's research profile, generate personalized outreach messages for 3 channels. Return a JSON object with a "messages" array containing exactly 3 objects, each with:
- "channel": "email", "linkedin_dm", or "twitter_dm"
- "subject": email subject line (empty string for non-email channels)
- "body": the message body (twitter_dm must be under 280 characters)
- "cta": call to action text

Guidelines:
- Reference specific details from the lead's profile and interests
- Match the tone to the platform (professional for email/LinkedIn, casual for Twitter)
- For tier A leads, be more detailed and personalized
- For tier C leads, keep it brief and value-focused
- Include a clear call-to-action in each message
- IMPORTANT: All text (subject, body, cta) must be written in English unless explicitly told otherwise

Respond with ONLY valid JSON, no markdown."""


def _strip_json_fences(text: str) -> str:
    """Strip markdown code fences from LLM response."""
    text = text.strip()
    text = _re.sub(r'^```(?:json)?\s*', '', text)
    text = _re.sub(r'\s*```$', '', text)
    return text.strip()


def _lead_fallback_research(lead: dict) -> dict:
    """Fallback research when LLM fails."""
    followers = lead.get("followers", 0)
    score = min(50, max(10, followers // 200))
    tier = "A" if score >= 75 else ("B" if score >= 50 else "C")
    return {
        "industry": lead.get("tags", ["Unknown"])[0] if lead.get("tags") else "Unknown",
        "interests": lead.get("tags", [])[:3] or ["general business"],
        "best_channel": "email" if lead.get("email") else "social_dm",
        "talking_points": [f"Active on {lead.get('platform', 'social media')}", "Potential collaboration opportunity"],
        "quality_score": score,
        "tier": tier
    }


async def _research_lead(client, lead: dict, product_context: str, language: str) -> dict:
    """Research Agent: analyze a single lead via LLM."""
    async with _pipeline_semaphore:
        try:
            user_prompt = f"""Lead profile:
- Platform: {lead.get('platform', 'unknown')}
- Username: {lead.get('username', 'unknown')}
- Profile URL: {lead.get('profile_url', 'none')}
- Email: {lead.get('email') or 'none'}
- Followers: {lead.get('followers', 0)}
- Tags: {lead.get('tags', [])}"""

            if product_context:
                user_prompt += f"\n\nProduct context: {product_context}"
            if language == "zh":
                user_prompt += "\n\n请用中文回复所有字段。"
            else:
                user_prompt += "\n\nIMPORTANT: Write ALL fields (industry, interests, talking_points) in English only."

            response = await client.chat.completions.create(
                model="meta-llama/llama-3-8b-instruct",
                messages=[
                    {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                extra_headers={"HTTP-Referer": "http://localhost:8000", "X-Title": "OpenClaw AI Agent"},
                max_tokens=500
            )
            raw = response.choices[0].message.content
            result = json.loads(_strip_json_fences(raw))
            # Ensure required fields
            for key in ["industry", "interests", "best_channel", "talking_points", "quality_score", "tier"]:
                if key not in result:
                    result[key] = _lead_fallback_research(lead)[key]
            return result
        except Exception as e:
            print(f"[ResearchAgent] Failed for {lead.get('username')}: {e}")
            return _lead_fallback_research(lead)


async def _generate_messages(client, lead: dict, research: dict, product_context: str, language: str) -> list:
    """Chat Agent: generate personalized outreach messages."""
    async with _pipeline_semaphore:
        try:
            user_prompt = f"""Lead research:
- Username: {lead.get('username', 'unknown')}
- Platform: {lead.get('platform', 'unknown')}
- Industry: {research.get('industry', 'Unknown')}
- Interests: {research.get('interests', [])}
- Best channel: {research.get('best_channel', 'email')}
- Talking points: {research.get('talking_points', [])}
- Quality tier: {research.get('tier', 'C')}
- Followers: {lead.get('followers', 0)}
- Email: {lead.get('email') or 'none'}"""

            if product_context:
                user_prompt += f"\n\nProduct context: {product_context}"
            if language == "zh":
                user_prompt += "\n\n请用中文撰写所有消息（subject、body、cta）。"
            else:
                user_prompt += "\n\nIMPORTANT: Write ALL messages (subject, body, cta) in English only. Do not use Chinese."

            response = await client.chat.completions.create(
                model="meta-llama/llama-3-8b-instruct",
                messages=[
                    {"role": "system", "content": CHAT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                extra_headers={"HTTP-Referer": "http://localhost:8000", "X-Title": "OpenClaw AI Agent"},
                max_tokens=1500
            )
            raw = response.choices[0].message.content
            result = json.loads(_strip_json_fences(raw))
            messages = result.get("messages", [])
            # Validate twitter_dm length
            for msg in messages:
                if msg.get("channel") == "twitter_dm" and len(msg.get("body", "")) > 280:
                    msg["body"] = msg["body"][:277] + "..."
            return messages if messages else _fallback_messages(lead, research, language)
        except Exception as e:
            print(f"[ChatAgent] Failed for {lead.get('username')}: {e}")
            return _fallback_messages(lead, research, language)


def _fallback_messages(lead: dict, research: dict, language: str) -> list:
    """Fallback messages when LLM fails."""
    username = lead.get("username", "")
    industry = research.get("industry", "your industry")
    tier = research.get("tier", "C")

    if language == "zh":
        return [
            {"channel": "email", "subject": f"关于{industry}的合作机会", "body": f"您好 {username}，我们注意到您在{industry}领域的活跃表现，希望能探讨合作机会。", "cta": "预约15分钟通话"},
            {"channel": "linkedin_dm", "subject": "", "body": f"Hi {username}，看了您的资料很感兴趣，方便聊聊合作吗？", "cta": ""},
            {"channel": "twitter_dm", "subject": "", "body": f"Hi {username}! 对您的业务很感兴趣，期待交流 🤝", "cta": ""}
        ]
    else:
        return [
            {"channel": "email", "subject": f"Collaboration opportunity in {industry}", "body": f"Hi {username},\n\nWe noticed your active presence in {industry} and would love to explore a potential collaboration.", "cta": "Book a 15-min call"},
            {"channel": "linkedin_dm", "subject": "", "body": f"Hi {username}, I came across your profile and found your work in {industry} impressive. Would you be open to a quick chat?", "cta": ""},
            {"channel": "twitter_dm", "subject": "", "body": f"Hey {username}! Love what you're doing in {industry}. Let's connect! 🤝", "cta": ""}
        ]


@router.post("/marketing-pipeline")
async def marketing_pipeline(
    request: MarketingPipelineRequest,
    current_user=Depends(get_current_user)
):
    """
    Full marketing pipeline: Research Agent + Chat Agent.
    Analyzes each lead and generates personalized multi-channel messages.
    """
    try:
        client = _get_llm_client()
    except RuntimeError:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY not configured")

    leads = request.leads[:20]  # Cap at 20 leads
    if not leads:
        return {"status": "error", "message": "No leads provided"}

    product_context = request.product_context
    language = request.language
    user_id = current_user.id

    # Stage 1: Research Agent — analyze all leads concurrently
    research_tasks = [_research_lead(client, lead, product_context, language) for lead in leads]
    research_results = await asyncio.gather(*research_tasks)

    # Stage 2: Chat Agent — generate messages for each lead
    message_tasks = [
        _generate_messages(client, leads[i], research_results[i], product_context, language)
        for i in range(len(leads))
    ]
    all_messages = await asyncio.gather(*message_tasks)

    # Stage 3: Save to database and build response
    tier_distribution = {"A": 0, "B": 0, "C": 0}
    results = []
    db_messages = []

    for i, lead in enumerate(leads):
        research = research_results[i]
        messages = all_messages[i]

        tier_distribution[research.get("tier", "C")] += 1

        # Save research to leads table
        lead_id = lead.get("id")
        if lead_id:
            from db import save_lead_research, save_marketing_messages
            await save_lead_research(lead_id, research, research.get("quality_score", 0))

        # Prepare messages for DB
        for msg in messages:
            db_messages.append({
                "lead_id": lead_id,
                "user_id": user_id,
                "channel": msg.get("channel", ""),
                "subject": msg.get("subject", ""),
                "body": msg.get("body", ""),
                "cta": msg.get("cta", ""),
                "sequence_step": 1,
                "status": "draft"
            })

        results.append({
            "lead": {
                "id": lead_id,
                "username": lead.get("username", ""),
                "platform": lead.get("platform", ""),
                "profile_url": lead.get("profile_url", ""),
                "followers": lead.get("followers", 0)
            },
            "research": research,
            "messages": messages
        })

    # Batch save messages
    if db_messages:
        from db import save_marketing_messages
        await save_marketing_messages(db_messages)

    return {
        "status": "success",
        "summary": {
            "total_leads": len(leads),
            "researched": len(research_results),
            "messages_generated": sum(len(m) for m in all_messages),
            "tier_distribution": tier_distribution
        },
        "results": results
    }


# ─── Skill Execution ──────────────────────────────────────────────

class SkillExecuteRequest(BaseModel):
    skill_id: str
    input_text: str = ""
    language: str = "en"


_SKILL_PROMPTS = {
    "s1": {
        "system": "You are a professional multilingual translator. Return valid JSON only, no markdown fences. Write ALL text content in {lang_name}.",
        "user_tpl": "Translate the following text into English, Chinese, Spanish, French, and German.\n\nText:\n{input}\n\nReturn JSON:\n{{\"translations\": [{{\"lang\": \"en\", \"text\": \"...\"}}, {{\"lang\": \"zh\", \"text\": \"...\"}}, {{\"lang\": \"es\", \"text\": \"...\"}}, {{\"lang\": \"fr\", \"text\": \"...\"}}, {{\"lang\": \"de\", \"text\": \"...\"}}]}}"
    },
    "s2": {
        "system": "You are a market research analyst. Return valid JSON only, no markdown fences. Write ALL text content in {lang_name}.",
        "user_tpl": "Analyze the top competitors for the following product/niche/leads data. Identify strengths, weaknesses, and market opportunities.\n\nContext:\n{input}\n\nReturn JSON:\n{{\"competitors\": [{{\"name\": \"...\", \"strengths\": [\"...\"], \"weaknesses\": [\"...\"], \"opportunities\": [\"...\"]}}], \"market_trends\": [\"...\"], \"recommendation\": \"...\"}}"
    },
    "s3": {
        "system": "You are an email marketing expert specializing in high-open-rate subject lines. Return valid JSON only, no markdown fences. Write ALL text content in {lang_name}.",
        "user_tpl": "Generate 10 high-open-rate email subject lines for the following product/niche/campaign.\n\nContext:\n{input}\n\nReturn JSON:\n{{\"subjects\": [{{\"text\": \"...\", \"predicted_open_rate\": \"35%\", \"rationale\": \"...\"}}]}}"
    },
    "s4": {
        "system": "You are a LinkedIn outreach specialist. Write professional, personalized DMs. Return valid JSON only, no markdown fences. Write ALL text content in {lang_name}.",
        "user_tpl": "Generate 3 LinkedIn outreach DM variants for the following lead/context. Each variant should have a different tone (professional, friendly, bold).\n\nContext:\n{input}\n\nReturn JSON:\n{{\"scripts\": [{{\"variant\": \"Professional\", \"opener\": \"...\", \"body\": \"...\", \"cta\": \"...\", \"tone\": \"professional\"}}, {{\"variant\": \"Friendly\", \"opener\": \"...\", \"body\": \"...\", \"cta\": \"...\", \"tone\": \"friendly\"}}, {{\"variant\": \"Bold\", \"opener\": \"...\", \"body\": \"...\", \"cta\": \"...\", \"tone\": \"bold\"}}]}}"
    },
    "s5": {
        "system": "You are a conversion rate optimization expert. Return valid JSON only, no markdown fences. Write ALL text content in {lang_name}.",
        "user_tpl": "Given the following marketing copy, generate 3 A/B test variants. Each variant should change a different element (headline, CTA, tone).\n\nOriginal copy:\n{input}\n\nReturn JSON:\n{{\"variants\": [{{\"variant_id\": \"A\", \"text\": \"...\", \"change_description\": \"...\", \"hypothesis\": \"...\"}}, {{\"variant_id\": \"B\", \"text\": \"...\", \"change_description\": \"...\", \"hypothesis\": \"...\"}}, {{\"variant_id\": \"C\", \"text\": \"...\", \"change_description\": \"...\", \"hypothesis\": \"...\"}}]}}"
    },
    "s6": {
        "system": "You are a data quality analyst. Return valid JSON only, no markdown fences. Write ALL text content in {lang_name}.",
        "user_tpl": "Analyze the following leads data for quality issues. Flag duplicates, missing fields, invalid emails, suspicious entries, and low-quality records.\n\nLeads data:\n{input}\n\nReturn JSON:\n{{\"total\": 10, \"valid\": 8, \"issues_found\": 2, \"cleaned_leads\": [...], \"removed\": [...], \"issues\": [{{\"lead\": \"...\", \"reason\": \"...\"}}], \"summary\": \"...\"}}"
    },
}


@router.post("/execute-skill")
async def execute_skill(request: SkillExecuteRequest, current_user=Depends(get_current_user)):
    """Execute a skill module via LLM."""
    skill_id = request.skill_id
    if skill_id not in _SKILL_PROMPTS:
        raise HTTPException(status_code=400, detail=f"Unknown skill_id: {skill_id}")

    prompt_cfg = _SKILL_PROMPTS[skill_id]
    is_zh = request.language == "zh"
    lang_name = "Chinese" if is_zh else "English"
    system_prompt = prompt_cfg["system"].replace("{lang_name}", lang_name)
    user_content = prompt_cfg["user_tpl"].replace("{input}", request.input_text or ("(未提供输入)" if is_zh else "(no input provided)"))
    user_content += "\n\n" + ("请用中文回复所有文本内容。只返回纯JSON，不要用markdown代码块包裹。" if is_zh else "Write ALL text content in English. Return raw JSON only, do not wrap in markdown code blocks.")

    try:
        client = _get_llm_client()
        async with _pipeline_semaphore:
            response = await client.chat.completions.create(
                model="meta-llama/llama-3-8b-instruct",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                extra_headers={"HTTP-Referer": "http://localhost:8000", "X-Title": "OpenClaw AI Agent"},
                max_tokens=2000
            )
            raw = response.choices[0].message.content
            result = json.loads(_strip_json_fences(raw))
            return {"status": "success", "skill_id": skill_id, "result": result}
    except json.JSONDecodeError:
        # Try to fix common JSON issues from LLM output
        try:
            fixed = raw.strip()
            # Remove markdown code fences if present
            if fixed.startswith("```"):
                first_newline = fixed.index("\n")
                fixed = fixed[first_newline + 1:]
            if fixed.endswith("```"):
                fixed = fixed[:-3].rstrip()
            result = json.loads(fixed)
            return {"status": "success", "skill_id": skill_id, "result": result}
        except Exception:
            return {"status": "success", "skill_id": skill_id, "result": {"raw_output": raw}}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
