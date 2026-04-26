# 性能分析子代理

## 使用场景
分析代码性能瓶颈、检查 N+1 查询、内存泄漏等问题时使用此子代理。

## 性能问题清单

### Backend (Python)

#### 1. 数据库查询
```python
# ❌ N+1 查询
for lead in leads:
    user = await conn.fetchrow("SELECT * FROM users WHERE id = $1", lead.user_id)
    # 每个 lead 都执行一次查询

# ✅ 正确：批量查询
user_ids = [lead.user_id for lead in leads]
users = await conn.fetch("SELECT * FROM users WHERE id = ANY($1)", user_ids)
```

#### 2. 连接池配置
```python
# ❌ 错误：每次请求创建新连接
conn = await asyncpg.connect(database_url)

# ✅ 正确：使用连接池
pool = await asyncpg.create_pool(database_url, min_size=5, max_size=20)
async with pool.acquire() as conn:
    # ...
```

#### 3. 异步 vs 同步
```python
# ❌ 错误：在 async 函数中使用同步代码
def process_data(data):
    time.sleep(10)  # 阻塞！

# ✅ 正确：使用异步版本
async def process_data(data):
    await asyncio.sleep(10)  # 非阻塞
```

#### 4. 大数据处理
```python
# ❌ 错误：一次性加载所有数据
all_leads = await conn.fetch("SELECT * FROM leads")  # 可能数千条

# ✅ 正确：分页查询
async def get_leads_paginated(page, page_size):
    offset = (page - 1) * page_size
    return await conn.fetch(
        "SELECT * FROM leads ORDER BY created_at LIMIT $1 OFFSET $2",
        page_size, offset
    )
```

### Frontend (React)

#### 1. 不必要的重新渲染
```jsx
# ❌ 错误：每次渲染创建新函数
<button onClick={() => handleClick(id)}>

# ✅ 正确：使用 useCallback
const handleClick = useCallback((id) => {
    // ...
}, []);
```

#### 2. 大列表渲染
```jsx
# ❌ 错误：直接渲染所有数据
{leads.map(lead => <LeadCard key={lead.id} lead={lead} />)}

# ✅ 正确：虚拟列表
import { FixedSizeList } from 'react-window';
<FixedSizeList
    height={400}
    itemCount={leads.length}
    itemSize={80}
>
    ({ index, style }) => <LeadCard style={style} lead={leads[index]} />
</FixedSizeList>
```

#### 3. 依赖过多的 useEffect
```jsx
# ❌ 错误
useEffect(() => {
    fetchData();
    processData();
    updateUI();
}, [data, trigger, config]);

# ✅ 正确：拆分成多个 useEffect
useEffect(() => { fetchData(); }, []);
useEffect(() => { processData(); }, [processedData]);
```

## 性能指标

| 指标 | 目标值 |
|------|--------|
| API 响应时间 | < 200ms (p95) |
| 数据库查询 | < 50ms (p95) |
| 前端 FCP | < 1.5s |
| 前端 TTI | < 3s |
| 并发连接数 | < 连接池上限的 80% |

## 分析工具

```bash
# Python profiling
python -m cProfile -o output.prof script.py
python -c "import pstats; p = pstats.Stats('output.prof'); p.sort_stats('cumulative').print(20)"

# 数据库慢查询
SELECT * FROM pg_stat_statements WHERE mean_exec_time > 100 ORDER BY mean_exec_time DESC;

# 前端 bundle 分析
cd frontend && npm run build -- --analyze
```
