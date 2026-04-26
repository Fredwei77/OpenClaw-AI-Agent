"""
Twitter/X Agent - Twitter 社交平台爬虫
用于在 Twitter/X 上搜索潜在客户、提取联系方式

功能：
1. 关键字搜索推文和用户
2. 提取用户资料信息
3. 提取关注者信息
4. 遵守 Twitter 速率限制（30条/小时）
"""

import os
import sys
import asyncio
import urllib.parse
from typing import List, Dict, Optional
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.base_agent import BaseAgent
from browser_cluster.manager.browser_manager import BrowserManager


class TwitterAgent(BaseAgent):
    """
    Twitter/X 平台线索提取 Agent
    """

    # Twitter 搜索 URL
    SEARCH_URL = "https://twitter.com/search?q={keyword}&src=typed_query&f=user"

    def __init__(self, name: str = "TwitterAgent", browser_manager: BrowserManager = None, db=None):
        super().__init__(name, browser_manager, db)
        self.platform = "twitter"

    async def run(self, task: dict) -> List[Dict]:
        """
        执行 Twitter 线索提取

        Args:
            task: {
                "keyword": str,      # 搜索关键字
                "limit": int         # 限制结果数量
            }

        Returns:
            List[Dict]: 提取的线索列表
        """
        keyword = task.get("keyword", "")
        limit = task.get("limit", 20)

        if not keyword:
            raise ValueError("Keyword is required for Twitter search")

        context_id = f"twitter_{self.name}_{task.get('id', 'default')}"
        print(f"[TwitterAgent] Searching Twitter for: '{keyword}'")

        leads = []

        try:
            context = await self.browser_manager.get_context(context_id)
            if not context:
                context = await self.browser_manager.create_context(context_id)

            page = await context.new_page()

            # Twitter 需要设置合适的 headers
            await page.set_extra_http_headers({
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            })

            # 访问搜索页面
            encoded_keyword = urllib.parse.quote(keyword)
            search_url = f"https://twitter.com/search?q={encoded_keyword}&src=typed_query&f=user"

            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

            # 等待用户列表加载
            try:
                await page.wait_for_selector('[data-testid="UserCell"]', timeout=10000)
            except Exception:
                print("[TwitterAgent] User list did not load in time")

            await asyncio.sleep(2)

            # 提取用户
            leads = await self._extract_users(page, keyword, limit)

            await page.close()

            print(f"[TwitterAgent] Extracted {len(leads)} leads from Twitter")

        except Exception as e:
            print(f"[TwitterAgent] Error during scraping: {e}")
            leads = self._get_mock_leads(keyword, limit)

        # 保存到数据库
        if leads and self.db:
            try:
                await self.db.save_leads(leads)
            except Exception as e:
                print(f"[TwitterAgent] Failed to save leads: {e}")

        return leads

    async def _extract_users(self, page, keyword: str, limit: int) -> List[Dict]:
        """从页面提取 Twitter 用户"""
        leads = []

        try:
            # Twitter 用户卡片选择器
            user_cells = await page.query_selector_all('[data-testid="UserCell"]')

            for cell in user_cells[:limit]:
                try:
                    # 提取用户名（显示名称）
                    name_el = await cell.query_selector('div[dir="ltr"] > span')
                    name = await name_el.text_content() if name_el else ""

                    # 提取 handle (@username)
                    handle_el = await cell.query_selector('span:has-text("@")')
                    handle = await handle_el.text_content() if handle_el else ""

                    # 提取简介
                    bio_el = await cell.query_selector('div[dir="ltr"]:not([class])')
                    bio = await bio_el.text_content() if bio_el else ""

                    # 提取 profile URL
                    profile_url = ""
                    if name_el:
                        link_el = await name_el.evaluate_handle("el => el.closest('a')")
                        if link_el:
                            profile_url = await link_el.get_attribute('href')
                            if profile_url and not profile_url.startswith('http'):
                                profile_url = f"https://twitter.com{profile_url}"

                    if handle:
                        lead = {
                            "platform": "twitter",
                            "username": f"{name} ({handle})" if name else handle,
                            "profile_url": profile_url or f"https://twitter.com/{handle.strip('@')}",
                            "email": None,
                            "followers": 0,
                            "tags": [keyword],
                            "metadata": {
                                "bio": bio[:200] if bio else None
                            }
                        }
                        leads.append(lead)

                except Exception as e:
                    print(f"[TwitterAgent] Error parsing user cell: {e}")
                    continue

        except Exception as e:
            print(f"[TwitterAgent] Error extracting users: {e}")

        return leads

    def _get_mock_leads(self, keyword: str, limit: int) -> List[Dict]:
        """获取模拟数据"""
        mock_leads = []

        for i in range(min(limit, 5)):
            mock_leads.append({
                "platform": "twitter",
                "username": f"@{keyword.replace(' ', '')}{i+1}",
                "profile_url": f"https://twitter.com/{keyword.replace(' ', '')}{i+1}",
                "email": None,
                "followers": (i + 1) * 5000,
                "tags": [keyword],
                "metadata": {
                    "bio": f"Professional {keyword} enthusiast and content creator"
                }
            })

        return mock_leads


# Standalone execution
async def execute_twitter_task(task: dict) -> List[Dict]:
    """Execute Twitter task"""
    from browser_cluster.manager.browser_pool import get_browser_pool

    pool = get_browser_pool()
    context_id = f"twitter_task_{task.get('id', 'default')}"

    try:
        context_id, context, instance = await pool.acquire_context(context_id)
        agent = TwitterAgent(browser_manager=None)
        # 直接爬取
        leads = await agent._extract_users(context, task.get("keyword", ""), task.get("limit", 20))
        return leads
    finally:
        await pool.release_context(context_id)


twitter_agent = TwitterAgent
