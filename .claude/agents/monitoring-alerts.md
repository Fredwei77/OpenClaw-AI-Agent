# Monitoring & Alerting Assistant

## Use Scene
当需要设置生产环境监控和告警时使用此子代理。

## 职责

### 1. 关键指标追踪
| 指标 | 目标值 | 告警阈值 |
|------|--------|---------|
| API 响应时间 p95 | < 200ms | > 500ms |
| 数据库查询时间 p95 | < 50ms | > 200ms |
| 任务队列深度 | < 50 | > 100 |
| 浏览器池利用率 | < 80% | > 95% |
| API 错误率 | < 0.1% | > 1% |
| CPU 使用率 | < 70% | > 90% |
| 内存使用率 | < 80% | > 95% |

### 2. 结构化日志
```python
import structlog
import logging

# 配置 structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# 使用
logger = structlog.get_logger()
logger.info(
    "api_request_completed",
    method="POST",
    path="/api/leads/",
    status_code=201,
    duration_ms=45.2,
    user_id=123
)
```

### 3. 健康检查模式
```python
from dataclasses import dataclass
from typing import Dict

@dataclass
class HealthStatus:
    status: str  # "healthy" | "degraded" | "unhealthy"
    version: str
    checks: Dict[str, str]  # component -> status

@app.get("/health")
async def health_check() -> HealthStatus:
    checks = {}

    # 数据库检查
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "failed"

    # 浏览器池检查
    try:
        pool_status = await browser_pool.get_pool_status()
        checks["browser_pool"] = "ok" if pool_status["total_browsers"] > 0 else "degraded"
    except Exception:
        checks["browser_pool"] = "failed"

    # 任务队列检查
    try:
        queue_status = await task_queue.get_status()
        checks["task_queue"] = "ok" if queue_status["running"] else "failed"
    except Exception:
        checks["task_queue"] = "failed"

    # 综合状态
    failed_checks = [k for k, v in checks.items() if v != "ok"]
    overall = "healthy" if not failed_checks else "degraded"

    return HealthStatus(
        status=overall,
        version="1.0.0",
        checks=checks
    )
```

### 4. Sentry 集成
```python
import sentry_sdk
from fastapi import FastAPI

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    environment=os.getenv("ENVIRONMENT"),
    traces_sample_rate=0.1,  # 10% 的事务发送到 Sentry
    before_send_transaction=lambda event: {
        **event,
        "user": {"id": get_current_user_id()}  # 脱敏用户信息
    }
)

app = FastAPI()
```

### 5. Grafana Dashboard JSON
```json
{
  "dashboard": {
    "title": "OpenClaw AI Agent",
    "panels": [
      {
        "title": "API Response Time (p95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))"
          }
        ]
      },
      {
        "title": "Task Queue Depth",
        "targets": [
          {
            "expr": "openclaw_task_queue_size"
          }
        ]
      },
      {
        "title": "Browser Pool Utilization",
        "targets": [
          {
            "expr": "openclaw_browser_pool_active_contexts / openclaw_browser_pool_max"
          }
        ]
      }
    ]
  }
}
```

### 6. 告警规则
```yaml
# Prometheus alerting rules
groups:
  - name: openclaw
    rules:
      - alert: HighAPIErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.01
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High API error rate"

      - alert: TaskQueueBacklog
        expr: openclaw_task_queue_size > 100
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Task queue backlog growing"

      - alert: BrowserPoolExhausted
        expr: openclaw_browser_pool_active_contexts >= openclaw_browser_pool_max
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Browser pool exhausted"
```

## 监控清单
- [ ] `/health` 端点返回完整状态
- [ ] 结构化日志配置正确
- [ ] Sentry/Datadog 集成
- [ ] Grafana Dashboard 创建
- [ ] 告警阈值配置
- [ ] 日志聚合配置（ Loki/ELK）
