"""
Social Handler - 社交平台自动化操作处理器
提供 follow、collect 等社交自动化功能

功能：
1. follow_user - 关注用户
2. collect_leads - 收集线索数据
3. send_message - 发送消息

特点：
- 遵守平台速率限制
- 重试逻辑（指数退避）
- 反封禁措施（随机延迟）
"""

import asyncio
import random
import re
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

try:
    from playwright.async_api import Page, BrowserContext
except ImportError:
    Page = None
    BrowserContext = None


class ActionStatus(str, Enum):
    """操作状态"""
    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    BLOCKED = "blocked"
    RETRYING = "retrying"


@dataclass
class ActionResult:
    """操作结果"""
    status: ActionStatus
    message: str
    data: Optional[Dict] = None
    retry_count: int = 0


class RateLimitConfig:
    """平台速率限制配置"""
    PLATFORM_LIMITS = {
        "twitter": {"follow": 400, "unfollow": 400, "like": 1000, "retweet": 300, "message": 1000, "window": 3600},
        "x": {"follow": 400, "unfollow": 400, "like": 1000, "retweet": 300, "message": 1000, "window": 3600},
        "linkedin": {"connect": 20, "message": 25, "visit": 100, "window": 3600},
        "instagram": {"follow": 200, "unfollow": 200, "like": 350, "comment": 60, "message": 50, "window": 3600},
        "facebook": {"friend": 50, "message": 200, "like": 500, "window": 3600},
    }

    @classmethod
    def get_limit(cls, platform: str, action: str) -> tuple[int, int]:
        """获取限制 (max_requests, window_seconds)"""
        platform_lower = platform.lower()
        if platform_lower in cls.PLATFORM_LIMITS:
            action_lower = action.lower()
            limits = cls.PLATFORM_LIMITS[platform_lower]
            if action_lower in limits:
                return limits[action_lower], limits.get("window", 3600)
        return 50, 3600  # 默认限制


