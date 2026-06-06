# Changelog

## [v1.1.0] - 2026-06-02

### 单机 Lead 工作台产品化

- 完成登录后 Lead 持久化、状态流转、线索详情和营销草稿闭环。
- 修复社交平台粉丝数溢出，统一使用 `BIGINT` 和输入归一化。
- 优化四类 AI 营销动作输出质量，增加 OpenRouter 模型路由与本地回退。
- 新增真实运行状态中心，展示数据库、浏览器池、任务队列和 AI 路由。
- “近期营销活动”改为真实 Pipeline 批次，支持审批进度实时聚合。
- Electron 安装版首次运行自动生成本机配置，并在启动时执行幂等数据库升级。

## [v0.1.0] - 2026-05-08

### 🎉 首发版本

### ✨ 新功能
- **多 Agent 系统**：Lead Agent、Research Agent、Chat Agent 协作工作流
- **Anti-Ban Engine**：住宅代理支持、动态限速、多账号轮换
- **Playwright 浏览器集群**：支持高速批量操作
- **browser-harness 集成**：基于真实 Chrome，抗检测更强
- **结构化 Lead Scoring**：AI 评分系统，自动排序高质量客户
- **Electron 桌面应用**：支持本地桌面端部署
- **6 套 DESIGN.md 参考库**：Shopify、Stripe、Linear、Vercel、Notion、Supabase

### 🛠️ 技术特性
- FastAPI 后端 + React 前端
- PostgreSQL 本地存储
- JWT 认证 + bcrypt 密码哈希
- 支持 OpenRouter 多模型（GPT-4 / Claude / 国产模型）
- Claude Code hooks 配置完整（代码审查、安全审查、测试生成）

### 🐛 修复
- CORS 跨域问题修复
- 数据库连接池优化
- SQL 查询条件修复

### 📖 文档
- 中英双语 README
- CLAUDE.md 完整开发规范
- 设计系统参考库使用指南
