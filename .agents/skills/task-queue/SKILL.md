# Task Queue & Background Processing

## Use Scene
当实现新 agent 或调试任务执行时调用此技能。

## 提交任务
```python
from scheduler.task_queue import get_task_queue, TaskPriority

# 在 API 路由中
@router.post("/", response_model=TaskResponse)
async def create_task(
    task: TaskCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    # 先创建数据库记录
    db_task = await create_task_in_db(task)

    # 提交到队列
    queue = get_task_queue()
    await queue.submit_task(
        task_id=db_task.id,
        user_id=current_user.id,
        agent_name=task.agent_name,
        task_type=task.task_type,
        payload=task.payload,
        priority=TaskPriority.HIGH,
        platform=task.payload.get("platform")  # 用于速率限制
    )

    return db_task
```

## 优先级级别
```python
class TaskPriority(int, Enum):
    LOW = 0      # 批量任务、低优先级
    NORMAL = 1   # 默认
    HIGH = 2     # 用户主动触发的任务
    URGENT = 3   # 时间敏感、关键任务
```

## 执行器注册
```python
# 在 task_queue.py 中注册
async def linkedin_agent_executor(payload: dict) -> List[Dict]:
    from agents.linkedin_agent import LinkedInAgent
    agent = LinkedInAgent()
    return await agent.run(payload)

queue = get_task_queue()
queue.register_executor("LinkedInAgent", linkedin_agent_executor)
```

## 任务状态流转
```
pending → running → completed
                   ↓
                 failed → (可重试)
                   ↓
               cancelled
```

## 任务结果存储
```python
# 在 agent 执行完成后
await update_task_status(
    task_id=task_id,
    status="completed",
    result={"leads_found": len(leads), "data": leads}
)

# 失败时
await update_task_status(
    task_id=task_id,
    status="failed",
    error="Rate limit exceeded"
)
```

## 速率限制配置
```python
PLATFORM_RATE_LIMITS = {
    "linkedin": 20,      # 每小时
    "facebook": 15,
    "twitter": 30,
    "x": 30,
    "instagram": 20,
    "tiktok": 15,
    "default": 50
}
```

## 并发控制
```python
# 配置最大并发任务数
max_concurrent = int(os.getenv("MAX_CONCURRENT_TASKS", "5"))

# 超过并发限制时，任务会在队列中等待
# 不建议设置过高（< 10），会导致系统资源竞争
```

## 监控任务队列
```python
# 获取队列状态
status = await queue.get_status()
# {
#     "running": True,
#     "queue_size": 12,
#     "active_tasks": 3,
#     "max_concurrent": 5,
#     "rate_limiters": {...}
# }
```

## 常见问题

### Q: 任务卡在 running 状态
A: 检查 agent 执行器是否有未捕获的异常，使用 `try/except` 包装

### Q: 速率限制总是触发
A: 调整 `PLATFORM_RATE_LIMITS`，或增加时间窗口

### Q: 任务重复执行
A: 确保 `submit_task` 使用相同的 `task_id`，队列会忽略重复
