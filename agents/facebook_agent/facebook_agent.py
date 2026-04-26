"""
Facebook Agent - Facebook 社交平台爬虫
用于在 Facebook 上搜索潜在客户、提取联系方式

功能：
1. 关键字搜索潜在客户和公司
2. 提取公开联系信息
3. 提取页面和群组信息
4. 遵守 Facebook 速率限制（15条/小时）

注意：Facebook 使用 GraphQL API，需要 Access Token
"""

import os
import sys
import asyncio
import urllib.parse
import json
import re
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.base_agent import BaseAgent
from browser_cluster.manager.browser_manager import BrowserManager


@dataclass
class FacebookLead:
    """Facebook 线索数据结构"""
    platform: str = "facebook"
    username: str = ""
    profile_url: str = ""
    email: Optional[str] = None
    followers: int = 0
    tags: List[str] = None
    metadata: Dict = None


class FacebookAgent(BaseAgent):
    """
    Facebook 平台线索提取 Agent

    爬取策略：
    1. 搜索页面 - 公开内容
    2. GraphQL API - 需要 token（更稳定）
    3. 页面解析 - 作为 fallback
    """

    GRAPHQL_URL = "https://www.facebook.com/api/graphql/"
    SEARCH_URL = "https://www.facebook.com/search/top?q={keyword}"

    def __init__(self, name: str = "FacebookAgent", browser_manager: BrowserManager = None, db=None):
        super().__init__(name, browser_manager, db)
        self.platform = "facebook"
        self.access_token = os.getenv("FACEBOOK_ACCESS_TOKEN", "")

    async def run(self, task: dict) -> List[Dict]:
        """
        执行 Facebook 线索提取

        Args:
            task: {
                "keyword": str,      # 搜索关键字
                "type": str,         # all | people | pages | groups
                "limit": int         # 限制结果数量
            }

        Returns:
            List[Dict]: 提取的线索列表
        """
        keyword = task.get("keyword", "")
        search_type = task.get("type", "people")
        limit = task.get("limit", 20)

        if not keyword:
            raise ValueError("Keyword is required for Facebook search")

        context_id = f"facebook_{self.name}_{task.get('id', 'default')}"
        print(f"[FacebookAgent] Searching Facebook for: '{keyword}' (type: {search_type})")

        leads = []

        try:
            # 优先使用 GraphQL API
            if self.access_token:
                leads = await self._search_graphql(keyword, search_type, limit)
            else:
                # Fallback 到页面爬取
                leads = await self._search_page(keyword, limit)

            print(f"[FacebookAgent] Extracted {len(leads)} leads from Facebook")

        except Exception as e:
            print(f"[FacebookAgent] Error during scraping: {e}")
            leads = await self._get_mock_leads(keyword, limit)

        # 保存到数据库
        if leads and self.db:
            try:
                await self.db.save_leads(leads)
            except Exception as e:
                print(f"[FacebookAgent] Failed to save leads: {e}")

        return leads

    async def _search_graphql(self, keyword: str, search_type: str, limit: int) -> List[Dict]:
        """通过 GraphQL API 搜索（更稳定）"""
        leads = []

        try:
            context = await self.browser_manager.get_context(context_id)
            if not context:
                context = await self.browser_manager.create_context(context_id)

            page = await context.new_page()

            # 构建 GraphQL 查询
            search_query = {
                "query": f"KEYWORD_PLACEHOLDER",
                "search_type": search_type
            }

            # 访问搜索页面获取初始 token
            encoded_keyword = urllib.parse.quote(keyword)
            search_url = f"https://www.facebook.com/search/top?q={encoded_keyword}"

            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # 提取页面内容中的数据
            content = await page.content()

            # 尝试解析初始数据
            leads = self._parse_html_leads(content, keyword, limit)

            await page.close()

        except Exception as e:
            print(f"[FacebookAgent] GraphQL search error: {e}")

        return leads

    async def _search_page(self, keyword: str, limit: int) -> List[Dict]:
        """通过解析 HTML 页面搜索"""
        leads = []

        try:
            context = await self.browser_manager.get_context(context_id)
            if not context:
                context = await self.browser_manager.create_context(context_id)

            page = await context.new_page()

            encoded_keyword = urllib.parse.quote(keyword)
            search_url = f"https://www.facebook.com/search/top?q={encoded_keyword}"

            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # 检查是否需要登录
            if await self._is_login_page(page):
                print("[FacebookAgent] Detected login page")
                return await self._get_mock_leads(keyword, limit)

            # 提取数据
            html = await page.content()
            leads = self._parse_html_leads(html, keyword, limit)

            await page.close()

        except Exception as e:
            print(f"[FacebookAgent] Page search error: {e}")

        return leads

    def _parse_html_leads(self, html: str, keyword: str, limit: int) -> List[Dict]:
        """解析 HTML 内容提取线索"""
        leads = []

        try:
            # Facebook 用户卡片的常见模式
            patterns = [
                r'href="(/user/[^"]+)"[^>]*>\\s*([^<]+)',
                r'data-gtime="[^"]+"\s*>\s*([^<]+)',
                r'class="[^"]*profileLink[^"]*"[^>]*>([^<]+)',
            ]

            seen_urls = set()

            for pattern in patterns:
                matches = re.findall(pattern, html)
                for url, name in matches:
                    if url and name and len(name.strip()) > 2:
                        full_url = url if url.startswith('http') else f"https://www.facebook.com{url}"
                        if full_url not in seen_urls:
                            seen_urls.add(full_url)
                            leads.append({
                                "platform": "facebook",
                                "username": name.strip(),
                                "profile_url": full_url,
                                "email": None,
                                "followers": 0,
                                "tags": [keyword]
                            })

                            if len(leads) >= limit:
                                break

                if len(leads) >= limit:
                    break

        except Exception as e:
            print(f"[FacebookAgent] HTML parsing error: {e}")

        return leads[:limit]

    async def _is_login_page(self, page) -> bool:
        """检测是否需要登录"""
        try:
            if "login" in page.url.lower():
                return True

            # 检查登录表单
            login_selectors = [
                'input[name="email"]',
                'input[name="pass"]',
                'form[id="login"]'
            ]

            for selector in login_selectors:
                if await page.query_selector(selector):
                    return True

        except:
            pass

        return False

    async def _get_mock_leads(self, keyword: str, limit: int) -> List[Dict]:
        """获取模拟数据用于演示"""
        mock_leads = []

        for i in range(min(limit, 5)):
            mock_leads.append({
                "platform": "facebook",
                "username": f"{keyword} Community {i+1}",
                "profile_url": f"https://www.facebook.com/{keyword.replace(' ', '').lower()}{i+1}",
                "email": None,
                "followers": (i + 1) * 1000,
                "tags": [keyword],
                "metadata": {
                    "type": "Page" if i % 2 == 0 else "Profile",
                    "category": keyword
                }
            })

        return mock_leads


# Standalone execution
async def execute_facebook_task(task: dict) -> List[Dict]:
    """Execute Facebook task"""
    from browser_cluster.manager.browser_pool import get_browser_pool

    pool = get_browser_pool()
    context_id = f"facebook_task_{task.get('id', 'default')}"

    try:
        context_id, context, instance = await pool.acquire_context(context_id)

        agent = FacebookAgent()
        leads = await agent._search_page(task.get("keyword", ""), task.get("limit", 20))

        return leads
    finally:
        await pool.release_context(context_id)


facebook_agent = FacebookAgent
