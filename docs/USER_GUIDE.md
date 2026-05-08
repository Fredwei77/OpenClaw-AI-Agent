# OpenClaw AI Agent - 用户手册

跨境电商获客 + 客服自动化 AI Agent 系统

---

## 目录

1. [系统简介](#1-系统简介)
2. [环境要求](#2-环境要求)
3. [环境配置](#3-环境配置)
   - [3.1 安装基础依赖](#31-安装基础依赖)
   - [3.2 数据库配置](#32-数据库配置)
   - [3.3 环境变量配置](#33-环境变量配置)
   - [3.4 Python 虚拟环境](#34-python-虚拟环境)
   - [3.5 前端依赖安装](#35-前端依赖安装)
4. [启动方式](#4-启动方式)
   - [4.1 开发模式（源码）](#41-开发模式源码)
   - [4.2 桌面应用（Electron）](#42-桌面应用electron)
   - [4.3 生产部署](#43-生产部署)
5. [功能模块说明](#5-功能模块说明)
   - [5.1 系统概览 (Nexus Overview)](#51-系统概览-nexus-overview)
   - [5.2 线索捕获 (Lead Extractor)](#52-线索捕获-lead-extractor)
   - [5.3 营销引擎 (Marketing Engine)](#53-营销引擎-marketing-engine)
   - [5.4 成长分析 (Growth Analytics)](#54-成长分析-growth-analytics)
   - [5.5 插件生态 (Plugin Ecosystem)](#55-插件生态-plugin-ecosystem)
   - [5.6 技能模块 (Skill Modules)](#56-技能模块-skill-modules)
   - [5.7 系统配置 (System Config)](#57-系统配置-system-config)
6. [API 接口文档](#6-api-接口文档)
7. [数据库说明](#7-数据库说明)
8. [故障排除](#8-故障排除)
9. [安全注意事项](#9-安全注意事项)

---

## 1. 系统简介

OpenClaw AI Agent 是一套面向跨境电商的智能获客与客服自动化系统，集成了以下核心能力：

| 能力 | 说明 |
|------|------|
| 多平台线索采集 | 支持 X (Twitter)、LinkedIn、Shopify、Facebook、Instagram 等平台 |
| AI 智能营销 | 自动生成开发信、社交媒体话术、A/B 测试文案 |
| 全链路营销管道 | Research Agent 分析线索 → Chat Agent 生成多渠道消息 |
| 6 大技能模块 | 多语言翻译、竞品分析、主题行优化、LinkedIn 话术、A/B 变体、数据清洗 |
| 插件系统 | 可扩展的插件架构，支持自定义功能 |
| 数据分析 | 线索质量评分、意图分层、营销效果追踪 |

### 技术架构

```
┌─────────────────────────────────────────────────┐
│              Electron 桌面应用 (可选)              │
│  ┌───────────────────────────────────────────┐  │
│  │         React 前端 (端口 5173/打包后本地)     │  │
│  └─────────────────┬─────────────────────────┘  │
│                    │ HTTP API                     │
│  ┌─────────────────▼─────────────────────────┐  │
│  │         FastAPI 后端 (端口 8000)             │  │
│  │  ┌──────────┬──────────┬───────────────┐  │  │
│  │  │ Auth API │ Agent API│ Analytics API │  │  │
│  │  └──────────┴──────────┴───────────────┘  │  │
│  │         │                    │              │  │
│  │  ┌──────▼──────┐    ┌──────▼──────┐       │  │
│  │  │ Playwright  │    │  OpenRouter  │       │  │
│  │  │ 浏览器集群   │    │  LLM API    │       │  │
│  │  └─────────────┘    └─────────────┘       │  │
│  └─────────────────┬─────────────────────────┘  │
│                    │                              │
│  ┌─────────────────▼─────────────────────────┐  │
│  │           PostgreSQL 数据库                  │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

---

## 2. 环境要求

### 必需

| 组件 | 最低版本 | 推荐版本 |
|------|----------|----------|
| Python | 3.10+ | 3.12 |
| Node.js | 18+ | 20 LTS |
| PostgreSQL | 14+ | 16 |
| Chrome 浏览器 | 最新版 | 最新版 |

### 可选

| 组件 | 用途 |
|------|------|
| Redis | 任务队列（Celery） |
| Git | 版本管理 |

### API 密钥

| 密钥 | 获取地址 | 用途 |
|------|----------|------|
| OpenRouter API Key | https://openrouter.ai/keys | AI 模型调用（必需） |

---

## 3. 环境配置

### 3.1 安装基础依赖

**Windows (推荐使用 winget)：**

```powershell
# Python
winget install Python.Python.3.12

# Node.js
winget install OpenJS.NodeJS.LTS

# PostgreSQL
winget install PostgreSQL.PostgreSQL.16

# Git
winget install Git.Git
```

**macOS：**

```bash
brew install python@3.12 node@20 postgresql@16 git
```

**Linux (Ubuntu/Debian)：**

```bash
sudo apt update
sudo apt install python3.12 python3.12-venv nodejs npm postgresql git
```

### 3.2 数据库配置

**1. 创建数据库：**

```bash
# 登录 PostgreSQL
psql -U postgres

# 创建数据库和用户
CREATE DATABASE openclaw_db;
CREATE USER openclaw WITH PASSWORD 'openclaw';
GRANT ALL PRIVILEGES ON DATABASE openclaw_db TO openclaw;
\q
```

**2. 执行数据库迁移：**

```bash
# 方式一：使用 psql
psql -U openclaw -d openclaw_db -f database/migrations/init.sql

# 方式二：使用脚本（Linux/macOS）
./scripts/migrate.sh
```

**3. 验证数据库：**

```bash
psql -U openclaw -d openclaw_db -c "\dt"
```

应看到 10 张表：`users`, `accounts`, `proxies`, `leads`, `messages`, `comments`, `stores`, `products`, `ads`, `tasks`

### 3.3 环境变量配置

复制环境变量模板并编辑：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入以下配置：

```env
# ========== 必填 ==========
# 数据库连接
DATABASE_URL=postgresql://openclaw:openclaw@localhost:5432/openclaw_db

# JWT 密钥（用于用户认证，请替换为随机生成的密钥）
# 生成命令：python -c "import secrets; print(secrets.token_urlsafe(32))"
JWT_SECRET_KEY=your-generated-secret-key-here

# OpenRouter API Key（AI 功能必需）
# 获取地址：https://openrouter.ai/keys
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# ========== 可选 ==========
# 环境模式：development / production
ENVIRONMENT=development

# 调试模式（生产环境请设为 False）
DEBUG=True

# CORS 允许的来源（逗号分隔）
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

# 代理配置（用于爬虫）
# PROXY_HOST=
# PROXY_USERNAME=
# PROXY_PASSWORD=

# Chrome 用户数据目录（保持登录会话）
# CHROME_USER_DATA_DIR=C:\Users\YourName\AppData\Local\Google\Chrome\User Data

# Redis（任务队列，可选）
# REDIS_URL=redis://localhost:6379/0
```

### 3.4 Python 虚拟环境

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 安装后端依赖
pip install -r backend/requirements.txt

# 如果没有 requirements.txt，手动安装核心依赖：
pip install fastapi uvicorn asyncpg python-dotenv pydantic bcrypt python-jose playwright playwright-stealth httpx openai python-multipart email-validator
```

### 3.5 前端依赖安装

```bash
cd frontend
npm install
cd ..
```

---

## 4. 启动方式

### 4.1 开发模式（源码）

#### 方式一：一键启动（推荐）

```powershell
# Windows PowerShell
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
```

此脚本会自动：
1. 启动后端服务 → http://localhost:8000
2. 启动前端开发服务器 → http://localhost:5173
3. 启动 Chrome（带远程调试端口 9222）并打开前端页面

#### 方式二：手动启动

打开两个终端窗口：

**终端 1 - 后端：**
```bash
cd backend
# 确保虚拟环境已激活
python main.py
# 等待看到：Uvicorn running on http://0.0.0.0:8000
```

**终端 2 - 前端：**
```bash
cd frontend
npm run dev
# 等待看到：Local: http://localhost:5173/
```

然后在浏览器中打开 http://localhost:5173

#### 方式三：Chrome 调试模式

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome-debug-profile" http://localhost:5173
```

### 4.2 桌面应用（Electron）

#### 直接运行安装包

```
desktop\electron_app\dist\OpenClaw AI Setup 1.0.0.exe
```

运行安装程序，按提示完成安装。安装后从桌面快捷方式或开始菜单启动。

#### 从源码运行 Electron

```bash
cd desktop/electron_app
npm install
npm start
```

#### 重新构建 Electron 安装包

```bash
cd desktop/electron_app
npm run dist
```

构建产物位于 `desktop/electron_app/dist/` 目录。

> **注意：** 构建前需先执行 `cd frontend && npm run build` 生成前端打包文件。

### 4.3 生产部署

**1. 构建前端：**

```bash
cd frontend
npm run build
```

**2. 配置环境变量：**

```env
ENVIRONMENT=production
DEBUG=False
ALLOWED_ORIGINS=https://your-domain.com
```

**3. 启动后端：**

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

**4. 反向代理（Nginx 示例）：**

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        root /path/to/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 5. 功能模块说明

系统包含 7 个功能模块，通过顶部导航栏切换。

### 5.1 系统概览 (Nexus Overview)

系统主仪表盘，展示全局状态：

| 指标 | 说明 |
|------|------|
| 服务状态 | 后端连接状态（在线/离线） |
| 线索总数 | 已采集的线索数量 |
| 系统健康 | 整体运行状态 |
| 活跃代理 | 当前运行的 Agent 数量 |

### 5.2 线索捕获 (Lead Extractor)

从社交媒体平台采集潜在客户信息。

**支持平台：**

| 平台 | 说明 |
|------|------|
| X (Twitter) | 搜索推特用户 |
| LinkedIn Matrix | 搜索领英用户 |
| Shopify Network | 搜索 Shopify 商家 |

**使用步骤：**

1. 选择目标平台
2. 输入行业关键词（如 "fitness equipment"、"跨境电商"）
3. 点击「Deploy Extractor」开始采集
4. 采集结果实时显示在下方表格中

**表格字段：**

| 列名 | 说明 |
|------|------|
| Platform | 来源平台 |
| Account Identity | 用户名/账号名 |
| Neural Link | 用户主页链接 |
| Target Variables | 粉丝数、标签等 |

### 5.3 营销引擎 (Marketing Engine)

包含两大部分：AI 营销助手和全链路营销管道。

#### 5.3.1 AI 营销助手

点击右侧「MARKETING AI」按钮打开聊天面板，可向 AI 发送指令生成营销内容。

**支持的营销动作：**

| 动作 | 说明 |
|------|------|
| 生成个性化开发信 | 基于线索数据生成 Cold Email |
| 批量潜在客户分类 | 将线索分为高/中/低意向 |
| AI 社交媒体跟进 | 生成 Twitter/LinkedIn 跟进话术 |

#### 5.3.2 全链路营销管道 (Full Marketing Pipeline)

一键执行「Research Agent + Chat Agent」双阶段流程：

**流程：**

```
线索数据 → Research Agent（分析线索、评分分层）→ Chat Agent（生成多渠道消息）→ 输出
```

**输出内容：**

| 渠道 | 说明 |
|------|------|
| Email | 个性化开发信（含主题行、正文、CTA） |
| LinkedIn DM | 领英私信模板 |
| Twitter DM | 推特私信模板 |

**线索分层：**

| 等级 | 分数范围 | 颜色 |
|------|----------|------|
| High (A) | ≥75 | 绿色 |
| Medium (B) | 50-74 | 蓝色 |
| Low (C) | <50 | 灰色 |

### 5.4 成长分析 (Growth Analytics)

数据可视化仪表盘，展示营销效果和线索质量趋势。

### 5.5 插件生态 (Plugin Ecosystem)

管理已安装的插件和浏览插件市场。

**功能：**
- 搜索已安装插件
- 启用/禁用插件
- 浏览插件市场并安装新插件

**插件目录结构：**

```
plugins/
├── example_plugin/
│   ├── plugin.py        # 插件主文件
│   └── manifest.json    # 插件清单
└── plugin_manager/      # 插件管理器
```

### 5.6 技能模块 (Skill Modules)

6 个内置 AI 技能，每个技能接受文本输入并返回结构化结果。

| # | 技能名称 | 标签 | 输入 | 输出 |
|---|----------|------|------|------|
| 1 | 多语言翻译 | NLP | 营销文案 | 英/中/西/法/德 五国翻译 |
| 2 | 深度竞品分析 | Research | 产品/行业/线索 | 竞品画像、优劣势、市场趋势 |
| 3 | 邮件主题行优化 | Email | 产品/行业描述 | 10 条高打开率主题行 |
| 4 | 领英触达话术 | Social | 目标线索信息 | 3 种风格私信（专业/友好/大胆） |
| 5 | A/B 测试变体 | CRO | 原始营销文案 | 3 个变体版本（含假设） |
| 6 | 线索数据清洗 | Data | 线索数据 | 有效/无效统计、问题清单 |

**使用方法：**

1. 展开目标技能卡片
2. 在输入框中粘贴文本、关键词或数据
3. 点击「执行技能」
4. 查看结构化结果，支持一键复制

### 5.7 系统配置 (System Config)

| 配置项 | 说明 |
|--------|------|
| API Key 管理 | 更新 OpenRouter API Key |
| AI 代理设置 | 默认 LLM 模型选择 |
| 最大并发爬虫数 | 同时运行的爬虫数量 |
| 网络与 Webhooks | 网络配置 |
| 测试连接 | 验证后端 API 连通性 |

---

## 6. API 接口文档

后端运行在 http://localhost:8000，所有接口以 `/api` 为前缀。

### 6.1 认证接口

| 路由 | 方法 | 描述 | 请求体 |
|------|------|------|--------|
| `/api/auth/register` | POST | 用户注册 | `{"email": "...", "password": "..."}` |
| `/api/auth/login` | POST | 用户登录 | `{"email": "...", "password": "..."}` |

**登录响应示例：**
```json
{
  "status": "success",
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "user": {"id": 1, "email": "user@example.com"}
}
```

### 6.2 线索接口

| 路由 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/api/leads/` | GET | 获取线索列表 | 需要 |
| `/api/leads/` | POST | 创建线索 | 需要 |

### 6.3 任务接口

| 路由 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/api/tasks/` | GET | 获取任务列表 | 需要 |
| `/api/tasks/` | POST | 创建任务 | 需要 |

### 6.4 Agent 接口

| 路由 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/api/agents/test-scraper` | POST | 执行爬虫 | 不需要 |
| `/api/agents/test-llm` | POST | 测试 LLM | 不需要 |
| `/api/agents/marketing-pipeline` | POST | 全链路营销管道 | 需要 |
| `/api/agents/execute-skill` | POST | 执行技能模块 | 需要 |

**测试 LLM 请求示例：**
```json
{
  "prompt": "写一封跨境电商开发信",
  "language": "zh"
}
```

### 6.5 分析接口

| 路由 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/api/analytics/` | GET | 数据分析 | 需要 |

### 6.6 系统接口

| 路由 | 方法 | 描述 |
|------|------|------|
| `/` | GET | 根路径信息 |
| `/health` | GET | 健康检查 |
| `/metrics` | GET | Prometheus 指标 |

### 6.7 认证方式

需要认证的接口需在请求头中携带 JWT Token：

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

---

## 7. 数据库说明

### 7.1 数据表

| 表名 | 说明 | 主要字段 |
|------|------|----------|
| `users` | 用户账户 | email, password_hash, role |
| `leads` | 线索数据 | platform, username, email, followers, tags, status |
| `tasks` | 任务队列 | agent_name, task_type, payload, status, result |
| `accounts` | 平台账户 | platform, username, password, status, risk_score |
| `messages` | 发送的消息 | lead_id, content, status, sent_at |
| `comments` | 评论 | account_id, post_url, content, status |
| `stores` | 店铺 | platform, store_url, category |
| `products` | 产品 | product_name, price, category, rating |
| `ads` | 广告 | platform, advertiser, ad_text, engagement |
| `proxies` | 代理 | host, port, username, password, status |

### 7.2 线索状态流转

```
new → contacted → qualified → converted
                  → rejected
```

### 7.3 任务状态流转

```
pending → running → completed
                  → failed
```

### 7.4 性能索引

数据库已预建 14 个索引，覆盖高频查询场景：

- 线索查询：`user_id + status`、`platform + username`、`created_at`
- 任务查询：`user_id + status`、`status`、`created_at`
- 消息查询：`lead_id`、`account_id`、`status`
- 账户查询：`platform + status`、`risk_score`
- 产品查询：`user_id`、`category`

---

## 8. 故障排除

### 8.1 CORS 错误

**现象：** 前端控制台报 `Access to fetch has been blocked by CORS policy`

**解决：**
1. 确认后端已启动（http://localhost:8000）
2. 检查 `.env` 中 `ALLOWED_ORIGINS` 包含前端地址
3. 开发模式下系统自动允许 localhost 来源，重启后端即可

### 8.2 数据库连接失败

**现象：** 后端启动报 `Connection refused` 或 `database does not exist`

**解决：**
1. 确认 PostgreSQL 服务已启动
2. 检查 `DATABASE_URL` 连接信息是否正确
3. 确认数据库已创建并执行了迁移脚本

```bash
# 检查 PostgreSQL 状态
pg_isready

# 测试连接
psql -U openclaw -d openclaw_db -c "SELECT 1"
```

### 8.3 AI 功能不工作

**现象：** 点击营销动作或技能执行后返回错误

**解决：**
1. 检查 `.env` 中 `OPENROUTER_API_KEY` 是否正确配置
2. 确认 API Key 有效（访问 https://openrouter.ai/keys 检查）
3. 检查账户余额是否充足

### 8.4 爬虫采集无结果

**现象：** 点击 Deploy Extractor 后表格为空

**解决：**
1. 确认 Chrome 浏览器已安装
2. 检查网络连接（可能需要配置代理）
3. 尝试更具体的关键词
4. 某些平台可能需要登录态，配置 `CHROME_USER_DATA_DIR`

### 8.5 Electron 应用无法启动

**现象：** 双击 exe 后无反应或闪退

**解决：**
1. 确认 Python 已安装并在 PATH 中
2. 确认 `.venv` 虚拟环境已创建并安装了依赖
3. 从命令行启动查看错误信息：
   ```bash
   cd desktop/electron_app
   npm start
   ```
4. 检查 `desktop/electron_app/dist/win-unpacked/resources/.env` 配置

### 8.6 前端构建失败

**现象：** `npm run build` 报错

**解决：**
```bash
# 清除缓存重新安装
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

### 8.7 端口被占用

**现象：** 启动报 `Address already in use`

```bash
# Windows 查找占用端口的进程
netstat -ano | findstr :8000
# 终止进程
taskkill /PID <进程ID> /F

# macOS/Linux
lsof -i :8000
kill -9 <进程ID>
```

---

## 9. 安全注意事项

### 已实现的安全措施

- [x] JWT 令牌认证
- [x] 密码 bcrypt 哈希存储
- [x] CORS 跨域配置
- [x] 环境变量敏感信息保护
- [x] 数据库连接池
- [x] SQL 参数化查询（防注入）

### 生产环境建议

1. **更换 JWT 密钥：** 使用 `python -c "import secrets; print(secrets.token_urlsafe(32))"` 生成强密钥
2. **关闭调试模式：** `.env` 中设置 `DEBUG=False`
3. **限制 CORS 来源：** 仅允许正式域名
4. **使用 HTTPS：** 配置 SSL 证书
5. **定期备份数据库：**
   ```bash
   pg_dump -U openclaw openclaw_db > backup_$(date +%Y%m%d).sql
   ```
6. **保护 `.env` 文件：** 确保不被提交到版本控制
7. **API Key 轮换：** 定期更换 OpenRouter API Key

---

## 附录：快捷命令速查

| 操作 | 命令 |
|------|------|
| 一键启动开发环境 | `powershell -ExecutionPolicy Bypass -File scripts\dev.ps1` |
| 仅启动后端 | `cd backend && python main.py` |
| 仅启动前端 | `cd frontend && npm run dev` |
| 构建前端 | `cd frontend && npm run build` |
| 构建 Electron | `cd desktop/electron_app && npm run dist` |
| 数据库迁移 | `psql -U openclaw -d openclaw_db -f database/migrations/init.sql` |
| 生成 JWT 密钥 | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| 健康检查 | `curl http://localhost:8000/health` |
| 查看 API 文档 | 浏览器打开 http://localhost:8000/docs |

---

> **文档版本：** v1.0.0
> **更新日期：** 2026-05-08
> **适用版本：** OpenClaw AI Agent 1.0.0
