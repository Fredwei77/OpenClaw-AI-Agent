"""
Monitoring and Metrics Module
提供 Prometheus 格式的监控指标

指标：
- tasks_total: 总任务数
- tasks_active: 活跃任务数
- tasks_completed: 已完成任务数
- tasks_failed: 失败任务数
- rate_limit_hits_total: 速率限制命中次数
- scrape_requests_total: 爬取请求数（按平台）
- scrape_duration_seconds: 爬取耗时分布
- browser_pool_browsers: 浏览器池中的浏览器数
- browser_pool_contexts: 浏览器池中的上下文数
"""

import time
import os
from typing import Dict, Optional
from functools import wraps
from datetime import datetime

try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


# ========================
# Metric Definitions
# ========================

if PROMETHEUS_AVAILABLE:
    # Task metrics
    TASKS_TOTAL = Counter(
        "openclaw_tasks_total",
        "Total number of tasks processed",
        ["agent_name", "task_type", "status"]
    )

    TASKS_ACTIVE = Gauge(
        "openclaw_tasks_active",
        "Number of currently running tasks"
    )

    TASKS_DURATION_SECONDS = Histogram(
        "openclaw_tasks_duration_seconds",
        "Task execution duration in seconds",
        ["agent_name", "task_type"],
        buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0]
    )

    # Rate limiting metrics
    RATE_LIMIT_HITS = Counter(
        "openclaw_rate_limit_hits_total",
        "Total number of rate limit occurrences",
        ["platform"]
    )

    # Scrape metrics
    SCRAPE_REQUESTS = Counter(
        "openclaw_scrape_requests_total",
        "Total number of scrape requests",
        ["platform", "status"]
    )

    SCRAPE_DURATION = Histogram(
        "openclaw_scrape_duration_seconds",
        "Scrape request duration in seconds",
        ["platform"],
        buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
    )

    # Browser pool metrics
    BROWSER_POOL_BROWSERS = Gauge(
        "openclaw_browser_pool_browsers",
        "Number of browsers in the pool"
    )

    BROWSER_POOL_CONTEXTS = Gauge(
        "openclaw_browser_pool_contexts",
        "Number of browser contexts in the pool"
    )

    # Lead collection metrics
    LEADS_COLLECTED = Counter(
        "openclaw_leads_collected_total",
        "Total number of leads collected",
        ["platform", "source"]
    )

    # API metrics
    API_REQUESTS = Counter(
        "openclaw_api_requests_total",
        "Total number of API requests",
        ["endpoint", "method", "status"]
    )

    API_DURATION = Histogram(
        "openclaw_api_duration_seconds",
        "API request duration in seconds",
        ["endpoint", "method"],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
    )


# ========================
# Metric Helper Functions
# ========================

def track_task(agent_name: str, task_type: str):
    """装饰器：跟踪任务执行"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            TASKS_ACTIVE.inc()

            start_time = time.time()
            status = "success"

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                TASKS_ACTIVE.dec()
                TASKS_TOTAL.labels(agent_name=agent_name, task_type=task_type, status=status).inc()
                TASKS_DURATION_SECONDS.labels(agent_name=agent_name, task_type=task_type).observe(duration)

        return wrapper
    return decorator


def track_scrape(platform: str):
    """装饰器：跟踪爬取请求"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                SCRAPE_REQUESTS.labels(platform=platform, status=status).inc()
                SCRAPE_DURATION.labels(platform=platform).observe(duration)

        return wrapper
    return decorator


class MetricsCollector:
    """指标收集器"""

    def __init__(self):
        self._custom_metrics: Dict = {}
        self._start_time = time.time()

    def record_task(self, agent_name: str, task_type: str, status: str, duration: float):
        """记录任务指标"""
        if PROMETHEUS_AVAILABLE:
            TASKS_TOTAL.labels(agent_name=agent_name, task_type=task_type, status=status).inc()
            TASKS_DURATION_SECONDS.labels(agent_name=agent_name, task_type=task_type).observe(duration)

    def record_rate_limit(self, platform: str):
        """记录速率限制"""
        if PROMETHEUS_AVAILABLE:
            RATE_LIMIT_HITS.labels(platform=platform).inc()

    def record_scrape(self, platform: str, status: str, duration: float):
        """记录爬取请求"""
        if PROMETHEUS_AVAILABLE:
            SCRAPE_REQUESTS.labels(platform=platform, status=status).inc()
            SCRAPE_DURATION.labels(platform=platform).observe(duration)

    def record_leads(self, platform: str, source: str, count: int):
        """记录收集的线索"""
        if PROMETHEUS_AVAILABLE:
            LEADS_COLLECTED.labels(platform=platform, source=source).inc(count)

    def update_browser_pool(self, browsers: int, contexts: int):
        """更新浏览器池指标"""
        if PROMETHEUS_AVAILABLE:
            BROWSER_POOL_BROWSERS.set(browsers)
            BROWSER_POOL_CONTEXTS.set(contexts)

    def record_api_request(self, endpoint: str, method: str, status: int, duration: float):
        """记录 API 请求"""
        if PROMETHEUS_AVAILABLE:
            status_str = str(status)
            API_REQUESTS.labels(endpoint=endpoint, method=method, status=status_str).inc()
            API_DURATION.labels(endpoint=endpoint, method=method).observe(duration)

    def get_metrics(self) -> bytes:
        """获取 Prometheus 格式的指标"""
        if not PROMETHEUS_AVAILABLE:
            return b"# Prometheus metrics unavailable (prometheus_client not installed)"

        return generate_latest()

    def get_content_type(self) -> str:
        """获取 Prometheus 内容类型"""
        return CONTENT_TYPE_LATEST

    def get_stats(self) -> Dict:
        """获取基本统计信息"""
        return {
            "uptime_seconds": time.time() - self._start_time,
            "prometheus_available": PROMETHEUS_AVAILABLE,
            "timestamp": datetime.now().isoformat()
        }


# 全局指标收集器实例
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标收集器"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


# ========================
# FastAPI Middleware (Optional - uncomment to enable)
# ========================

# To use API metrics middleware, add this to main.py:
# from starlette.middleware.base import BaseHTTPMiddleware
# app.add_middleware(BaseHTTPMiddleware, dispatch=metrics_middleware)


# ========================
# Health Check
# ========================

def get_health_status() -> Dict:
    """获取健康状态"""
    collector = get_metrics_collector()
    stats = collector.get_stats()

    return {
        "status": "healthy",
        "timestamp": stats["timestamp"],
        "uptime_seconds": stats["uptime_seconds"],
        "prometheus_available": stats["prometheus_available"],
    }
