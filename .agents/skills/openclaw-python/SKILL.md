# OpenClaw Python 代码规范

## 使用场景
当您需要审查、编写或修改 Python 代码时自动调用此技能。

## 代码规范

### 1. 异步代码
```python
# ✅ 正确：使用 asyncpg 而非普通 psycopg2
async def get_data():
    conn = await asyncpg.connect(database_url)
    ...

# ❌ 错误：使用同步驱动
conn = psycopg2.connect(database_url)
```

### 2. 类型提示
```python
# ✅ 正确：完整类型提示
async def save_leads(leads: List[Dict], user_id: Optional[int] = None) -> int:
    ...

# ❌ 错误：省略类型
async def save_leads(leads, user_id=None):
    ...
```

### 3. 错误处理
```python
# ✅ 正确：使用 try/except/finally
try:
    result = await db.execute(query)
except Exception as e:
    logger.error(f"Database error: {e}")
    raise
finally:
    await conn.close()

# ❌ 错误：捕获所有异常但不做处理
try:
    ...
except:
    pass
```

### 4. 日志记录
```python
# ✅ 正确：使用结构化日志
logger.info(f"[Agent] Task {task_id} completed", extra={"task_id": task_id, "duration": elapsed})

# ❌ 错误：使用 print 而非日志
print(f"Task {task_id} done")
```

### 5. FastAPI 路由
```python
# ✅ 正确：使用依赖注入获取当前用户
@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    current_user: UserResponse = Depends(get_current_user)
):
    # 验证用户权限
    if row['user_id'] and row['user_id'] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return ...

# ❌ 错误：直接在路由中查询数据库
@router.get("/{task_id}")
async def get_task(task_id: int):
    row = await conn.fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)
    return row
```

### 6. Pydantic 模型
```python
# ✅ 正确：使用 Field 进行验证
class TaskCreate(BaseModel):
    agent_name: str = Field(..., min_length=1, max_length=255)
    task_type: Literal["scrape", "comment", "like", "follow", "message", "analytics"]
    payload: dict = Field(default_factory=dict)
    priority: int = Field(default=1, ge=0, le=3)

# ❌ 错误：缺少验证
class TaskCreate(BaseModel):
    agent_name: str
    task_type: str
    payload: dict = {}
```

### 7. JWT 安全
```python
# ✅ 正确：验证 token 且优雅降级
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    warnings.warn("JWT_SECRET_KEY not set! Using random key for dev only.")
    SECRET_KEY = secrets.token_urlsafe(32)

# ❌ 错误：直接 raise 导致服务无法启动
if not SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY must be set")
```

## FastAPI 最佳实践

1. **路由组织**：按功能模块分离 (auth, leads, tasks, agents, analytics)
2. **错误处理**：使用 HTTPException 而非通用异常
3. **响应格式**：通过中间件统一响应格式
4. **依赖注入**：使用 Depends() 获取认证、数据库连接
5. **后台任务**：使用 BackgroundTasks 而非自定义线程

## Playwright 浏览器自动化

1. **上下文隔离**：每个账户使用独立的 BrowserContext
2. **代理轮换**：使用代理池避免被封禁
3. **速率限制**：遵守平台限制 (LinkedIn 20/小时, Facebook 15/小时)
4. **Stealth 模式**：使用 playwright_stealth 避免被检测
5. **资源清理**：使用 try/finally 确保浏览器正确关闭

## 数据库操作

1. **连接池**：使用 asyncpg.create_pool 而非每次新建连接
2. **事务**：使用 async with transaction() 确保原子性
3. **UPSERT**：使用 INSERT ... ON CONFLICT DO UPDATE 去重
4. **索引**：为高频查询字段创建索引

## 环境变量

敏感信息必须通过环境变量获取：
- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `OPENROUTER_API_KEY`
- `.env` 文件必须添加到 `.gitignore`
