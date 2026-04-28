"""
Task Queue and Scheduler System
任务队列和调度系统

功能：
1. 异步任务执行（不阻塞 HTTP 请求）
2. 任务限速（LinkedIn 20条/小时，Facebook 15条/小时）
3. 任务状态跟踪
4. 失败重试机制
5. 优先级队列
"""

import asyncio
import json
import os
import sys
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import traceback

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import update_task_status, get_task


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    """任务优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


# Platform rate limits (per hour)
PLATFORM_RATE_LIMITS = {
    "linkedin": 20,
    "facebook": 15,
    "twitter": 30,
    "x": 30,
    "instagram": 20,
    "tiktok": 15,
    "default": 50
}


@dataclass
class QueuedTask:
    """队列中的任务"""
    task_id: int
    user_id: int
    agent_name: str
    task_type: str
    payload: Dict
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict] = None
    error: Optional[str] = None
    platform: Optional[str] = None  # For rate limiting


class RateLimiter:
    """
    基于滑动窗口的速率限制器
    实现平滑的请求速率控制
    """

    def __init__(self, max_requests: int, window_seconds: int = 3600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: List[datetime] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """
        尝试获取一个请求配额

        Returns:
            True if allowed, False if rate limited
        """
        async with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=self.window_seconds)

            # 清理过期的请求记录
            self.requests = [req_time for req_time in self.requests if req_time > cutoff]

            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True

            return False

    async def wait_time(self) -> float:
        """获取需要等待的时间（秒）"""
        async with self._lock:
            if len(self.requests) < self.max_requests:
                return 0.0

            oldest = min(self.requests)
            next_available = oldest + timedelta(seconds=self.window_seconds)
            wait = (next_available - datetime.now()).total_seconds()
            return max(0.0, wait)


class RedisRateLimiter:
    """
    基于 Redis 的分布式速率限制器
    使用滑动窗口算法，支持多实例部署
    """

    def __init__(self, redis_client, key_prefix: str = "ratelimit", max_requests: int = 50, window_seconds: int = 3600):
        self.redis = redis_client
        self.key_prefix = key_prefix
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def _get_key(self, platform: str) -> str:
        """获取 Redis key"""
        return f"{self.key_prefix}:{platform}"

    async def acquire(self, platform: str = "default") -> bool:
        """
        尝试获取一个请求配额

        Returns:
            True if allowed, False if rate limited
        """
        key = self._get_key(platform)
        now = datetime.now().timestamp()
        window_start = now - self.window_seconds

        try:
            # 使用 Redis sorted set 实现滑动窗口
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, self.window_seconds + 10)
            results = await pipe.execute()

            current_count = results[1]

            if current_count < self.max_requests:
                return True
            else:
                # 超限，移除刚添加的
                await self.redis.zrem(key, str(now))
                return False

        except Exception as e:
            print(f"[RedisRateLimiter] Error: {e}")
            return True  # Redis 失败时放行

    async def wait_time(self, platform: str = "default") -> float:
        """获取需要等待的时间（秒）"""
        key = self._get_key(platform)
        now = datetime.now().timestamp()

        try:
            oldest = await self.redis.zrange(key, 0, 0, withscores=True)
            if not oldest:
                return 0.0

            oldest_timestamp = oldest[0][1]
            next_available = oldest_timestamp + self.window_seconds
            wait = next_available - now
            return max(0.0, wait)

        except Exception as e:
            print(f"[RedisRateLimiter] Error getting wait time: {e}")
            return 0.0

    async def get_usage(self, platform: str = "default") -> int:
        """获取当前使用量"""
        key = self._get_key(platform)
        now = datetime.now().timestamp()
        window_start = now - self.window_seconds

        try:
            await self.redis.zremrangebyscore(key, 0, window_start)
            return await self.redis.zcard(key)
        except Exception:
            return 0


class DistributedLock:
    """
    基于 Redis 的分布式锁
    用于多实例部署时的资源互斥
    """

    def __init__(self, redis_client, lock_name: str, expire_seconds: int = 30):
        self.redis = redis_client
        self.lock_name = f"lock:{lock_name}"
        self.expire_seconds = expire_seconds
        self._locked = False

    async def acquire(self, blocking: bool = True, timeout: int = 10) -> bool:
        """
        获取锁

        Args:
            blocking: 是否阻塞等待
            timeout: 阻塞超时时间（秒）

        Returns:
            True if lock acquired, False otherwise
        """
        import time

        start_time = time.time()

        while True:
            try:
                # 使用 SETNX 模式
                acquired = await self.redis.set(
                    self.lock_name,
                    "1",
                    nx=True,
                    ex=self.expire_seconds
                )

                if acquired:
                    self._locked = True
                    return True

                if not blocking:
                    return False

                if time.time() - start_time >= timeout:
                    return False

                await asyncio.sleep(0.1)

            except Exception as e:
                print(f"[DistributedLock] Error acquiring lock: {e}")
                return False

    async def release(self) -> bool:
        """释放锁"""
        if not self._locked:
            return True

        try:
            await self.redis.delete(self.lock_name)
            self._locked = False
            return True
        except Exception as e:
            print(f"[DistributedLock] Error releasing lock: {e}")
            return False

    async def extend(self, extra_seconds: int = None) -> bool:
        """延长锁的持有时间"""
        if not self._locked:
            return False

        try:
            expire = extra_seconds or self.expire_seconds
            await self.redis.expire(self.lock_name, expire)
            return True
        except Exception:
            return False

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.release()

    def __enter__(self):
        """同步上下文管理器入口（仅用于非异步上下文）"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """同步上下文管理器出口（警告：可能无法在事件循环关闭时执行）"""
        # 同步版本仅在已获取锁时记录警告
        if self._locked:
            # 尝试获取事件循环并调度释放
            try:
                loop = asyncio.get_running_loop()
                # 在事件循环运行时，使用 create_task
                loop.call_later(0.1, lambda: asyncio.create_task(self.release()))
            except RuntimeError:
                # 没有运行中的事件循环，锁可能会持有到进程结束
                import warnings
                warnings.warn(
                    "DistributedLock released synchronously but event loop not running. "
                    "Use 'async with' for proper cleanup.",
                    ResourceWarning
                )


# Redis 客户端管理
_redis_client = None


async def get_redis_client():
    """获取 Redis 客户端"""
    global _redis_client

    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            try:
                import redis.asyncio as redis
                _redis_client = redis.from_url(redis_url, decode_responses=True)
                # 测试连接
                await _redis_client.ping()
                print(f"[Redis] Connected to {redis_url}")
            except Exception as e:
                print(f"[Redis] Failed to connect: {e}")
                _redis_client = None
        else:
            print("[Redis] REDIS_URL not configured, using in-memory rate limiter")

    return _redis_client


async def close_redis_client():
    """关闭 Redis 客户端"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None


