# OpenClaw AI Agent - User Guide

Cross-Border Ecommerce Customer Acquisition & Customer Service Automation AI Agent System

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Requirements](#2-system-requirements)
3. [Environment Setup](#3-environment-setup)
   - [3.1 Install Prerequisites](#31-install-prerequisites)
   - [3.2 Database Setup](#32-database-setup)
   - [3.3 Environment Variables](#33-environment-variables)
   - [3.4 Python Virtual Environment](#34-python-virtual-environment)
   - [3.5 Frontend Dependencies](#35-frontend-dependencies)
4. [Starting the Application](#4-starting-the-application)
   - [4.1 Development Mode (Source)](#41-development-mode-source)
   - [4.2 Desktop App (Electron)](#42-desktop-app-electron)
   - [4.3 Production Deployment](#43-production-deployment)
5. [Feature Modules](#5-feature-modules)
   - [5.1 Nexus Overview](#51-nexus-overview)
   - [5.2 Lead Extractor](#52-lead-extractor)
   - [5.3 Marketing Engine](#53-marketing-engine)
   - [5.4 Growth Analytics](#54-growth-analytics)
   - [5.5 Plugin Ecosystem](#55-plugin-ecosystem)
   - [5.6 Skill Modules](#56-skill-modules)
   - [5.7 System Config](#57-system-config)
6. [API Reference](#6-api-reference)
7. [Database Schema](#7-database-schema)
8. [Troubleshooting](#8-troubleshooting)
9. [Security Notes](#9-security-notes)

---

## 1. Introduction

OpenClaw AI Agent is an intelligent customer acquisition and customer service automation system for cross-border e-commerce. It integrates:

| Capability | Description |
|------------|-------------|
| Multi-Platform Lead Extraction | X (Twitter), LinkedIn, Shopify, Facebook, Instagram |
| AI-Powered Marketing | Cold emails, social media scripts, A/B test copy |
| Full Marketing Pipeline | Research Agent analyzes leads → Chat Agent generates multi-channel messages |
| 6 Skill Modules | Multi-lang translation, competitor analysis, subject line optimizer, LinkedIn scripts, A/B variants, data scrubber |
| Plugin System | Extensible plugin architecture |
| Analytics | Lead quality scoring, intent tiering, marketing performance tracking |

### Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, TailwindCSS v4, Lucide React, Recharts |
| Backend | FastAPI, asyncpg, Pydantic, bcrypt, JWT |
| Browser Automation | Playwright, playwright-stealth |
| Database | PostgreSQL |
| AI | OpenRouter (OpenAI-compatible API) |
| Desktop | Electron 33 |

---

## 2. System Requirements

### Required

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Python | 3.10+ | 3.12 |
| Node.js | 18+ | 20 LTS |
| PostgreSQL | 14+ | 16 |
| Chrome Browser | Latest | Latest |

### Optional

| Component | Purpose |
|-----------|---------|
| Redis | Task queue (Celery) |
| Git | Version control |

### API Keys

| Key | Where to Get | Purpose |
|-----|--------------|---------|
| OpenRouter API Key | https://openrouter.ai/keys | AI model access (required) |

---

## 3. Environment Setup

### 3.1 Install Prerequisites

**Windows (using winget):**

```powershell
winget install Python.Python.3.12
winget install OpenJS.NodeJS.LTS
winget install PostgreSQL.PostgreSQL.16
winget install Git.Git
```

**macOS:**

```bash
brew install python@3.12 node@20 postgresql@16 git
```

**Linux (Ubuntu/Debian):**

```bash
sudo apt update
sudo apt install python3.12 python3.12-venv nodejs npm postgresql git
```

### 3.2 Database Setup

**1. Create the database:**

```bash
psql -U postgres

CREATE DATABASE openclaw_db;
CREATE USER openclaw WITH PASSWORD 'openclaw';
GRANT ALL PRIVILEGES ON DATABASE openclaw_db TO openclaw;
\q
```

**2. Run migrations:**

```bash
psql -U openclaw -d openclaw_db -f database/migrations/init.sql
```

**3. Verify:**

```bash
psql -U openclaw -d openclaw_db -c "\dt"
```

You should see 10 tables: `users`, `accounts`, `proxies`, `leads`, `messages`, `comments`, `stores`, `products`, `ads`, `tasks`

### 3.3 Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
# ========== Required ==========
DATABASE_URL=postgresql://openclaw:openclaw@localhost:5432/openclaw_db
JWT_SECRET_KEY=your-generated-secret-key-here
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# ========== Optional ==========
ENVIRONMENT=development
DEBUG=True
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

Generate a JWT secret key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3.4 Python Virtual Environment

```bash
python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r backend/requirements.txt

# Or install core dependencies manually:
pip install fastapi uvicorn asyncpg python-dotenv pydantic bcrypt python-jose playwright playwright-stealth httpx openai python-multipart email-validator
```

### 3.5 Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

---

## 4. Starting the Application

### 4.1 Development Mode (Source)

#### Option A: One-Click Start (Recommended)

```powershell
# Windows PowerShell
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
```

This script automatically:
1. Starts the backend → http://localhost:8000
2. Starts the frontend dev server → http://localhost:5173
3. Launches Chrome with remote debugging (port 9222)

#### Option B: Manual Start

**Terminal 1 - Backend:**
```bash
cd backend
python main.py
# Wait for: Uvicorn running on http://0.0.0.0:8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
# Wait for: Local: http://localhost:5173/
```

Open http://localhost:5173 in your browser.

#### Option C: Chrome Debug Mode

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome-debug-profile" http://localhost:5173
```

### 4.2 Desktop App (Electron)

#### Run the Installer

```
desktop\electron_app\dist\OpenClaw AI Setup 1.0.0.exe
```

Run the installer and follow the prompts. Launch from the desktop shortcut or Start Menu.

#### Run from Source

```bash
cd desktop/electron_app
npm install
npm start
```

#### Rebuild the Installer

```bash
cd frontend && npm run build && cd ..
cd desktop/electron_app
npm run dist
```

Output: `desktop/electron_app/dist/OpenClaw AI Setup 1.0.0.exe`

### 4.3 Production Deployment

**1. Build frontend:**
```bash
cd frontend && npm run build
```

**2. Set environment:**
```env
ENVIRONMENT=production
DEBUG=False
ALLOWED_ORIGINS=https://your-domain.com
```

**3. Start backend:**
```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

**4. Nginx reverse proxy:**
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

## 5. Feature Modules

The system has 7 modules accessible via the top navigation bar.

### 5.1 Nexus Overview

Main dashboard showing global system status:

| Metric | Description |
|--------|-------------|
| Server Integrity | Backend connection status |
| Total Leads Extracted | Number of leads collected |
| System Health | Overall health status |
| Active Droids | Number of running agents |

### 5.2 Lead Extractor

Extract potential customer information from social media platforms.

**Supported Platforms:**

| Platform | Description |
|----------|-------------|
| X (Twitter) | Search Twitter users |
| LinkedIn Matrix | Search LinkedIn users |
| Shopify Network | Search Shopify merchants |

**Usage:**

1. Select target platform
2. Enter niche keyword (e.g. "fitness equipment", "yoga mat")
3. Click "Deploy Extractor"
4. Results appear in the table below

**Table Columns:**

| Column | Description |
|--------|-------------|
| Platform | Source platform |
| Account Identity | Username/account name |
| Neural Link | Profile URL |
| Target Variables | Followers, tags, etc. |

### 5.3 Marketing Engine

Two components: AI Marketing Assistant and Full Marketing Pipeline.

#### 5.3.1 AI Marketing Assistant

Click the "MARKETING AI" button to open the chat panel. Send commands to generate marketing content.

**Available Actions:**

| Action | Description |
|--------|-------------|
| Generate Cold Email | Personalized email based on lead data |
| Lead Classification | Categorize leads as High/Medium/Low intent |
| Social Media Follow-up | Generate Twitter/LinkedIn follow-up scripts |

#### 5.3.2 Full Marketing Pipeline

One-click "Research Agent + Chat Agent" dual-stage workflow:

```
Lead Data → Research Agent (analyze, score, tier) → Chat Agent (generate messages) → Output
```

**Output Channels:**

| Channel | Description |
|---------|-------------|
| Email | Personalized cold email (subject, body, CTA) |
| LinkedIn DM | LinkedIn direct message template |
| Twitter DM | Twitter direct message template |

**Lead Tiering:**

| Tier | Score | Color |
|------|-------|-------|
| High (A) | ≥75 | Green |
| Medium (B) | 50-74 | Blue |
| Low (C) | <50 | Gray |

### 5.4 Growth Analytics

Data visualization dashboard showing marketing performance and lead quality trends.

### 5.5 Plugin Ecosystem

Manage installed plugins and browse the plugin marketplace.

- Search installed plugins
- Enable/disable plugins
- Browse marketplace and install new plugins

**Plugin Structure:**
```
plugins/
├── example_plugin/
│   ├── plugin.py        # Plugin main file
│   └── manifest.json    # Plugin metadata
└── plugin_manager/      # Plugin manager
```

### 5.6 Skill Modules

6 built-in AI skills that accept text input and return structured results.

| # | Skill Name | Tag | Input | Output |
|---|-----------|-----|-------|--------|
| 1 | Multi-lang Translate | NLP | Marketing copy | EN/ZH/ES/FR/DE translations |
| 2 | Deep Competitor Analysis | Research | Product/industry/leads | Competitor profiles, strengths, trends |
| 3 | Subject Line Optimizer | Email | Product/industry description | 10 high-open-rate subject lines |
| 4 | LinkedIn Outreach Script | Social | Target lead info | 3 scripts (professional/friendly/bold) |
| 5 | A/B Variant Generator | CRO | Original marketing copy | 3 variants with hypotheses |
| 6 | Lead Data Scrubber | Data | Lead data | Valid/invalid stats, issue list |

**Usage:**

1. Expand the target skill card
2. Paste text, keywords, or data into the input field
3. Click "Run Skill"
4. View structured results with one-click copy

### 5.7 System Config

| Setting | Description |
|---------|-------------|
| API Key Management | Update OpenRouter API Key |
| AI Agent Settings | Default LLM model selection |
| Max Concurrent Scrapers | Number of simultaneous scrapers |
| Network & Webhooks | Network configuration |
| Test Connection | Verify backend API connectivity |

---

## 6. API Reference

Backend runs at http://localhost:8000. All endpoints are prefixed with `/api`.

### 6.1 Auth Endpoints

| Route | Method | Description | Body |
|-------|--------|-------------|------|
| `/api/auth/register` | POST | Register user | `{"email": "...", "password": "..."}` |
| `/api/auth/login` | POST | Login user | `{"email": "...", "password": "..."}` |

### 6.2 Lead Endpoints

| Route | Method | Description | Auth |
|-------|--------|-------------|------|
| `/api/leads/` | GET | List leads | Required |
| `/api/leads/` | POST | Create lead | Required |

### 6.3 Task Endpoints

| Route | Method | Description | Auth |
|-------|--------|-------------|------|
| `/api/tasks/` | GET | List tasks | Required |
| `/api/tasks/` | POST | Create task | Required |

### 6.4 Agent Endpoints

| Route | Method | Description | Auth |
|-------|--------|-------------|------|
| `/api/agents/test-scraper` | POST | Run scraper | No |
| `/api/agents/test-llm` | POST | Test LLM | No |
| `/api/agents/marketing-pipeline` | POST | Full marketing pipeline | Required |
| `/api/agents/execute-skill` | POST | Execute skill module | Required |

### 6.5 Analytics Endpoints

| Route | Method | Description | Auth |
|-------|--------|-------------|------|
| `/api/analytics/` | GET | Data analytics | Required |

### 6.6 System Endpoints

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Root info |
| `/health` | GET | Health check |
| `/metrics` | GET | Prometheus metrics |

### 6.7 Authentication

Authenticated endpoints require a JWT token in the header:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

Interactive API docs are available at http://localhost:8000/docs (Swagger UI).

---

## 7. Database Schema

### 7.1 Tables

| Table | Description | Key Fields |
|-------|-------------|------------|
| `users` | User accounts | email, password_hash, role |
| `leads` | Lead data | platform, username, email, followers, tags, status |
| `tasks` | Task queue | agent_name, task_type, payload, status, result |
| `accounts` | Platform accounts | platform, username, password, status, risk_score |
| `messages` | Sent messages | lead_id, content, status, sent_at |
| `comments` | Comments | account_id, post_url, content, status |
| `stores` | Stores | platform, store_url, category |
| `products` | Products | product_name, price, category, rating |
| `ads` | Ads | platform, advertiser, ad_text, engagement |
| `proxies` | Proxies | host, port, username, password, status |

### 7.2 Lead Status Flow

```
new → contacted → qualified → converted
                  → rejected
```

### 7.3 Task Status Flow

```
pending → running → completed
                  → failed
```

### 7.4 Performance Indexes

14 pre-built indexes covering high-frequency queries on leads, tasks, messages, accounts, and products.

---

## 8. Troubleshooting

### 8.1 CORS Error

**Symptom:** `Access to fetch has been blocked by CORS policy`

**Fix:**
1. Confirm backend is running (http://localhost:8000)
2. Check `ALLOWED_ORIGINS` in `.env` includes the frontend URL
3. In dev mode, localhost origins are auto-allowed — restart the backend

### 8.2 Database Connection Failed

**Symptom:** `Connection refused` or `database does not exist`

**Fix:**
1. Confirm PostgreSQL is running
2. Check `DATABASE_URL` in `.env`
3. Run migrations: `psql -U openclaw -d openclaw_db -f database/migrations/init.sql`

### 8.3 AI Features Not Working

**Symptom:** Skill execution or marketing actions return errors

**Fix:**
1. Check `OPENROUTER_API_KEY` in `.env`
2. Verify the key is valid at https://openrouter.ai/keys
3. Check account balance

### 8.4 Scraper Returns No Results

**Symptom:** Deploy Extractor shows empty table

**Fix:**
1. Confirm Chrome is installed
2. Check network (proxy may be needed)
3. Try more specific keywords
4. Configure `CHROME_USER_DATA_DIR` for login sessions

### 8.5 Electron App Won't Start

**Symptom:** App flashes or doesn't respond

**Fix:**
1. Confirm Python is installed and in PATH
2. Confirm `.venv` exists with dependencies installed
3. Run from command line to see errors:
   ```bash
   cd desktop/electron_app
   npm start
   ```

### 8.6 Port Already in Use

```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# macOS/Linux
lsof -i :8000
kill -9 <PID>
```

---

## 9. Security Notes

### Implemented Security Measures

- [x] JWT token authentication
- [x] Password bcrypt hashing
- [x] CORS configuration
- [x] Environment variable secret protection
- [x] Database connection pooling
- [x] Parameterized SQL queries (injection-safe)

### Production Recommendations

1. **Generate a strong JWT key:** `python -c "import secrets; print(secrets.token_urlsafe(32))"`
2. **Disable debug mode:** Set `DEBUG=False` in `.env`
3. **Restrict CORS:** Only allow production domains
4. **Use HTTPS:** Configure SSL certificates
5. **Regular database backups:**
   ```bash
   pg_dump -U openclaw openclaw_db > backup_$(date +%Y%m%d).sql
   ```
6. **Protect `.env`:** Ensure it's in `.gitignore`
7. **Rotate API keys:** Change OpenRouter keys periodically

---

## Quick Reference

| Action | Command |
|--------|---------|
| One-click dev start | `powershell -ExecutionPolicy Bypass -File scripts\dev.ps1` |
| Start backend only | `cd backend && python main.py` |
| Start frontend only | `cd frontend && npm run dev` |
| Build frontend | `cd frontend && npm run build` |
| Build Electron | `cd desktop/electron_app && npm run dist` |
| Database migration | `psql -U openclaw -d openclaw_db -f database/migrations/init.sql` |
| Generate JWT key | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| Health check | `curl http://localhost:8000/health` |
| API docs | Open http://localhost:8000/docs in browser |

---

> **Document Version:** v1.0.0
> **Last Updated:** 2026-05-08
> **App Version:** OpenClaw AI Agent 1.0.0
