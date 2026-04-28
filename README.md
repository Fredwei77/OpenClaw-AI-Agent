# OpenClaw Agent Framework

**Production-Ready AI Automation System (Anti-Ban · Structured Reasoning · Commercial Safe)**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Node Version](https://img.shields.io/badge/Node-18+-green.svg)](https://nodejs.org/)

---

## 📺 Demo Video
![OpenClaw Demo](./docs/assets/AI%20Agent%20Demo.mp4)

> [!TIP]
> **OpenClaw** is a powerful AI Agent framework designed for cross-border e-commerce (e.g., US market). It automates lead generation, customer research, and cold outreach while ensuring account safety through advanced anti-ban mechanisms.

---

## 🚀 Key Features

- **🛡️ Anti-Ban Engine**: 
  - Integrated **Residential Proxy** support to prevent IP-based blocking.
  - Dynamic **Rate Limiting** (e.g., LinkedIn 20 msgs/hr, FB 15 msgs/hr) to mimic human behavior.
  - Support for **Multi-Account** rotation.

- **🧠 Structured Reasoning**: 
  - Automated deep analysis of company websites, social media, and news.
  - **Lead Scoring System**: AI-driven prioritization (Company size, Industry, Purchase Intent).
  - Context-aware personalized cold emails/messages.

- **💼 Commercial Safe**:
  - **Local Persistence**: All customer data and chat logs stored in your own PostgreSQL database.
  - **GDPR-Friendly**: Designed with compliance and data privacy in mind.

---

## 🏗️ System Architecture

```mermaid
graph TD
    User([User Dashboard]) --> Gateway[OpenClaw Gateway]
    Gateway --> LeadAgent[Lead Agent - Search & Scraping]
    Gateway --> ResearchAgent[Research Agent - Analyisis & Scoring]
    Gateway --> ChatAgent[Chat Agent - Auto Reply]
    
    LeadAgent --> Sources(Google / LinkedIn / Facebook / X)
    ResearchAgent --> Analysis(Website / News / LinkedIn Profile)
    ChatAgent --> Social(Messenger / LinkedIn / X)
    
    Gateway --- DB[(PostgreSQL Local DB)]
```

---

## 📦 Modules

| Module | Core Technology | Description |
| :--- | :--- | :--- |
| **Lead Agent** | Playwright / Scrapy | Automatically discover leads from Google/Social Media. |
| **Research Agent** | GPT-4 / Claude / StepFun | Structured scoring and context extraction. |
| **Messenger Agent** | Webhooks / Browser-based | 24/7 AI-driven customer support & outreach. |

---

## 🛠️ Getting Started

### 1. Prerequisites
- Python 3.9+ 
- Node.js 18+
- PostgreSQL 14+

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/Fredwei77/OpenClaw-AI-Agent.git
cd OpenClaw-AI-Agent

# Install Backend Dependencies
pip install -r requirements.txt

# Install Frontend Dependencies
cd frontend
npm install
```

### 3. 配置环境变量
Copy the environment template and fill in your details:
```bash
cp .env.example .env
```

#### 3.1 AI API Keys（必填）
```env
OPENAI_API_KEY=sk-...        # OpenAI API Key
OPENROUTER_API_KEY=...       # OpenRouter API Key（推荐，支持多种模型）
```

#### 3.2 数据库配置（必填）
```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/openclaw_db
```

#### 3.3 浏览器爬取登录态配置（推荐）
要实现真实的 X/Twitter/LinkedIn 爬取，需要配置 Chrome 登录态：

1. **在 Chrome 中登录 X/Twitter/LinkedIn**
   - 关闭所有 Chrome 窗口
   - 打开 Chrome，使用你的账号登录 X、LinkedIn 等平台
   - 确认登录状态可以保持

2. **复制 Chrome 用户数据目录路径**
   - **Windows**: `C:/Users/你的用户名/AppData/Local/Google/Chrome/User Data`
   - **Mac**: `/Users/你的用户名/Library/Application Support/Google/Chrome`
   - **Linux**: `~/.config/google-chrome`

3. **配置 .env**
   ```env
   CHROME_USER_DATA_DIR=C:/Users/你的用户名/AppData/Local/Google/Chrome/User Data
   ```

4. **重启后端服务使配置生效**

#### 3.4 可选配置
```env
# 住宅代理（提高爬取稳定性）
SCRAPER_PROXY=http://username:password@proxyhost:port

# SerpAPI（合规的搜索结果API）
SERPAPI_KEY=your-serpapi-key
```

### 4. 运行服务

#### 启动后端服务
```bash
# 方式一：使用脚本
./scripts/dev.sh

# 方式二：手动启动
cd backend
python main.py
# 后端服务：http://localhost:8000
# API 文档：http://localhost:8000/docs
```

#### 启动前端服务
```bash
cd frontend
npm install  # 首次运行需要安装依赖
npm run dev
# 前端服务：http://localhost:5173
```

#### 验证服务运行
```bash
# 测试后端健康状态
curl http://localhost:8000/api/health

# 测试浏览器池状态
curl http://localhost:8000/api/agents/browser-status
```

---

## 📝 Roadmap
- [ ] Integration with more CRM platforms.
- [ ] Voice cloning for automated sales calls.
- [ ] Advanced visual dashboard for conversion tracking.

---

## 📄 License
Distributed under the MIT License. See `LICENSE` for more information.

---
Built with ❤️ by [OpenClaw Team](https://github.com/Fredwei77)