class TaskQueue:
    """
    任务队列管理器

    特性：
    1. 优先级队列（FIFO + 优先级）
    2. 平台级别的速率限制
    3. 并发控制
    4. 任务重试
    5. 后台执行
    """

    def __init__(
        self,
        max_concurrent: int = 5,
        max_queue_size: int = 1000
    ):
        self.max_concurrent = max_concurrent
        self.max_queue_size = max_queue_size

        self._queue: asyncio.PriorityQueue = None
        self._active_tasks: Dict[int, asyncio.Task] = {}
        self._rate_limiters: Dict[str, RateLimiter] = {}
        self._redis_rate_limiters: Dict[str, RedisRateLimiter] = {}
        self._redis_client = None
        self._use_redis = False
        self._running = False
        self._lock = asyncio.Lock()
        self._worker_task: Optional[asyncio.Task] = None

        # Agent 执行器映射
        self._executors: Dict[str, Callable] = {}

    def _init_queue(self):
        """初始化队列（延迟初始化）"""
        if self._queue is None:
            self._queue = asyncio.PriorityQueue(maxsize=self.max_queue_size)

    async def start(self):
        """启动任务队列"""
        if self._running:
            return

        self._init_queue()
        self._running = True

        # 尝试连接 Redis
        self._redis_client = await get_redis_client()
        self._use_redis = self._redis_client is not None

        if self._use_redis:
            # 使用 Redis 速率限制器
            print("[TaskQueue] Using Redis-backed rate limiters")
            for platform, limit in PLATFORM_RATE_LIMITS.items():
                self._redis_rate_limiters[platform] = RedisRateLimiter(
                    self._redis_client,
                    key_prefix=f"ratelimit:{platform}",
                    max_requests=limit
                )
        else:
            # 使用内存速率限制器（降级）
            print("[TaskQueue] Using in-memory rate limiters (Redis unavailable)")
            for platform, limit in PLATFORM_RATE_LIMITS.items():
                self._rate_limiters[platform] = RateLimiter(max_requests=limit)

        # 启动工作协程
        self._worker_task = asyncio.create_task(self._worker_loop())

        print(f"[TaskQueue] Started (max_concurrent={self.max_concurrent}, redis={self._use_redis})")

    async def stop(self):
        """停止任务队列"""
        self._running = False

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        # 等待活跃任务完成
        if self._active_tasks:
            print(f"[TaskQueue] Waiting for {len(self._active_tasks)} active tasks...")
            await asyncio.gather(*self._active_tasks.values(), return_exceptions=True)

        print("[TaskQueue] Stopped")

    def register_executor(self, agent_name: str, executor: Callable):
        """注册任务执行器"""
        self._executors[agent_name] = executor
        print(f"[TaskQueue] Registered executor for: {agent_name}")

    async def submit_task(
        self,
        task_id: int,
        user_id: int,
        agent_name: str,
        task_type: str,
        payload: Dict,
        priority: TaskPriority = TaskPriority.NORMAL,
        platform: str = None
    ) -> bool:
        """
        提交任务到队列

        Args:
            task_id: 数据库中的任务ID
            user_id: 用户ID
            agent_name: Agent 名称
            task_type: 任务类型
            payload: 任务参数
            priority: 优先级
            platform: 平台名称（用于速率限制）

        Returns:
            bool: 是否成功入队
        """
        if not self._running:
            await self.start()

        queued_task = QueuedTask(
            task_id=task_id,
            user_id=user_id,
            agent_name=agent_name,
            task_type=task_type,
            payload=payload,
            priority=priority,
            platform=platform or self._extract_platform(payload)
        )

        # 优先级 = (优先级数字, 时间戳) - 数字越小优先级越高
        priority_value = (priority.value, queued_task.created_at.timestamp())

        try:
            # 使用带超时的 put 避免任务丢失
            await asyncio.wait_for(
                self._queue.put((priority_value, queued_task)),
                timeout=5.0
            )
            print(f"[TaskQueue] Enqueued task {task_id} ({agent_name}/{task_type})")
            return True
        except asyncio.TimeoutError:
            print(f"[TaskQueue] Queue is full (timeout)! Task {task_id} rejected")
            await update_task_status(task_id, TaskStatus.FAILED, error="Queue timeout after 5s")
            return False
        except Exception as e:
            print(f"[TaskQueue] Failed to enqueue task {task_id}: {e}")
            await update_task_status(task_id, TaskStatus.FAILED, error=str(e))
            return False

    def _extract_platform(self, payload: Dict) -> Optional[str]:
        """从 payload 中提取平台信息"""
        platform = payload.get("platform", "")
        if platform:
            return platform.lower()
        return None

    async def _worker_loop(self):
        """工作协程 - 从队列取任务执行"""
        while self._running:
            try:
                # 等待获取任务（带超时）
                try:
                    priority, task = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # 检查并发限制
                if len(self._active_tasks) >= self.max_concurrent:
                    # 放回队列，等待有空位
                    await self._queue.put((priority, task))
                    await asyncio.sleep(0.1)
                    continue

                # 如果有平台限制，等待速率配额
                if task.platform:
                    # 优先使用 Redis 速率限制器
                    if self._use_redis and task.platform in self._redis_rate_limiters:
                        limiter = self._redis_rate_limiters[task.platform]
                        if not await limiter.acquire(task.platform):
                            wait_time = await limiter.wait_time(task.platform)
                            print(f"[TaskQueue] Rate limited for {task.platform} (Redis), waiting {wait_time:.1f}s")
                            # 重新放回队列（稍后重试）
                            await asyncio.sleep(min(wait_time, 5.0))
                            await self._queue.put((priority, task))
                            continue
                    elif task.platform in self._rate_limiters:
                        limiter = self._rate_limiters[task.platform]
                        if not await limiter.acquire():
                            wait_time = await limiter.wait_time()
                            print(f"[TaskQueue] Rate limited for {task.platform}, waiting {wait_time:.1f}s")
                            # 重新放回队列（稍后重试）
                            await asyncio.sleep(min(wait_time, 5.0))
                            await self._queue.put((priority, task))
                            continue

                # 创建任务执行协程
                active_task = asyncio.create_task(self._execute_task(task))
                self._active_tasks[task.task_id] = active_task

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[TaskQueue] Worker loop error: {e}")

    async def _execute_task(self, task: QueuedTask):
        """执行单个任务"""
        task.started_at = datetime.now()
        await update_task_status(task.task_id, TaskStatus.RUNNING)

        print(f"[TaskQueue] Executing task {task.task_id} ({task.agent_name})")

        try:
            executor = self._executors.get(task.agent_name)

            if not executor:
                # 动态导入 agent
                executor = await self._load_agent_executor(task.agent_name)

            if executor:
                # 执行任务
                result = await executor(task.payload)

                task.status = TaskStatus.COMPLETED
                task.result = result if isinstance(result, dict) else {"data": result}
                task.completed_at = datetime.now()

                await update_task_status(
                    task.task_id,
                    TaskStatus.COMPLETED,
                    result=task.result
                )

                print(f"[TaskQueue] Task {task.task_id} completed successfully")

            else:
                raise RuntimeError(f"No executor found for agent: {task.agent_name}")

        except Exception as e:
            error_str = traceback.format_exc()
            print(f"[TaskQueue] Task {task.task_id} failed: {e}")

            task.retry_count += 1

            if task.retry_count < task.max_retries:
                # 重试
                task.status = TaskStatus.PENDING
                priority = (task.priority.value, datetime.now().timestamp())
                await self._queue.put((priority, task))
                print(f"[TaskQueue] Task {task.task_id} scheduled for retry ({task.retry_count}/{task.max_retries})")
            else:
                # 最终失败
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.completed_at = datetime.now()

                await update_task_status(
                    task.task_id,
                    TaskStatus.FAILED,
                    error=task.error
                )

                print(f"[TaskQueue] Task {task.task_id} failed permanently after {task.retry_count} retries")

        finally:
            # 清理活跃任务
            if task.task_id in self._active_tasks:
                del self._active_tasks[task.task_id]

    async def _load_agent_executor(self, agent_name: str) -> Optional[Callable]:
        """动态加载 Agent 执行器"""
        try:
            agent_map = {
                "LeadAgent": "agents.lead_agent.lead_agent",
                "LinkedInAgent": "agents.linkedin_agent.linkedin_agent",
                "FacebookAgent": "agents.facebook_agent.facebook_agent",
                "TwitterAgent": "agents.twitter_agent.twitter_agent",
                "EmailAgent": "agents.email_agent.email_agent",
                "CommentAgent": "agents.comment_agent.comment_agent",
                "MarketingAgent": "agents.marketing_agent.marketing_agent",
                "ReportAgent": "agents.report_agent.report_agent",
            }

            if agent_name not in agent_map:
                return None

            module_path = agent_map[agent_name]
            from importlib import import_module

            # 简化处理：直接返回 None 让系统知道没有这个 agent
            # 实际实现时需要完善各个 agent
            return None

        except Exception as e:
            print(f"[TaskQueue] Failed to load executor for {agent_name}: {e}")
            return None

    async def get_status(self) -> Dict:
        """获取队列状态"""
        status = {
            "running": self._running,
            "queue_size": self._queue.qsize() if self._queue else 0,
            "active_tasks": len(self._active_tasks),
            "max_concurrent": self.max_concurrent,
            "use_redis": self._use_redis,
        }

        # 添加速率限制器信息
        if self._use_redis:
            # Redis-backed rate limiters
            redis_status = {}
            for platform, limiter in self._redis_rate_limiters.items():
                usage = await limiter.get_usage(platform)
                redis_status[platform] = {
                    "limit": limiter.max_requests,
                    "window_seconds": limiter.window_seconds,
                    "current_usage": usage
                }
            status["rate_limiters"] = redis_status
        else:
            # In-memory rate limiters
            status["rate_limiters"] = {
                platform: {
                    "limit": limiter.max_requests,
                    "window_seconds": limiter.window_seconds,
                    "current_usage": len(limiter.requests)
                }
                for platform, limiter in self._rate_limiters.items()
            }

        return status

    async def cancel_task(self, task_id: int) -> bool:
        """取消任务"""
        if task_id in self._active_tasks:
            self._active_tasks[task_id].cancel()
            await update_task_status(task_id, TaskStatus.CANCELLED)
            return True
        return False


# 全局任务队列实例
_global_queue: Optional[TaskQueue] = None


def get_task_queue() -> TaskQueue:
    """获取全局任务队列实例"""
    global _global_queue
    if _global_queue is None:
        max_concurrent = int(os.getenv("MAX_CONCURRENT_TASKS", "5"))
        _global_queue = TaskQueue(max_concurrent=max_concurrent)
    return _global_queue


async def init_task_queue():
    """初始化全局任务队列"""
    queue = get_task_queue()
    await queue.start()
    return queue


async def shutdown_task_queue():
    """关闭全局任务队列"""
    global _global_queue
    if _global_queue:
        await _global_queue.stop()
        _global_queue = None
