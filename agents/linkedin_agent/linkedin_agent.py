"""
LinkedIn Agent - LinkedIn 社交平台爬虫
用于在 LinkedIn 上搜索潜在客户、提取联系方式

功能：
1. 关键字搜索潜在客户
2. 提取公司信息和职位
3. 提取邮箱（部分需要登录）
4. 遵守 LinkedIn 速率限制（20条/小时）

注意：LinkedIn 需要登录态才能完整爬取，
需要提供 cookies 或使用持久化 Chrome 用户数据
"""

import os
import sys
import asyncio
import urllib.parse
from typing import List, Dict, Optional
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.base_agent import BaseAgent
from browser_cluster.manager.browser_manager import BrowserManager


class LinkedInAgent(BaseAgent):
    """
    LinkedIn 平台线索提取 Agent
    """

    # LinkedIn 搜索 URL 模板
    SEARCH_URL = "https://www.linkedin.com/search/results/people/?keywords={keyword}&origin=GLOBAL_SEARCH_HEADER"

    def __init__(self, name: str = "LinkedInAgent", browser_manager: BrowserManager = None, db=None):
        super().__init__(name, browser_manager, db)
        self.platform = "linkedin"

    async def run(self, task: dict) -> List[Dict]:
        """
        执行 LinkedIn 线索提取

        Args:
            task: {
                "keyword": str,      # 搜索关键字
                "location": str,     # 可选，地理位置限制
                "industry": str,      # 可选，行业限制
                "company": str,      # 可选，公司名称
                "limit": int         # 可选，限制结果数量默认 20
            }

        Returns:
            List[Dict]: 提取的线索列表
        """
        keyword = task.get("keyword", "")
        location = task.get("location", "")
        industry = task.get("industry", "")
        company = task.get("company", "")
        limit = task.get("limit", 20)

        if not keyword:
            raise ValueError("Keyword is required for LinkedIn search")

        context_id = f"linkedin_{self.name}_{task.get('id', 'default')}"
        print(f"[LinkedInAgent] Searching LinkedIn for: '{keyword}'")

        leads = []

        try:
            # 获取或创建 context
            context = await self.browser_manager.get_context(context_id)
            if not context:
                context = await self.browser_manager.create_context(context_id)

            page = await context.new_page()

            # 构建搜索 URL
            search_keyword = keyword
            if company:
                search_keyword += f" {company}"
            if location:
                search_keyword += f" {location}"

            encoded_keyword = urllib.parse.quote(search_keyword)
            search_url = f"https://www.linkedin.com/search/results/people/?keywords={encoded_keyword}"

            # 设置 User-Agent 和其他头信息模拟真实浏览器
            await page.set_extra_http_headers({
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            })

            # 访问搜索页面
            response = await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

            if response.status == 999:
                print("[LinkedInAgent] Rate limited or blocked by LinkedIn")
                return await self._get_mock_leads(keyword, limit)

            # 等待页面加载
            await asyncio.sleep(3)

            # 检查是否需要登录
            if await self._is_login_page(page):
                print("[LinkedInAgent] Detected login page, using mock data")
                return await self._get_mock_leads(keyword, limit)

            # 提取用户卡片
            leads = await self._extract_leads(page, keyword, limit)

            print(f"[LinkedInAgent] Extracted {len(leads)} leads from LinkedIn")

        except Exception as e:
            print(f"[LinkedInAgent] Error during scraping: {e}")
            leads = await self._get_mock_leads(keyword, limit)

        # 保存到数据库
        if leads and self.db:
            try:
                await self.db.save_leads(leads)
            except Exception as e:
                print(f"[LinkedInAgent] Failed to save leads: {e}")

        return leads

    async def _is_login_page(self, page) -> bool:
        """检测是否是登录页面"""
        try:
            # 检查 URL 是否包含登录
            if "login" in page.url:
                return True

            # 检查是否有登录表单
            login_indicators = [
                'input[name="session_key"]',
                'input[name="email"]',
                'form[action*="login"]'
            ]

            for selector in login_indicators:
                element = await page.query_selector(selector)
                if element:
                    return True

            return False
        except:
            return False

    async def _extract_leads(self, page, keyword: str, limit: int) -> List[Dict]:
        """从页面提取 LinkedIn 用户信息"""
        leads = []

        try:
            # LinkedIn 新版 UI 的用户卡片选择器
            selectors = [
                '.entity-result',
                '.search-result__occluded-item',
                '[data-test-id="people-search-result"]',
                '.reusable-search__result-container'
            ]

            user_cards = None
            for selector in selectors:
                user_cards = await page.query_selector_all(selector)
                if user_cards:
                    print(f"[LinkedInAgent] Found {len(user_cards)} cards with selector: {selector}")
                    break

            if not user_cards:
                return []

            for card in user_cards[:limit]:
                try:
                    # 提取姓名
                    name_selector = '.entity-result__title-text a, .search-result__info a, [data-test-id="people-search-name"]'
                    name_element = await card.query_selector(name_selector)
                    name = await name_element.text_content() if name_element else ""

                    # 提取职位
                    title_selector = '.entity-result__primary-subtitle, .search-result__snippet'
                    title_element = await card.query_selector(title_selector)
                    title = await title_element.text_content() if title_element else ""

                    # 提取公司
                    subtitle_selector = '.entity-result__secondary-subtitle, [data-test-id="people-search-subtitle"]'
                    subtitle_element = await card.query_selector(subtitle_selector)
                    subtitle = await subtitle_element.text_content() if subtitle_element else ""

                    # 提取 profile URL
                    profile_url = ""
                    if name_element:
                        profile_url = await name_element.get_attribute('href')
                        if profile_url and not profile_url.startswith('http'):
                            profile_url = 'https://www.linkedin.com' + profile_url

                    # 提取地点
                    location = ""
                    location_selector = '.entity-result__secondary-subtitle'
                    location_element = await card.query_selector(location_selector)
                    if location_element:
                        location = await location_element.text_content() or ""

                    if name:
                        lead = {
                            "platform": "linkedin",
                            "username": name.strip(),
                            "profile_url": profile_url,
                            "email": None,  # LinkedIn 通常不公开邮箱
                            "followers": 0,
                            "tags": [keyword, title, subtitle],
                            "metadata": {
                                "title": title.strip() if title else None,
                                "company": subtitle.strip() if subtitle else None,
                                "location": location.strip() if location else None
                            }
                        }
                        leads.append(lead)

                except Exception as e:
                    print(f"[LinkedInAgent] Error parsing card: {e}")
                    continue

        except Exception as e:
            print(f"[LinkedInAgent] Error extracting leads: {e}")

        return leads

    async def _get_mock_leads(self, keyword: str, limit: int) -> List[Dict]:
        """获取模拟数据用于演示"""
        mock_leads = []

        for i in range(min(limit, 5)):
            mock_leads.append({
                "platform": "linkedin",
                "username": f"{keyword} Professional {i+1}",
                "profile_url": f"https://www.linkedin.com/in/{keyword.replace(' ', '').lower()}{i+1}",
                "email": None,
                "followers": (i + 1) * 500,
                "tags": [keyword],
                "metadata": {
                    "title": f"Senior {keyword} Manager",
                    "company": f"{keyword} Corp",
                    "location": "New York, USA"
                }
            })

        return mock_leads


# Standalone execution function for task queue
async def execute_linkedin_task(task: dict) -> List[Dict]:
    """Execute LinkedIn task using global browser pool"""
    from browser_cluster.manager.browser_pool import get_browser_pool

    pool = get_browser_pool()
    context_id = f"linkedin_task_{task.get('id', 'default')}"

    try:
        context_id, context, instance = await pool.acquire_context(context_id)

        agent = LinkedInAgent(browser_manager=None, db=None)
        # 直接使用 context 进行爬取
        leads = await agent._extract_leads_from_context(context, task)

        return leads
    finally:
        await pool.release_context(context_id)


# Alias for consistency
linkedin_agent = LinkedInAgent
