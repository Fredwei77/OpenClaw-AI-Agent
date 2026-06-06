# Database Design & PostgreSQL Best Practices

## Use Scene
当需要创建或修改数据库架构时调用此技能。

## Schema 规范

### 1. 表命名
- 使用复数 snake_case：`leads`, `user_accounts`, `task_queue`
- 外键必须使用 `_id` 后缀：`user_id`, `lead_id`

### 2. 必需字段
每个表必须包含：
```sql
id SERIAL PRIMARY KEY,
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

### 3. UPSERT 模式
```python
# 使用 ON CONFLICT 去重
INSERT INTO leads (user_id, platform, username, profile_url, email, followers, tags)
VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (platform, username)
DO UPDATE SET
    profile_url = EXCLUDED.profile_url,
    email = COALESCE(EXCLUDED.email, leads.email),
    followers = EXCLUDED.followers,
    updated_at = CURRENT_TIMESTAMP
```

### 4. 索引策略
```sql
-- 高频查询字段创建索引
CREATE INDEX idx_leads_user_status ON leads(user_id, status);
CREATE INDEX idx_leads_platform ON leads(platform);

-- 避免在低选择性字段上单独建索引
-- 不要在 status 上单独建索引（只有 few values）
```

### 5. 迁移安全
```sql
-- 始终使用 IF NOT EXISTS
CREATE TABLE IF NOT EXISTS users (...);

-- 危险操作使用 CASCADE 要小心
DROP TABLE IF EXISTS old_table CASCADE;
```

### 6. 字段类型选择
| 数据类型 | 使用场景 |
|---------|---------|
| `SERIAL` | 自增主键 |
| `VARCHAR(n)` | 有长度限制的字符串 |
| `TEXT` | 无限制的长文本 |
| `NUMERIC` | 货币、评分等精确数值 |
| `JSONB` | 结构化数据（任务 payload）|
| `TIMESTAMP` | 日期时间 |
| `TEXT[]` | PostgreSQL 数组（tags） |

### 7. 外键约束
```sql
-- 良好的外键设计
ALTER TABLE leads ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- 使用部分索引优化
CREATE INDEX idx_leads_new ON leads(created_at) WHERE status = 'new';
```

## 连接池配置
```python
# 正确：使用连接池
pool = await asyncpg.create_pool(
    DATABASE_URL,
    min_size=5,      # 最小连接数
    max_size=20,     # 最大连接数
    command_timeout=60
)
```

## 常见错误
```sql
-- ❌ 错误：在文本字段上使用 LIKE 进行模糊查询（无法使用索引）
SELECT * FROM leads WHERE username LIKE '%john%';

-- ✅ 正确：使用 ILIKE（仍无法使用索引，但更灵活）
SELECT * FROM leads WHERE username ILIKE '%john%';

-- ✅ 最佳：使用 pg_trgm 扩展和 GIN 索引
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_leads_username_trgm ON leads USING gin (username gin_trgm_ops);
```
