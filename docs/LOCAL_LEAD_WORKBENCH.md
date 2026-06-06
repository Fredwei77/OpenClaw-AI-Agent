# 单机版 Lead 工作台

## 前置依赖

- Python 3.11 或 3.12
- Node.js 20+
- Docker Desktop，或本机 PostgreSQL 16+

## 首次启动

```powershell
Copy-Item .env.example .env
powershell -ExecutionPolicy Bypass -File scripts/start-postgres.ps1
powershell -ExecutionPolicy Bypass -File scripts/migrate.ps1

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

Push-Location frontend
npm.cmd install
npm.cmd run build
Pop-Location

powershell -ExecutionPolicy Bypass -File scripts/dev.ps1
```

如果项目目录移动后 `.venv` 无法启动，请删除并重新创建虚拟环境。
`scripts/dev.ps1` 会优先使用可用的项目 `.venv`，并在其损坏时回退到系统 Python。

## Lead Workbench Flow

1. Register or log in.
2. Extract leads or create leads through the API.
3. Refresh the Lead workspace to load persisted records.
4. Update each lead status as it moves through the funnel.
5. Run the Marketing Pipeline to generate editable outreach drafts.
6. Open lead details to approve, mark as sent, or archive drafts.
7. Return to Marketing Engine to track the persisted campaign batch in Recent Campaigns.

“近期营销活动”来自真实 Pipeline 批次，不再使用演示数据。活动进度根据草稿生命周期
自动计算：全部草稿为排队中，出现审批或发送后为执行中，全部发送或归档后为已完成。

The Marketing Pipeline uses OpenRouter when configured. Without an
`OPENROUTER_API_KEY`, it falls back to local deterministic drafts so the
single-machine workflow remains usable offline.

前端地址：`http://localhost:5173`

后端健康检查：`http://localhost:8000/health`

## 运行状态与配置

登录后打开“系统配置”页面，可以查看数据库、浏览器池、任务队列和
OpenRouter 路由的实时安全摘要。页面不会读取或回传 API Key 明文。

本机配置统一由根目录 `.env` 管理。修改配置后执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 -Restart
```

常用单机参数：

- `OPENROUTER_API_KEY`：留空时使用可读的本地回退文案。
- `OPENROUTER_MARKETING_MODEL`：营销动作主模型。
- `OPENROUTER_MARKETING_FALLBACK_MODELS`：逗号分隔的模型回退链。
- `MAX_CONCURRENT_TASKS`：单机任务队列并发上限，默认 `5`。
- `MAX_BROWSER_INSTANCES`：Playwright 浏览器池上限，默认 `3`。
- `CHROME_USER_DATA_DIR`：需要复用浏览器登录态时配置。

## 数据规则

- Lead 写入必须关联当前登录用户。
- 默认不会生成演示 Lead。
- 仅在演示环境中设置 `DEMO_MODE=true`。
- Electron 安装包不会包含本机 `.env` 文件。

## Electron 安装版

`OpenClaw AI Setup 1.1.0.exe` 包含当前前端、后端、Agent、浏览器集群和数据库迁移。
首次运行时会在 Electron 用户配置目录生成独立 `.env`，并自动生成 JWT 密钥。
安装版后端启动时会执行幂等增量迁移，因此旧版数据库可以直接升级。
