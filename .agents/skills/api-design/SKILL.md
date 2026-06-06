# API 设计与开发规范

## 使用场景
当您需要设计新的 API 端点、审查 REST API 代码时使用此技能。

## RESTful 规范

### 1. URL 命名
```
✅ 正确：/api/leads, /api/tasks/{id}, /api/analytics/
❌ 错误：/getLeads, /fetch_all_tasks, /api/lead
```

### 2. HTTP 方法
| 方法 | 用途 | 示例 |
|------|------|------|
| GET | 获取资源 | `GET /api/leads` |
| POST | 创建资源 | `POST /api/tasks` |
| PATCH | 更新部分资源 | `PATCH /api/tasks/{id}` |
| PUT | 替换资源 | `PUT /api/users/{id}` |
| DELETE | 删除资源 | `DELETE /api/leads/{id}` |

### 3. 响应格式
```python
# ✅ 正确：统一响应格式
{
    "success": True,
    "data": {...},
    "message": "Operation successful"
}

# ❌ 错误：不一致的响应
{"result": [...]}
{"status": "ok", "items": [...]}
```

### 4. 错误响应
```python
# ✅ 正确：标准的 HTTP 异常
raise HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="Invalid task status"
)

# ✅ 正确：自定义错误格式
{
    "success": False,
    "error": {
        "code": "TASK_NOT_FOUND",
        "message": "Task with id 123 not found"
    }
}
```

### 5. 分页
```python
# ✅ 正确：标准分页响应
{
    "success": True,
    "data": [...],
    "pagination": {
        "page": 1,
        "page_size": 20,
        "total": 150,
        "total_pages": 8
    }
}
```

### 6. 过滤与排序
```
GET /api/leads?status=new&platform=linkedin&sort=created_at&order=desc
GET /api/tasks?agent_name=LeadAgent&status=pending
```

## Pydantic 模型

```python
# ✅ 正确：使用 Field 验证
class LeadCreate(BaseModel):
    platform: Literal["linkedin", "twitter", "facebook"]
    username: str = Field(..., min_length=1, max_length=255)
    profile_url: HttpUrl
    email: Optional[EmailStr] = None
    followers: int = Field(default=0, ge=0)
    tags: List[str] = Field(default_factory=list)

# ❌ 错误：缺少验证
class LeadCreate(BaseModel):
    platform: str
    username: str
    profile_url: str
```

## 中间件

```python
# ✅ 正确：分层中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)

# 响应格式中间件
app.add_middleware(GlobalResponseMiddleware)

# 异常处理
app.add_exception_handler(HTTPException, http_exception_handler)
```

## API 文档

```python
@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task: TaskCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    创建新任务并提交到队列执行。

    - **agent_name**: Agent 名称 (LeadAgent, LinkedInAgent, etc.)
    - **task_type**: 任务类型 (scrape, message, analytics)
    - **payload**: 任务参数 JSON
    - **priority**: 优先级 (0-3)

    返回创建的任务信息，包含状态为 'pending'。
    """
```

## 版本控制

```
/api/v1/leads    # 当前版本
/api/v2/leads    # 未来版本
```

## 速率限制

```python
# 在响应头中添加速率限制信息
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640000000
```
