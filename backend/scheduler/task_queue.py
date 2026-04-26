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

        # 初始化平台速率限制器
        for platform, limit in PLATFORM_RATE_LIMITS.items():
            self._rate_limiters[platform] = RateLimiter(max_requests=limit)

        # 启动工作协程
        self._worker_task = asyncio.create_task(self._worker_loop())

        print(f"[TaskQueue] Started (max_concurrent={self.max_concurrent})")

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
            self._queue.put_nowait((priority_value, queued_task))
            print(f"[TaskQueue] Enqueued task {task_id} ({agent_name}/{task_type})")
            return True
        except asyncio.QueueFull:
            print(f"[TaskQueue] Queue is full! Task {task_id} rejected")
            await update_task_status(task_id, TaskStatus.FAILED, error="Queue overflow")
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
                if task.platform and task.platform in self._rate_limiters:
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
        return {
            "running": self._running,
            "queue_size": self._queue.qsize() if self._queue else 0,
            "active_tasks": len(self._active_tasks),
            "max_concurrent": self.max_concurrent,
            "rate_limiters": {
                platform: {
                    "limit": limiter.max_requests,
                    "window_seconds": limiter.window_seconds,
                    "current_usage": len(limiter.requests)
                }
                for platform, limiter in self._rate_limiters.items()
            }
        }

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
