# OpenClaw AI Agent

跨境电商获客 + 客服自动化 AI Agent 系统

## 项目结构

```
OpenClaw AI Agent/
├── agents/                    # AI Agent 实现
│   ├── base_agent.py          # 抽象基类
│   ├── lead_agent/            # 线索提取 (X/Twitter)
│   ├── linkedin_agent/        # LinkedIn 线索提取
│   ├── facebook_agent/         # Facebook 线索提取
│   ├── twitter_agent/         # Twitter 线索提取
│   ├── email_agent/           # 邮件自动化
│   ├── comment_agent/         # 评论自动化
│   ├── marketing_agent/       # 营销工作流
│   ├── report_agent/          # 数据报告
│   ├── data_agent/            # 数据清洗
│   ├── shopify_agent/          # Shopify 集成
│   └── ads_agent/             # 广告投放管理
│
├── backend/                   # FastAPI 后端
│   ├── main.py                # 应用入口
│   ├── db.py                  # 数据库操作 (连接池, UPSERT)
│   ├── api/                   # API 路由
│   │   ├── auth.py            # 认证 (JWT)
│   │   ├── leads.py           # 线索 CRUD
│   │   ├── tasks.py           # 任务队列
│   │   ├── agents.py          # Agent 执行
│   │   ├── products.py        # 产品管理
│   │   └── analytics.py       # 数据分析
│   ├── middleware.py         # 中间件
│   └── scheduler/             # 任务调度
│       └── task_queue.py      # 异步任务队列
│
├── browser_cluster/          # Playwright 浏览器集群
│   ├── manager/
│   │   ├── browser_manager.py # 浏览器管理
│   │   └── browser_pool.py    # 常驻浏览器池
│   └── workers/               # 浏览器工作器
│
├── frontend/                  # React + Vite 前端
│   ├── src/App.jsx           # 主应用
│   └── package.json
│
├── database/                  # PostgreSQL
│   └── migrations/
│       └── init.sql          # 数据库初始化
│
├── desktop/                  # Electron 桌面应用
├── plugins/                  # 插件系统
├── scripts/                  # 自动化脚本
└── .claude/                  # Claude Code 配置
    ├── settings.json         # Hooks 配置
    ├── skills/               # 自定义技能
    │   ├── openclaw-python/
    │   ├── openclaw-frontend/
    │   └── api-design/
    └── agents/              # 子代理
        ├── code-reviewer.md
        ├── security-reviewer.md
        ├── test-writer.md
        └── performance-analyzer.md
```

## 快速开始

### 1. 环境配置
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 填入配置
DATABASE_URL=postgresql://postgres:openclaw@localhost:5432/openclaw_db
JWT_SECRET_KEY=your-secret-key
OPENROUTER_API_KEY=your-api-key
```

### 2. 启动服务
```bash
# 方式一：使用脚本
./scripts/dev.sh

# 方式二：手动启动
cd backend && python main.py          # 后端 http://localhost:8000
cd frontend && npm run dev            # 前端 http://localhost:5173
```

### 3. 数据库迁移
```bash
./scripts/migrate.sh
# 或
psql $DATABASE_URL -f database/migrations/init.sql
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18, TailwindCSS v4, Lucide React, Recharts |
| 后端 | FastAPI, asyncpg, Pydantic, bcrypt, JWT |
| 浏览器 | Playwright, playwright-stealth |
| 数据库 | PostgreSQL |
| AI | OpenRouter (OpenAI 兼容 API) |

## API 端点

| 路由 | 方法 | 描述 |
|------|------|------|
| `/api/auth/register` | POST | 用户注册 |
| `/api/auth/login` | POST | 用户登录 |
| `/api/leads/` | GET | 获取线索列表 |
| `/api/leads/` | POST | 创建线索 |
| `/api/tasks/` | GET | 获取任务列表 |
| `/api/tasks/` | POST | 创建任务 |
| `/api/agents/test-scraper` | POST | 执行爬虫 |
| `/api/agents/test-llm` | POST | 测试 LLM |
| `/api/analytics/` | GET | 数据分析 |

## CLI 命令

```bash
# Claude Code hooks (已配置)
- /code-reviewer    # 代码审查
- /security-reviewer # 安全审查
- /test-writer      # 测试编写
- /performance-analyzer # 性能分析

# MCP 服务器 (需要手动添加)
claude mcp add github
claude mcp add postgres
claude mcp add playwright
claude mcp add slack
```

## 开发规范

### Python 代码
- 使用 `black` 格式化
- 使用 `ruff` Linting
- 使用 `mypy` 类型检查
- 异步代码使用 `async/await`
- 数据库操作使用连接池

### React 前端
- 组件使用函数式组件 + hooks
- API 调用统一管理
- 使用 `useCallback`/`useMemo` 优化
- Tailwind CSS 原子化样式

### Git 提交
```bash
# 使用 /commit 命令提交
/commit

# 提交信息格式
feat: add LinkedIn agent implementation
fix: resolve CORS issue in production
refactor: improve database connection pooling
```

## 环境变量

| 变量 | 描述 | 必填 |
|------|------|------|
| `DATABASE_URL` | PostgreSQL 连接 URL | 是 |
| `JWT_SECRET_KEY` | JWT 签名密钥 | 是 |
| `OPENROUTER_API_KEY` | OpenRouter API 密钥 | 是 |
| `SCRAPER_PROXY` | 爬虫代理 URL | 否 |
| `CHROME_USER_DATA_DIR` | Chrome 用户数据目录 | 否 |
| `ENVIRONMENT` | 环境 (development/production) | 否 |
| `ALLOWED_ORIGINS` | CORS 允许的来源 | 否 |

## 数据库

### 主要表

- `users` - 用户账户
- `leads` - 线索数据
- `tasks` - 任务队列
- `accounts` - 平台账户
- `messages` - 发送的消息
- `products` - 产品目录

### 索引

```sql
CREATE INDEX idx_leads_user_status ON leads(user_id, status);
CREATE INDEX idx_leads_platform_username ON leads(platform, username);
CREATE INDEX idx_tasks_user_status ON tasks(user_id, status);
CREATE INDEX idx_messages_lead_id ON messages(lead_id);
```

## 安全

- [x] JWT 认证
- [x] 密码 bcrypt 哈希
- [x] CORS 配置
- [x] 环境变量敏感信息保护
- [x] 数据库连接池
- [x] SQL UPSERT 防注入

## 插件系统

插件位于 `plugins/` 目录，结构：
```
plugins/
├── example_plugin/
│   ├── plugin.py           # 插件主文件
│   └── manifest.json      # 插件清单
└── plugin_manager/         # 插件管理器
```

## License

MIT
