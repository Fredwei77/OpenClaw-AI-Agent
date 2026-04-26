# 测试编写子代理

## 使用场景
为代码生成测试用例、确保测试覆盖率时使用此子代理。

## 测试策略

### 1. 测试金字塔
```
         ┌───────────┐
         │   E2E    │  ← 少量，端到端
        ┌┴─────────┴┐
        │ Integration│  ← 中等，API 测试
       ┌┴───────────┴┐
       │    Unit     │  ← 大量，函数/方法测试
      ┌┴─────────────┴┐
```

### 2. Backend API 测试
```python
# tests/test_leads.py
import pytest
from httpx import AsyncClient
from main import app

@pytest.mark.asyncio
async def test_create_lead():
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

@pytest.mark.asyncio
async def test_lead_not_found():
    async with AsyncClient(app, base_url="http://test") as client:
        response = await client.get("/api/leads/99999")
        assert response.status_code == 404
```

### 3. 数据库测试
```python
# tests/test_db.py
import pytest
from db import save_leads, get_db_pool

@pytest.mark.asyncio
async def test_save_leads_upsert():
    leads = [
        {"platform": "twitter", "username": "test_user", "profile_url": "https://x.com/test"},
    ]
    count = await save_leads(leads, user_id=1)
    assert count == 1

    # 重复插入应该更新而不是报错
    count = await save_leads(leads, user_id=1)
    assert count == 0  # 没有新插入
```

### 4. Agent 测试
```python
# tests/test_agents.py
import pytest
from agents.linkedin_agent import LinkedInAgent

@pytest.mark.asyncio
async def test_linkedin_search():
    agent = LinkedInAgent()
    results = await agent.run({
        "keyword": "fitness equipment",
        "limit": 5
    })
    assert isinstance(results, list)
    assert len(results) <= 5
```

### 5. 覆盖率要求
- 核心业务逻辑：80%+
- API 路由：90%+
- Agent run() 方法：70%+

## Mock 使用

```python
# ✅ 正确：Mock 外部 API 调用
@pytest.fixture
def mock_openai(mocker):
    return mocker.patch("openai.AsyncOpenAI.chat.completions.create")

# ❌ 错误：Mock 内部实现
@pytest.fixture
def mock_save_leads(mocker):
    return mocker.patch("db.save_leads", return_value=0)
```

## 夹具 (Fixtures)

```python
# conftest.py
import pytest
from httpx import AsyncClient
from main import app

@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {test_jwt_token}"}

@pytest.fixture
async def client():
    async with AsyncClient(app, base_url="http://test") as c:
        yield c
```
