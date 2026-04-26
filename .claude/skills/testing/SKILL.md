# Testing Standards

## Use Scene
当为后端 API 或 agents 编写测试时调用此技能。

## 测试结构
```python
# tests/test_leads.py
import pytest
from httpx import AsyncClient
from main import app

@pytest.mark.asyncio
async def test_create_lead():
    """测试创建线索 API"""
    async with AsyncClient(app, base_url="http://test") as client:
        response = await client.post(
            "/api/leads/",
            json={
                "platform": "linkedin",
                "username": "John Doe",
                "profile_url": "https://linkedin.com/in/johndoe"
            },
            headers={"Authorization": f"Bearer {test_token}"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["platform"] == "linkedin"
        assert "id" in data

@pytest.mark.asyncio
async def test_get_leads_with_auth():
    """测试获取线索列表（需要认证）"""
    async with AsyncClient(app, base_url="http://test") as client:
        response = await client.get(
            "/api/leads/",
            headers={"Authorization": f"Bearer {test_token}"}
        )
        assert response.status_code == 200
        assert "leads" in response.json()
```

## Fixture 配置
```python
# tests/conftest.py
import pytest
from httpx import AsyncClient
from main import app

@pytest.fixture
def auth_headers():
    """生成测试用 JWT token"""
    from auth import create_access_token
    token = create_access_token(data={"sub": "1", "email": "test@example.com"})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
async def client():
    """HTTP 测试客户端"""
    async with AsyncClient(app, base_url="http://test") as c:
        yield c

@pytest.fixture
async def db_pool():
    """测试数据库连接池"""
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5)
    yield pool
    await pool.close()
```

## Mock 外部依赖
```python
# ✅ 正确：Mock 外部 API
import pytest
from unittest.mock import patch

@pytest.mark.asyncio
async def test_scrape_with_mock():
    with patch("agents.lead_agent.LeadAgent.run") as mock_run:
        mock_run.return_value = [
            {"platform": "twitter", "username": "test_user"}
        ]
        result = await agent.run({"keyword": "test"})
        assert len(result) == 1

# ❌ 错误：Mock 内部实现
@pytest.fixture
def mock_save_leads(mocker):
    return mocker.patch("db.save_leads", return_value=0)
```

## 覆盖率要求
| 模块 | 目标覆盖率 |
|------|----------|
| API 路由 | 90%+ |
| 核心业务逻辑 | 80%+ |
| Agent run() 方法 | 70%+ |
| 数据库操作 | 75%+ |

## 运行测试
```bash
# 运行所有测试
pytest backend/tests/ -v

# 运行带覆盖率
pytest backend/tests/ --cov=api --cov-report=html

# 运行特定测试
pytest backend/tests/test_leads.py::test_create_lead -v

# 运行忽略某个目录
pytest backend/tests/ --ignore=backend/tests/integration/
```

## API 测试模式
```python
# 1. 测试成功响应
assert response.status_code == 200
assert "data" in response.json()

# 2. 测试认证错误
assert response.status_code == 401

# 3. 测试验证错误
assert response.status_code == 422
errors = response.json()
assert "detail" in errors

# 4. 测试 404
assert response.status_code == 404

# 5. 测试分页
assert "pagination" in response.json()
assert response.json()["pagination"]["page"] == 1
```

## Agent 测试
```python
@pytest.mark.asyncio
async def test_linkedin_agent():
    """测试 LinkedIn Agent"""
    agent = LinkedInAgent(browser_manager=mock_browser_manager)

    # Mock 浏览器上下文
    with mock_browser_manager.get_or_create_context() as mock_context:
        mock_page = AsyncMock()
        mock_context.new_page.return_value = mock_page
        mock_page.query_selector_all.return_value = []

        results = await agent.run({
            "keyword": "fitness equipment",
            "limit": 5
        })

        assert isinstance(results, list)
        assert len(results) <= 5
```

## 集成测试
```python
@pytest.mark.asyncio
async def test_full_workflow():
    """端到端测试：创建任务 -> 执行 -> 获取结果"""
    # 1. 创建任务
    create_response = await client.post("/api/tasks/", json={...})
    task_id = create_response.json()["id"]

    # 2. 等待任务执行
    import asyncio
    for _ in range(30):  # 最多等待 30 秒
        await asyncio.sleep(1)
        status_response = await client.get(f"/api/tasks/{task_id}")
        status = status_response.json()["status"]
        if status in ("completed", "failed"):
            break

    # 3. 验证结果
    final_response = await client.get(f"/api/tasks/{task_id}")
    assert final_response.json()["status"] == "completed"
```
