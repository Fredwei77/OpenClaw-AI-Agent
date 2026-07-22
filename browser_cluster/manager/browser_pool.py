"""
Persistent Browser Pool - 常驻浏览器连接池
解决每次请求启动/关闭浏览器导致的超时问题

架构：
1. BrowserPoolManager 作为常驻进程管理多个 BrowserManager 实例
2. 每个账户/会话分配独立的 context
3. 使用引用计数来管理 context 的生命周期
4. 支持代理轮换和账户隔离
"""

import asyncio
import os
import uuid
import weakref
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright
except ImportError:
    # Fallback for when playwright is not installed
    Playwright = None
    Browser = None
    BrowserContext = None


@dataclass
class BrowserInstance:
    """单个浏览器实例的元数据"""
    instance_id: str
    browser: Optional[Browser] = None
    playwright: Optional[Playwright] = None
    contexts: Dict[str, BrowserContext] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)
    is_healthy: bool = True
    proxy_config: Optional[dict] = None
    user_data_dir: Optional[str] = None
    reference_count: int = 0
    cdp_url: Optional[str] = None  # Chrome DevTools Protocol URL
    is_connected: bool = False  # True if connected via CDP


class BrowserPoolManager:
    """
    常驻浏览器连接池管理器

    使用方式：
    1. 启动时初始化池
    2. 通过 acquire_context() 获取 context
    3. 使用完后通过 release_context() 释放
    4. 关闭时调用 shutdown() 清理
    """

    def __init__(
        self,
        max_browsers: int = 3,
        context_timeout: int = 30000,
        browser_timeout: int = 300000,  # 5 minutes
        cleanup_interval: int = 60
    ):
        self.max_browsers = max_browsers
        self.context_timeout = context_timeout
        self.browser_timeout = browser_timeout
        self.cleanup_interval = cleanup_interval

        self._browsers: Dict[str, BrowserInstance] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._started = False

    async def start(self):
        """启动浏览器池管理器"""
        if self._started:
            return

        print(f"[BrowserPool] Starting pool manager (max_browsers={self.max_browsers})")
        self._started = True

        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self):
        """停止浏览器池管理器并清理所有资源"""
        print("[BrowserPool] Stopping pool manager...")
        self._started = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        async with self._lock:
            for instance_id, instance in list(self._browsers.items()):
                await self._close_browser_instance(instance)
            self._browsers.clear()

        print("[BrowserPool] Pool manager stopped")

    async def _cleanup_loop(self):
        """定期清理不健康的浏览器实例和超时context"""
        while self._started:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_stale_instances()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[BrowserPool] Cleanup error: {e}")

    async def _cleanup_stale_instances(self):
        """清理过期或不健康的浏览器实例"""
        async with self._lock:
            stale_ids = []
            now = datetime.now()

            for instance_id, instance in self._browsers.items():
                # 清理超过超时时间且无引用的实例
                if (instance.reference_count == 0 and
                    now - instance.last_used > timedelta(milliseconds=self.browser_timeout)):
                    stale_ids.append(instance_id)

                # 检查浏览器健康状态
                if instance.browser and not instance.is_healthy:
                    stale_ids.append(instance_id)

            for instance_id in stale_ids:
                print(f"[BrowserPool] Cleaning up stale instance: {instance_id}")
                await self._close_browser_instance(self._browsers[instance_id])
                del self._browsers[instance_id]

    async def _close_browser_instance(self, instance: BrowserInstance):
        """关闭单个浏览器实例"""
        try:
            # 关闭所有 contexts
            for ctx_id, context in list(instance.contexts.items()):
                try:
                    await context.close()
                except Exception as e:
                    print(f"[BrowserPool] Error closing context {ctx_id}: {e}")
            instance.contexts.clear()

            # 关闭浏览器
            if instance.browser:
                try:
                    await instance.browser.close()
                except Exception as e:
                    print(f"[BrowserPool] Error closing browser: {e}")

            # 停止 playwright
            if instance.playwright:
                try:
                    await instance.playwright.stop()
                except Exception as e:
                    print(f"[BrowserPool] Error stopping playwright: {e}")

        except Exception as e:
            print(f"[BrowserPool] Error in _close_browser_instance: {e}")

    async def _create_browser_instance(self, proxy: dict = None, user_data_dir: str = None, cdp_url: str = None) -> BrowserInstance:
        """创建新的浏览器实例

        Args:
            proxy: 代理配置
            user_data_dir: Chrome 用户数据目录（用于保持登录态）
            cdp_url: Chrome DevTools Protocol URL（优先使用）
        """
        instance_id = str(uuid.uuid4())[:8]

        playwright = await async_playwright().start()

        browser = None

        # 优先使用 CDP 连接（最稳定的方式保持登录态）
        if cdp_url:
            try:
                print(f"[BrowserPool] Connecting to Chrome via CDP: {cdp_url}")
                browser = await playwright.chromium.connect_over_cdp(cdp_url)
                instance = BrowserInstance(
                    instance_id=instance_id,
                    browser=browser,
                    playwright=playwright,
                    proxy_config=proxy,
                    user_data_dir=user_data_dir,
                    cdp_url=cdp_url,
                    is_connected=True
                )
                print(f"[BrowserPool] Connected to Chrome via CDP: {instance_id}")
                return instance
            except Exception as e:
                print(f"[BrowserPool] CDP connection failed: {e}, falling back to launch")
                # CDP 失败时停止 playwright，避免资源泄漏
                await playwright.stop()
                playwright = None

        # 使用普通 launch 方式
        launch_options = {
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox"
            ]
        }

        # 如果配置了 user_data_dir，使用它来保持登录态
        if user_data_dir:
            # 确保目录存在
            if os.path.exists(user_data_dir):
                launch_options["user_data_dir"] = user_data_dir

        if proxy:
            launch_options["proxy"] = {
                "server": proxy["host"],
                "username": proxy.get("username", ""),
                "password": proxy.get("password", "")
            }

        browser = await playwright.chromium.launch(**launch_options)

        instance = BrowserInstance(
            instance_id=instance_id,
            browser=browser,
            playwright=playwright,
            proxy_config=proxy,
            user_data_dir=user_data_dir,
            cdp_url=cdp_url,
            is_connected=False
        )

        print(f"[BrowserPool] Created new browser instance: {instance_id}")
        return instance

    async def _get_available_instance(self, proxy: dict = None, user_data_dir: str = None, cdp_url: str = None) -> BrowserInstance:
        """获取或创建一个可用的浏览器实例"""
        # 尝试找一个健康的、有剩余容量的实例
        async with self._lock:
            for instance_id, instance in self._browsers.items():
                if instance.browser:
                    try:
                        if hasattr(instance.browser, "is_connected") and not instance.browser.is_connected():
                            instance.is_healthy = False
                            continue
                    except Exception:
                        instance.is_healthy = False
                        continue
                if instance.is_healthy and len(instance.contexts) < 10:  # 每个浏览器最多10个context
                    # 检查代理配置、user_data_dir 和 cdp_url 是否匹配
                    if proxy == instance.proxy_config or not proxy:
                        if user_data_dir == instance.user_data_dir or not user_data_dir:
                            if cdp_url == instance.cdp_url or not cdp_url:
                                return instance

            # 如果没有可用实例且未达到上限，创建新的
            if len(self._browsers) < self.max_browsers:
                instance = await self._create_browser_instance(proxy, user_data_dir, cdp_url)
                self._browsers[instance.instance_id] = instance
                return instance

            # 如果达到上限，等待一个实例变得可用
            raise RuntimeError("[BrowserPool] All browser instances are at capacity. Please wait and retry.")

    async def acquire_context(
        self,
        context_id: str = None,
        proxy: dict = None,
        user_data_dir: str = None,
        cdp_url: str = None
    ) -> tuple[str, BrowserContext, BrowserInstance]:
        """
        获取一个浏览器 context

        Args:
            context_id: Context ID
            proxy: 代理配置
            user_data_dir: Chrome 用户数据目录（用于保持登录态）
            cdp_url: Chrome DevTools Protocol URL（优先使用）


        Returns:
            tuple[str, BrowserContext, BrowserInstance]: (context_id, context, instance)
            使用完后必须调用 release_context()
        """
        if not self._started:
            await self.start()

        if context_id is None:
            context_id = str(uuid.uuid4())[:12]

        instance = await self._get_available_instance(proxy, user_data_dir, cdp_url)

        async with self._lock:
            instance.reference_count += 1
            instance.last_used = datetime.now()

        # 如果已经有这个 context_id，直接返回
        if context_id in instance.contexts:
            return context_id, instance.contexts[context_id], instance

        # CDP 模式：使用 Chrome 默认 context（包含登录态 Cookie）
        if instance.is_connected and instance.browser.contexts:
            context = instance.browser.contexts[0]
            instance.contexts[context_id] = context
            instance.last_used = datetime.now()
            print(f"[BrowserPool] Acquired default context {context_id} via CDP (has cookies)")
            return context_id, context, instance

        # 创建新的 context
        context_options = {
            "viewport": {"width": 1280, "height": 720},
            "timezone_id": "America/New_York",
            "locale": "en-US",
        }

        if proxy:
            context_options["proxy"] = {
                "server": proxy["host"],
                "username": proxy.get("username", ""),
                "password": proxy.get("password", "")
            }

        try:
            context = await instance.browser.new_context(**context_options)
        except Exception as e:
            message = str(e).lower()
            if "target page, context or browser has been closed" in message or "targetclosed" in message:
                print(f"[BrowserPool] Browser instance {instance.instance_id} is closed; recreating once")
                async with self._lock:
                    instance.is_healthy = False
                    instance.reference_count = max(0, instance.reference_count - 1)
                    if instance.instance_id in self._browsers:
                        await self._close_browser_instance(instance)
                        del self._browsers[instance.instance_id]
                instance = await self._get_available_instance(proxy, user_data_dir, cdp_url)
                async with self._lock:
                    instance.reference_count += 1
                    instance.last_used = datetime.now()
                context = await instance.browser.new_context(**context_options)
            else:
                async with self._lock:
                    instance.reference_count = max(0, instance.reference_count - 1)
                raise
        instance.contexts[context_id] = context
        instance.last_used = datetime.now()

        print(f"[BrowserPool] Acquired context {context_id} on instance {instance.instance_id}")
        return context_id, context, instance

    async def release_context(self, context_id: str, instance_id: str = None):
        """
        释放一个浏览器 context（减少引用计数）
        Context不会被关闭，只是标记为可用
        """
        async with self._lock:
            for inst_id, instance in self._browsers.items():
                if context_id in instance.contexts:
                    instance.reference_count = max(0, instance.reference_count - 1)
                    instance.last_used = datetime.now()
                    print(f"[BrowserPool] Released context {context_id} (ref={instance.reference_count})")
                    return

    async def close_context(self, context_id: str, instance_id: str = None):
        """强制关闭一个特定的 context"""
        async with self._lock:
            for inst_id, instance in self._browsers.items():
                if context_id in instance.contexts:
                    # CDP 模式下不关闭默认 context（是用户的 Chrome 主 context）
                    if instance.is_connected:
                        del instance.contexts[context_id]
                        instance.reference_count = max(0, instance.reference_count - 1)
                        return
                    try:
                        await instance.contexts[context_id].close()
                    except Exception as e:
                        print(f"[BrowserPool] Error closing context {context_id}: {e}")
                    finally:
                        del instance.contexts[context_id]
                        instance.reference_count = max(0, instance.reference_count - 1)
                    return

    async def get_pool_status(self) -> Dict:
        """获取连接池状态信息"""
        async with self._lock:
            total_contexts = sum(len(inst.contexts) for inst in self._browsers.values())
            total_refs = sum(inst.reference_count for inst in self._browsers.values())

            return {
                "total_browsers": len(self._browsers),
                "max_browsers": self.max_browsers,
                "total_contexts": total_contexts,
                "active_references": total_refs,
                "instances": [
                    {
                        "instance_id": inst.instance_id,
                        "context_count": len(inst.contexts),
                        "reference_count": inst.reference_count,
                        "is_healthy": inst.is_healthy,
                        "is_connected": inst.is_connected,
                        "cdp_url": inst.cdp_url,
                        "user_data_dir": inst.user_data_dir,
                        "created_at": inst.created_at.isoformat(),
                        "last_used": inst.last_used.isoformat()
                    }
                    for inst in self._browsers.values()
                ]
            }


# 全局单例 - 在应用启动时初始化
_global_pool: Optional[BrowserPoolManager] = None


def get_browser_pool() -> BrowserPoolManager:
    """获取全局浏览器池实例"""
    global _global_pool
    if _global_pool is None:
        max_browsers = int(os.getenv("MAX_BROWSER_INSTANCES", "3"))
        _global_pool = BrowserPoolManager(max_browsers=max_browsers)
    return _global_pool


async def init_browser_pool():
    """初始化全局浏览器池"""
    pool = get_browser_pool()
    await pool.start()
    return pool


async def shutdown_browser_pool():
    """关闭全局浏览器池"""
    global _global_pool
    if _global_pool:
        await _global_pool.stop()
        _global_pool = None
