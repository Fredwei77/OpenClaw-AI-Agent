# 🤖 AI Agent for Cross-Border E-Commerce

### Automated Multi-Platform Lead Generation System — Save 3 Hours Every Day on Customer Development

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Node Version](https://img.shields.io/badge/Node-18+-green.svg)](https://nodejs.org/)
[![Stars](https://img.shields.io/github/stars/Fredwei77/OpenClaw-AI-Agent?style=social)](https://github.com/Fredwei77/OpenClaw-AI-Agent/stargazers)
[![Forks](https://img.shields.io/github/forks/Fredwei77/OpenClaw-AI-Agent?style=social)](https://github.com/Fredwei77/OpenClaw-AI-Agent/network/members)

> [!TIP]
> **OpenClaw** is a production-ready AI Agent system that automates cross-border e-commerce lead generation and customer outreach — with built-in anti-ban protection so your accounts stay safe.

---

## 🎯 Who is this for?

| You are... | Your pain point | OpenClaw helps by... |
|-----------|----------------|---------------------|
| 🛒 Shopify / Amazon Seller | Expensive traffic, don't know where to find customers | AI discovers qualified leads from X/Twitter/LinkedIn automatically |
| 🌍 B2B Export Sales | Low efficiency in lead development, poor response rates | Personalized AI messages, 24/7 automated outreach |
| 📈 E-commerce Team | Multiple accounts，Easy to be blocked | Isolated browser environments + smart rotation, ban-proof |
| 💰 Indie Hacker / Solopreneur | No time for social media marketing | AI Agent handles content posting and responses automatically |

---

## ⚡ Why OpenClaw?

| Feature | Traditional Approach | OpenClaw |
|---------|---------------------|----------|
| Multi-platform support | Multiple disconnected tools | ✅ One system: X / Twitter / LinkedIn / Facebook |
| Ban prevention | High risk of account bans | ✅ Anti-crawl + multi-account rotation + Rate Limiting |
| Data security | Stored on third-party servers, risky | ✅ Local PostgreSQL, data always under your control |
| AI capabilities | Basic rule-based automation | ✅ GPT-4 / Claude / DeepSeek for intelligent analysis + personalized messages |
| Deployment | Must be cloud-hosted, platform dependent | ✅ Windows local deployment, ready out of the box |
| Pricing | Monthly subscription, ongoing costs | ✅ One-time purchase, lifetime access |

---

## 💼 Real Use Cases

### Use Case 1: Wake Up to 30 High-Quality Leads in Your Database Every Morning

> *"I sell Amazon accessories. Before, I spent 2 hours every day searching for potential customers on LinkedIn. Now this AI Agent automatically saves 30 precision leads to the database by the time I wake up — including company size, contact info, and interaction history."*

### Use Case 2: Running 5 LinkedIn Accounts Simultaneously, Never Banned Again

> *"Before, managing a matrix of 5 accounts meant frequent bans from cross-account association. With OpenClaw's isolated browser environment + residential proxies + intelligent rate limiting, every account behaves like a real user — no more bans."*

### Use Case 3: Real-Time Competitor Monitoring to Catch Sales Opportunities First

> *"After setting up competitor keywords + industry keywords, the AI monitors discussions on X/Twitter/LinkedIn. The moment someone asks 'Does anyone know an alternative to XXX product?', the sales bot instantly triggers a personalized response flow."*

---

## 🏗️ System Architecture

```mermaid
graph LR
    subgraph 🔍 Lead Discovery
        X[X/Twitter] --> L[Lead Agent]
        LinkedIn --> L
        FB[Facebook] --> L
        Google[Google Search] --> L
    end
    
    subgraph 🧠 AI Analysis
        L --> R[Research Agent]
        R --> S[Lead Scoring]
        S --> P[Company Profile]
    end
    
    subgraph 📬 Automated Outreach
        P --> M[Chat Agent]
        M --> Email[Email]
        M --> DM[Direct Message]
        M --> Comment[Comment Engagement]
    end
    
    S --> DB[PostgreSQL<br/>Local Database]
    P --> DB
```

**How it works:**

1. **Lead Agent** automatically discovers potential customers from X/Twitter/LinkedIn/Facebook
2. **Research Agent** analyzes company websites, social profiles, and industry news
3. **AI Scoring** evaluates based on company size, purchase intent, and engagement heat
4. **Chat Agent** sends personalized messages (Email / DM / Comments)
5. All data stored in **your local PostgreSQL** — secure and compliant

---

## 🚀 Quick Start（5 Minutes to Running）

### Step 1: Clone the Project
```bash
git clone https://github.com/Fredwei77/OpenClaw-AI-Agent.git
cd OpenClaw-AI-Agent
```

### Step 2: One-Click Install
```bash
# Windows: double-click
scripts/install.bat

# Or manually
pip install -r requirements.txt
cd frontend && npm install
```

### Step 3: Configure Environment Variables
```bash
cp .env.example .env
# Edit .env and add your API keys
```

```env
OPENROUTER_API_KEY=sk-or-...  # Required for real AI output
OPENROUTER_AUTOMATION_MODEL=qwen/qwen3-30b-a3b-instruct-2507
OPENROUTER_AUTOMATION_FALLBACK_MODELS=google/gemini-2.5-flash,openai/gpt-4o-mini
AUTOMATION_SECRET_KEY=replace-with-a-long-random-secret
DATABASE_URL=postgresql://postgres:password@localhost:5432/openclaw_db
```

### Step 4: Start Services
```bash
# Backend
cd backend && python main.py

# Frontend (new terminal)
cd frontend && npm run dev
```

### Step 5: Open in Browser
- Frontend UI: http://localhost:5173
- API Docs: http://localhost:8000/docs

---

## 📦 Core Modules

| Module | Technology | Description |
|--------|------------|-------------|
| **Lead Agent** | Playwright / Scrapy | Auto-discover qualified customers from X/Twitter/LinkedIn/Facebook |
| **Research Agent** | GPT-4 / Claude / DeepSeek | Analyze company size, industry, purchase intent, generate customer profiles |
| **Chat Agent** | Webhooks + Browser Automation | Personalized automated outreach, 24/7 operation |
| **Anti-Ban Engine** | Residential Proxy + Rate Limiting | Multi-account safe rotation, prevents IP/fingerprint linking |
| **Browser Cluster** | Playwright + Stealth Mode | Isolated browser environments, simulates real user behavior |
| **Local Database** | PostgreSQL | All customer data stored on your own server, GDPR-compliant |

---

## 🤖 AI Lead Automation

The AI Lead Automation workbench turns inbound messages into structured intent analysis and governed replies:

```text
Inbound Webhook -> AI intent/scoring -> Policy checks -> Draft/Review/Automatic
                -> Delivery queue -> Signed outbound Webhook -> Audit and analytics
```

### Capabilities

- **Real AI output:** OpenRouter structured generation with configurable primary and fallback models.
- **Safe fallback:** local deterministic analysis remains available when the provider is disabled or unavailable.
- **Governed replies:** draft, manual review, and automatic modes with confidence thresholds, handoff scores, blocked terms, and hourly limits.
- **Human takeover:** operators can take over or release conversations from the unified inbox.
- **Reliable delivery:** persisted outbound queue with retry backoff, lease recovery, and idempotency keys.
- **Security and audit:** encrypted signing secrets, HMAC-SHA256 callbacks, AI call logs, token/latency metrics, run history, and delivery history.

### Provider Modes

| Mode | Behavior |
|------|----------|
| `local` | Uses local deterministic analysis only |
| `hybrid` | Uses OpenRouter when configured and falls back locally on provider failure |
| `openrouter` | Requires successful OpenRouter structured generation |

### Outbound Webhook Contract

Outbound callbacks include `X-OpenClaw-Timestamp`, `X-OpenClaw-Signature`, and `Idempotency-Key`. Verify the signature as:

```text
HMAC-SHA256(signing_secret, timestamp + "." + raw_request_body)
```

Useful API routes include:

- `PUT /api/automations/settings` - configure provider, reply policy, and outbound Webhook.
- `POST /api/webhooks/simulate` - submit a generic inbound event for local testing.
- `GET /api/automations/ai-calls/recent` - inspect model calls and token/latency data.
- `GET /api/automations/deliveries/recent` - inspect delivery attempts and retry status.
- `POST /api/automations/messages/{message_id}/approve` - approve a reviewed reply.

> [!IMPORTANT]
> The current implementation connects only to generic inbound and outbound Webhooks. No real social media account or platform-specific connector is enabled yet.

---

## 🛡️ Anti-Ban Protection

```mermaid
graph TD
    subgraph Browser Isolation
        B1[Browser 1] --> U1[Isolated Profile]
        B2[Browser 2] --> U2[Isolated Profile]
        B3[Browser 3] --> U3[Isolated Profile]
    end
    
    subgraph IP Rotation
        P1[Residential Proxy 1]
        P2[Residential Proxy 2]
        P3[Residential Proxy 3]
    end
    
    subgraph Rate Limiting
        R1[LinkedIn: 20 msgs/hr]
        R2[Twitter: 50 msgs/hr]
        R3[Facebook: 15 msgs/hr]
    end
    
    U1 --> P1
    U2 --> P2
    U3 --> P3
    P1 --> R1
    P2 --> R2
    P3 --> R3
```

---

## 📅 Roadmap

### ✅ Completed
- [x] Multi-platform Lead Discovery (X / Twitter / LinkedIn / Facebook)
- [x] AI Lead Scoring System (company size + industry + purchase intent)
- [x] Browser Cluster + Anti-Ban Mechanism
- [x] Local PostgreSQL Data Storage
- [x] React Frontend + FastAPI Backend
- [x] Residential Proxy + Multi-Account Rotation
- [x] AI Lead Automation (OpenRouter + local fallback + signed Webhook delivery)

### 🔄 In Development
- [ ] TikTok Auto Lead Generation Module
- [ ] Shopify Data Sync
- [ ] Amazon Review Monitoring + Auto-Reply
- [ ] CRM Integration (HubSpot / Salesforce)

### 📋 Planned
- [ ] AI Sales Agent (Voice Auto-Dial)
- [ ] Video Content Auto-Generation
- [ ] Enterprise Multi-User Permission Management
- [ ] Cloud Sync (Optional)

---

## 🤝 Contributing

PRs are welcome! Here's how to contribute:

```bash
# 1. Fork the repo
# 2. Create a branch
git checkout -b feature/your-feature

# 3. Commit your changes
git commit -m 'Add: some feature'

# 4. Push to your branch
git push origin feature/your-feature

# 5. Open a Pull Request
```

🐛 Found a Bug? → Submit an [Issue](https://github.com/Fredwei77/OpenClaw-AI-Agent/issues)  
💡 Have an Idea? → Submit a [Feature Request](https://github.com/Fredwei77/OpenClaw-AI-Agent/issues/new/choose)

---

## 📊 Project Stats

![Stars](https://img.shields.io/github/stars/Fredwei77/OpenClaw-AI-Agent)
![Forks](https://img.shields.io/github/forks/Fredwei77/OpenClaw-AI-Agent)
![Issues](https://img.shields.io/github/issues/Fredwei77/OpenClaw-AI-Agent)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## 📄 License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for more information.

---

Built with ❤️ by [Fred Wei](https://github.com/Fredwei77)
Questions? → [Open an Issue](https://github.com/Fredwei77/OpenClaw-AI-Agent/issues/new)

支持我
----------
如果您觉得这个项目对您有帮助，您可以扫描以下二维码进行捐赠：
<img width="633" height="795" alt="zhifubao" src="https://github.com/user-attachments/assets/ecae1c5f-b224-49bf-8b91-18241c7fd455" />
