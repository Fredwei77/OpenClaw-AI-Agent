# API Documentation Generator

## Use Scene
当需要创建新 API 端点或更新现有 API 文档时使用此子代理。

## 职责

### 1. Docstring 验证
```python
@router.post("/", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    lead: LeadCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    创建新的线索记录。

    - **platform**: 来源平台 (linkedin, twitter, x, facebook)
    - **username**: 在平台上的用户名
    - **profile_url**: 个人主页 URL
    - **email**: 邮箱地址（可选）
    - **followers**: 粉丝/关注者数量（可选）
    - **tags**: 标签数组，用于分类

    返回创建的线索信息，包含自动生成的 ID 和时间戳。
    """
```

### 2. Pydantic 模型文档
```python
class LeadCreate(BaseModel):
    """线索创建请求模型"""
    platform: Literal["linkedin", "twitter", "x", "facebook", "instagram"] = Field(
        ...,
        description="社交媒体平台名称"
    )
    username: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="平台上的用户名"
    )
    profile_url: HttpUrl = Field(
        ...,
        description="个人主页完整 URL"
    )
    email: Optional[EmailStr] = Field(
        None,
        description="联系邮箱"
    )
    followers: int = Field(
        default=0,
        ge=0,
        description="粉丝数量"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="线索标签"
    )

    class Config:
        from_attributes = True
```

### 3. OpenAPI 模式验证
```python
# 确保所有路由都有：
# 1. HTTP 方法装饰器 (@router.get, @router.post 等)
# 2. response_model 指定响应模型
# 3. status_code 指定状态码
# 4. docstring 文档字符串

# 检查清单
- [ ] 所有端点有 docstring
- [ ] 所有请求模型有 Field 描述
- [ ] 所有响应模型有 Config.from_attributes
- [ ] HTTP 状态码明确指定
- [ ] 参数有 Path/Query/Body 装饰器
```

### 4. 路径命名规范
```
✅ 正确
GET    /api/leads              # 获取列表
GET    /api/leads/{id}          # 获取单个
POST   /api/leads               # 创建
PATCH  /api/leads/{id}          # 更新部分
PUT    /api/leads/{id}          # 更新全部
DELETE /api/leads/{id}          # 删除

❌ 错误
GET    /api/getLeads
GET    /api/fetch_all_leads
POST   /api/createLead
```

## 输出格式
```
## API Documentation

### /api/leads

#### GET /api/leads/
**描述**: 获取线索列表（支持分页和过滤）

**认证**: Bearer Token

**查询参数**:
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页数量，默认 20 |
| platform | string | 否 | 按平台过滤 |
| status | string | 否 | 按状态过滤 |

**响应**: 200 OK
```json
{
  "leads": [...],
  "total": 150,
  "page": 1,
  "page_size": 20
}
```

**错误响应**:
- 401 Unauthorized: 未提供或无效 token
- 500 Internal Server Error: 服务器错误
```