class SocialHandler:
    """
    社交平台自动化操作处理器

    使用方式：
    1. 初始化时注入 Page 对象
    2. 调用 follow/collect 等方法
    3. 自动处理速率限制和反封禁
    """

    def __init__(
        self,
        page: Page,
        platform: str = "twitter",
        rate_limiter: Callable = None,
        on_action: Callable = None
    ):
        """
        初始化社交处理器

        Args:
            page: Playwright Page 对象
            platform: 平台名称 (twitter, linkedin, instagram, etc.)
            rate_limiter: 速率限制器回调函数 (可选)
            on_action: 动作执行后的回调函数 (可选)
        """
        self.page = page
        self.platform = platform.lower()
        self.rate_limiter = rate_limiter
        self.on_action = on_action

        # 反封禁配置
        self.min_delay = 2.0  # 最小延迟（秒）
        self.max_delay = 8.0  # 最大延迟（秒）
        self.retry_delay = 5.0  # 重试前延迟（秒）

        # 速率限制追踪
        self._action_counts: Dict[str, List[datetime]] = {}

    async def _random_delay(self, action: str = None):
        """随机延迟，模拟人类行为"""
        delay = random.uniform(self.min_delay, self.max_delay)

        # 特殊动作额外延迟
        if action == "follow":
            delay += random.uniform(1.0, 3.0)
        elif action == "message":
            delay += random.uniform(2.0, 5.0)

        await asyncio.sleep(delay)

    async def _check_rate_limit(self, action: str) -> bool:
        """
        检查是否超过速率限制

        Returns:
            True if under limit, False if rate limited
        """
        max_requests, window_seconds = RateLimitConfig.get_limit(self.platform, action)

        now = datetime.now()
        key = f"{self.platform}_{action}"

        # 清理过期记录
        if key in self._action_counts:
            cutoff = now.timestamp() - window_seconds
            self._action_counts[key] = [
                t for t in self._action_counts[key] if t.timestamp() > cutoff
            ]
        else:
            self._action_counts[key] = []

        # 检查限制
        if len(self._action_counts[key]) >= max_requests:
            return False

        # 记录本次操作
        self._action_counts[key].append(now)
        return True

    async def _wait_for_rate_limit(self, action: str) -> float:
        """
        等待速率限制可用

        Returns:
            等待的秒数
        """
        max_requests, window_seconds = RateLimitConfig.get_limit(self.platform, action)

        key = f"{self.platform}_{action}"
        if key not in self._action_counts:
            return 0.0

        now = datetime.now()
        oldest = min(self._action_counts[key])
        next_available = oldest.timestamp() + window_seconds
        wait = next_available - now.timestamp()

        return max(0.0, wait)

    async def _execute_with_retry(
        self,
        action: str,
        func: Callable,
        max_retries: int = 3,
        **kwargs
    ) -> ActionResult:
        """
        执行操作并处理重试

        Args:
            action: 操作名称（用于速率限制）
            func: 要执行的异步函数
            max_retries: 最大重试次数
            **kwargs: 传递给函数的参数
        """
        retry_count = 0

        while retry_count <= max_retries:
            # 检查速率限制
            if not await self._check_rate_limit(action):
                wait_time = await self._wait_for_rate_limit(action)
                if wait_time > 60:
                    return ActionResult(
                        status=ActionStatus.RATE_LIMITED,
                        message=f"Rate limited for {action}, would need to wait {wait_time:.1f}s",
                        retry_count=retry_count
                    )
                await asyncio.sleep(wait_time)

            try:
                result = await func(**kwargs)

                # 触发回调
                if self.on_action:
                    await self.on_action(action, result)

                return ActionResult(
                    status=ActionStatus.SUCCESS,
                    message=f"{action} completed successfully",
                    data=result,
                    retry_count=retry_count
                )

            except Exception as e:
                error_msg = str(e).lower()

                # 检测是否被封禁
                if any(x in error_msg for x in ["blocked", "suspended", "locked", "challenge"]):
                    return ActionResult(
                        status=ActionStatus.BLOCKED,
                        message=f"Account may be blocked: {e}",
                        retry_count=retry_count
                    )

                # 检测是否需要重试
                if retry_count < max_retries:
                    retry_count += 1
                    wait = self.retry_delay * (2 ** retry_count)  # 指数退避
                    await asyncio.sleep(wait)
                    continue

                return ActionResult(
                    status=ActionStatus.FAILED,
                    message=f"{action} failed after {retry_count} retries: {e}",
                    retry_count=retry_count
                )

        return ActionResult(
            status=ActionStatus.FAILED,
            message=f"{action} failed after {max_retries} retries",
            retry_count=retry_count
        )

    async def follow_user(self, profile_url: str = None, username: str = None) -> ActionResult:
        """
        关注用户

        Args:
            profile_url: 用户主页 URL
            username: 用户名（不含 @）

        Returns:
            ActionResult: 操作结果
        """
        if not profile_url and not username:
            return ActionResult(
                status=ActionStatus.FAILED,
                message="Either profile_url or username is required"
            )

        if profile_url is None:
            profile_url = f"https://www.{self.platform}.com/{username}"

        async def _do_follow():
            await self.page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)  # 等待页面完全加载

            # 平台特定的 follow 按钮选择器
            selectors = self._get_follow_selectors()

            for selector in selectors:
                try:
                    button = await self.page.query_selector(selector)
                    if button:
                        # 检查按钮是否可用
                        is_disabled = await button.get_attribute("disabled")
                        if is_disabled:
                            continue

                        # 点击 follow 按钮
                        await button.click()
                        await self._random_delay("follow")

                        # 验证是否成功
                        if await self._verify_follow_success(selectors):
                            return {"profile_url": profile_url, "action": "follow"}
                except Exception:
                    continue

            raise Exception("Could not find or click follow button")

        return await self._execute_with_retry("follow", _do_follow)

    def _get_follow_selectors(self) -> List[str]:
        """获取平台特定的 follow 按钮选择器"""
        selectors_map = {
            "twitter": [
                '[data-testid="followButton"]',
                'div[data-testid="followButton"] span:has-text("Follow")',
                'button:has-text("Follow")',
            ],
            "x": [
                '[data-testid="followButton"]',
                'div[data-testid="followButton"] span:has-text("Follow")',
                'button:has-text("Follow")',
            ],
            "linkedin": [
                'button[aria-label*="Connect"]',
                '.pv-top-card-v2-ctas button:has-text("Connect")',
                '.artdeco-button:has-text("Connect")',
            ],
            "instagram": [
                'button:has-text("Follow")',
                '[role="button"]:has-text("Follow")',
            ],
            "facebook": [
                'button:has-text("Add Friend")',
                '[data-testid="addFriendButton"]',
            ],
        }
        return selectors_map.get(self.platform, ['button:has-text("Follow")'])

    async def _verify_follow_success(self, selectors: List[str]) -> bool:
        """验证 follow 是否成功"""
        await asyncio.sleep(1)  # 等待 UI 更新

        for selector in selectors:
            try:
                button = await self.page.query_selector(selector)
                if button:
                    text = await button.text_content()
                    if text and any(x in text.lower() for x in ["following", "requested", "connect"]):
                        return True
            except Exception:
                continue
        return False

    async def collect_leads(
        self,
        selectors: Dict[str, str] = None,
        max_items: int = 20,
        scroll_count: int = 3
    ) -> ActionResult:
        """
        收集页面上的线索数据

        Args:
            selectors: CSS 选择器映射 {
                "item": "用户卡片选择器",
                "name": "姓名选择器",
                "username": "用户名选择器",
                "bio": "简介选择器",
                "link": "链接选择器"
            }
            max_items: 最大收集数量
            scroll_count: 滚动加载次数

        Returns:
            ActionResult: 收集的线索列表
        """
        default_selectors = self._get_default_collect_selectors()
        selectors = selectors or default_selectors

        items = []

        async def _do_collect():
            # 滚动加载更多内容
            for i in range(scroll_count):
                await self.page.evaluate(f"window.scrollBy(0, {800 + i * 200})")
                await asyncio.sleep(random.uniform(1.0, 2.0))

            # 获取所有卡片
            item_selector = selectors.get("item")
            if not item_selector:
                return {"items": [], "count": 0, "error": "Missing item selector in selectors config"}

            cards = await self.page.query_selector_all(item_selector)

            for card in cards[:max_items]:
                try:
                    lead = {}

                    # 提取姓名/显示名
                    if selectors.get("name"):
                        name_el = await card.query_selector(selectors["name"])
                        if name_el:
                            lead["name"] = (await name_el.text_content()).strip()

                    # 提取用户名/handle
                    if selectors.get("username"):
                        username_el = await card.query_selector(selectors["username"])
                        if username_el:
                            lead["username"] = (await username_el.text_content()).strip()

                    # 提取简介
                    if selectors.get("bio"):
                        bio_el = await card.query_selector(selectors["bio"])
                        if bio_el:
                            lead["bio"] = (await bio_el.text_content()).strip()[:200]

                    # 提取链接
                    if selectors.get("link"):
                        link_el = await card.query_selector(selectors["link"])
                        if link_el:
                            href = await link_el.get_attribute("href")
                            if href:
                                if not href.startswith("http"):
                                    href = f"https://www.{self.platform}.com{href}"
                                lead["profile_url"] = href

                    # 提取粉丝数（如果有）
                    if selectors.get("followers"):
                        followers_el = await card.query_selector(selectors["followers"])
                        if followers_el:
                            text = await followers_el.text_content()
                            lead["followers"] = self._parse_number(text)

                    if lead.get("name") or lead.get("username"):
                        lead["platform"] = self.platform
                        lead["tags"] = []
                        items.append(lead)

                except Exception as e:
                    continue

            return {"items": items, "count": len(items)}

        return await self._execute_with_retry("collect", _do_collect)

    def _get_default_collect_selectors(self) -> Dict[str, str]:
        """获取平台默认的收集选择器"""
        selectors_map = {
            "twitter": {
                "item": '[data-testid="UserCell"]',
                "name": 'div[dir="ltr"] > span',
                "username": 'span:has-text("@")',
                "bio": 'div[dir="ltr"]:not([class])',
                "link": 'a[href*="/"]',
            },
            "x": {
                "item": '[data-testid="UserCell"]',
                "name": 'div[dir="ltr"] > span',
                "username": 'span:has-text("@")',
                "bio": 'div[dir="ltr"]:not([class])',
                "link": 'a[href*="/"]',
            },
            "linkedin": {
                "item": '.entity-result, .search-result__occluded-item',
                "name": '.entity-result__title-text a, .search-result__info a',
                "username": '.entity-result__title-text a span',
                "bio": '.entity-result__primary-subtitle, .search-result__snippet',
                "link": '.entity-result__title-text a',
            },
            "instagram": {
                "item": 'article a[href*="/p/"]',
                "name": 'article h2 a',
                "username": 'article h2 a',
                "bio": 'article p',
                "link": 'article a[href*="/p/"]',
            },
        }
        return selectors_map.get(self.platform, {})

    def _parse_number(self, text: str) -> int:
        """解析数字字符串（如 1.2K, 3.5M）"""
        if not text:
            return 0

        text = text.strip().replace(",", "")
        match = re.search(r'([\d.]+)\s*([KMB]?)', text, re.IGNORECASE)
        if not match:
            return 0

        num = float(match.group(1))
        suffix = match.group(2).upper() if match.group(2) else ""

        if suffix == "K":
            return int(num * 1000)
        elif suffix == "M":
            return int(num * 1000000)
        elif suffix == "B":
            return int(num * 1000000000)
        return int(num)

    async def send_message(
        self,
        recipient: str = None,
        profile_url: str = None,
        message: str = None,
        direct_url: str = None
    ) -> ActionResult:
        """
        发送私信

        Args:
            recipient: 收件人用户名
            profile_url: 收件人主页 URL
            direct_url: 私信直接链接
            message: 消息内容

        Returns:
            ActionResult: 操作结果
        """
        if not message:
            return ActionResult(
                status=ActionStatus.FAILED,
                message="Message content is required"
            )

        if not direct_url and not profile_url and not recipient:
            return ActionResult(
                status=ActionStatus.FAILED,
                message="Either direct_url, profile_url, or recipient is required"
            )

        # 构建 DM URL
        if direct_url is None:
            if profile_url:
                direct_url = f"{profile_url}/overlay/messaging"
            else:
                direct_url = f"https://www.{self.platform}.com/messages/compose?to=@{recipient}"

        async def _do_send():
            await self.page.goto(direct_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            # 平台特定的输入框和发送按钮
            selectors = self._get_message_selectors()

            # 等待并输入消息
            textarea = await self.page.wait_for_selector(selectors["input"], timeout=10000)
            await textarea.fill(message)

            # 点击发送
            send_button = await self.page.query_selector(selectors["send"])
            if send_button:
                await send_button.click()
                await self._random_delay("message")

            return {
                "recipient": recipient or profile_url,
                "message": message,
                "sent_at": datetime.now().isoformat()
            }

        return await self._execute_with_retry("message", _do_send)

    def _get_message_selectors(self) -> Dict[str, str]:
        """获取平台特定的消息选择器"""
        selectors_map = {
            "twitter": {
                "input": 'div[data-testid="dmComposerTextInput"]',
                "send": 'div[data-testid="dmComposerSendButton"]',
            },
            "x": {
                "input": 'div[data-testid="dmComposerTextInput"]',
                "send": 'div[data-testid="dmComposerSendButton"]',
            },
            "linkedin": {
                "input": 'div[contenteditable="true"][data-artdevo-is-focusorigin="true"]',
                "send": 'button[aria-label*="Send"]',
            },
            "instagram": {
                "input": 'textarea[placeholder*="Message"]',
                "send": 'button:has-text("Send")',
            },
        }
        return selectors_map.get(self.platform, {
            "input": 'textarea, div[contenteditable="true"]',
            "send": 'button:has-text("Send")'
        })


# 便捷函数
async def follow_user(handler: SocialHandler, profile_url: str = None, username: str = None) -> ActionResult:
    """关注用户的便捷函数"""
    return await handler.follow_user(profile_url, username)


async def collect_leads(handler: SocialHandler, selectors: Dict = None, max_items: int = 20) -> ActionResult:
    """收集线索的便捷函数"""
    return await handler.collect_leads(selectors, max_items)


async def send_message(handler: SocialHandler, recipient: str, message: str) -> ActionResult:
    """发送消息的便捷函数"""
    return await handler.send_message(recipient=recipient, message=message)
