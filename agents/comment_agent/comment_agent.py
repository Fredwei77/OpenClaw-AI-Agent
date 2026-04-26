"""
Comment Agent - 社交媒体评论自动化 Agent
用于在 LinkedIn、Twitter、Facebook 等平台自动评论

功能：
1. 批量评论帖子
2. 评论模板管理
3. 评论统计和追踪
4. 防封策略（延迟、随机化）
"""

import os
import sys
import asyncio
import random
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.base_agent import BaseAgent
from browser_cluster.manager.browser_manager import BrowserManager


@dataclass
class CommentTask:
    """评论任务"""
    post_url: str
    content: str
    account_id: int = None
    platform: str = "linkedin"


@dataclass
class CommentResult:
    """评论结果"""
    success: bool
    post_url: str
    content: str
    error: str = ""
    commented_at: datetime = None


class CommentAgent(BaseAgent):
    """
    社交媒体评论 Agent

    支持平台：
    - LinkedIn
    - Twitter/X
    - Facebook
    """

    # 平台选择器配置
    PLATFORM_CONFIG = {
        "linkedin": {
            "comment_button": 'button[aria-label*="Comment"]',
            "comment_input": '.comments-comment-box__input',
            "submit_button": 'button[aria-label="Post"]'
        },
        "twitter": {
            "comment_button": '[data-testid="reply"]',
            "comment_input": '[data-testid="tweetTextarea"]',
            "submit_button": '[data-testid="tweetButton"]'
        },
        "facebook": {
            "comment_button": 'a[aria-label*="Comment"]',
            "comment_input": 'form[action*="/comment"] textarea',
            "submit_button": 'button[type="submit"]'
        }
    }

    def __init__(self, name: str = "CommentAgent", browser_manager: BrowserManager = None, db=None):
        super().__init__(name, browser_manager, db)

        # 评论模板
        self.templates = [
            "Great insights! {topic} is indeed crucial for growth.",
            "I completely agree with this perspective on {topic}.",
            "Interesting approach! Would love to learn more about {topic}.",
            "This is exactly what we've been experiencing with {topic}.",
            "Thanks for sharing! {topic} has been a game-changer for us."
        ]

    async def run(self, task: dict) -> Dict:
        """
        执行评论任务

        Args:
            task: {
                "comments": List[Dict],     # 评论列表
                "platform": str,             # 平台
                "delay_range": tuple,       # 延迟范围 (min, max) 秒
                "use_templates": bool        # 是否使用模板
            }

        Returns:
            Dict: 评论统计结果
        """
        comments = task.get("comments", [])
        platform = task.get("platform", "linkedin").lower()
        delay_range = task.get("delay_range", (3, 8))
        use_templates = task.get("use_templates", True)

        if not comments:
            raise ValueError("No comments provided")

        print(f"[CommentAgent] Starting {len(comments)} comments on {platform}")

        results = []
        total_success = 0
        total_failed = 0

        config = self.PLATFORM_CONFIG.get(platform, self.PLATFORM_CONFIG["linkedin"])

        for i, comment_data in enumerate(comments):
            post_url = comment_data.get("post_url")
            content = comment_data.get("content", "")

            # 使用模板时随机选择
            if use_templates and not content:
                content = random.choice(self.templates)
                topic = comment_data.get("topic", "business")
                content = content.format(topic=topic)

            result = await self._post_comment(post_url, content, platform, config)
            results.append(result)

            if result.success:
                total_success += 1
            else:
                total_failed += 1

            # 随机延迟（防封）
            if i < len(comments) - 1:
                delay = random.uniform(*delay_range)
                await asyncio.sleep(delay)

        # 保存评论日志
        if self.db:
            await self._save_comment_logs(results, platform)

        return {
            "total": len(comments),
            "success": total_success,
            "failed": total_failed,
            "platform": platform,
            "results": results
        }

    async def _post_comment(self, post_url: str, content: str, platform: str, config: Dict) -> CommentResult:
        """在指定帖子下评论"""
        result = CommentResult(
            success=False,
            post_url=post_url,
            content=content,
            commented_at=datetime.now()
        )

        context_id = f"comment_{platform}_{id(post_url)}"

        try:
            context = await self.browser_manager.get_context(context_id)
            if not context:
                context = await self.browser_manager.create_context(context_id)

            page = await context.new_page()

            # 访问帖子
            await page.goto(post_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            # 点击评论按钮
            comment_button = await page.wait_for_selector(config["comment_button"], timeout=5000)
            await comment_button.click()
            await asyncio.sleep(1)

            # 输入评论
            comment_input = await page.wait_for_selector(config["comment_input"], timeout=5000)
            await comment_input.fill(content)
            await asyncio.sleep(0.5)

            # 提交评论
            submit_button = await page.wait_for_selector(config["submit_button"], timeout=5000)
            await submit_button.click()
            await asyncio.sleep(2)

            result.success = True
            print(f"[CommentAgent] Commented on {post_url}")

            await page.close()

        except Exception as e:
            result.error = str(e)
            print(f"[CommentAgent] Failed to comment on {post_url}: {e}")

        return result

    async def _save_comment_logs(self, results: List[CommentResult], platform: str):
        """保存评论日志"""
        try:
            for result in results:
                if result.success:
                    print(f"[CommentAgent] Logged comment on {result.post_url}")
        except Exception as e:
            print(f"[CommentAgent] Failed to save comment logs: {e}")


# Standalone execution
async def execute_comment_task(task: dict) -> Dict:
    """Execute comment task"""
    agent = CommentAgent()
    return await agent.run(task)


comment_agent = CommentAgent
