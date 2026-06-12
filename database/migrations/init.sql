-- OpenClaw AI Cross-Border Agent System
-- core 10 tables structure initialization
-- Database: PostgreSQL

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    password_hash TEXT,
    role VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS accounts (
    id SERIAL PRIMARY KEY,
    platform VARCHAR(50),
    username VARCHAR(255),
    password TEXT,
    proxy_id INT,
    status VARCHAR(50),
    risk_score INT DEFAULT 0,
    last_used TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proxies (
    id SERIAL PRIMARY KEY,
    host VARCHAR(255),
    port INT,
    username VARCHAR(255),
    password VARCHAR(255),
    status VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS leads (
    id SERIAL PRIMARY KEY,
    user_id INT,
    platform VARCHAR(50),
    username VARCHAR(255),
    profile_url TEXT,
    email VARCHAR(255),
    followers BIGINT,
    tags TEXT[],
    status VARCHAR(50) DEFAULT 'new',
    metadata JSONB DEFAULT '{}'::jsonb,
    quality_score INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    lead_id INT,
    account_id INT,
    content TEXT,
    status VARCHAR(50),
    sent_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS comments (
    id SERIAL PRIMARY KEY,
    account_id INT,
    post_url TEXT,
    content TEXT,
    status VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stores (
    id SERIAL PRIMARY KEY,
    user_id INT,
    platform VARCHAR(50),
    store_url TEXT,
    category VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    user_id INT,
    store_id INT,
    product_name TEXT,
    price NUMERIC,
    category VARCHAR(255),
    rating NUMERIC,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ads (
    id SERIAL PRIMARY KEY,
    platform VARCHAR(50),
    advertiser TEXT,
    ad_text TEXT,
    engagement INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    user_id INT,
    agent_name VARCHAR(255),
    task_type VARCHAR(255),
    payload JSONB,
    status VARCHAR(50),
    result JSONB,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS marketing_messages (
    id SERIAL PRIMARY KEY,
    lead_id INT,
    user_id INT NOT NULL,
    channel VARCHAR(50) NOT NULL,
    subject TEXT,
    body TEXT NOT NULL,
    cta TEXT,
    sequence_step INT DEFAULT 1,
    status VARCHAR(50) DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS marketing_campaigns (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    product_context TEXT,
    lead_count INT DEFAULT 0,
    generation_mode VARCHAR(50) DEFAULT 'local_fallback',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS automation_flows (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT DEFAULT '',
    trigger_type VARCHAR(100) NOT NULL DEFAULT 'inbound_message',
    trigger_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    definition JSONB NOT NULL DEFAULT '{"steps":[]}'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    lead_id INT,
    channel VARCHAR(50) NOT NULL DEFAULT 'webhook',
    external_id VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    assigned_to INT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_message_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_messages (
    id SERIAL PRIMARY KEY,
    conversation_id INT NOT NULL,
    user_id INT NOT NULL,
    direction VARCHAR(20) NOT NULL,
    message_type VARCHAR(30) NOT NULL DEFAULT 'text',
    content TEXT NOT NULL DEFAULT '',
    status VARCHAR(30) NOT NULL DEFAULT 'received',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS webhook_events (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    event_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    channel VARCHAR(50) NOT NULL DEFAULT 'webhook',
    lead_id INT,
    conversation_id INT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(30) NOT NULL DEFAULT 'received',
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS automation_runs (
    id SERIAL PRIMARY KEY,
    flow_id INT NOT NULL,
    user_id INT NOT NULL,
    event_id INT,
    conversation_id INT,
    lead_id INT,
    status VARCHAR(30) NOT NULL DEFAULT 'running',
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    current_step INT NOT NULL DEFAULT 0,
    error TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS automation_run_steps (
    id SERIAL PRIMARY KEY,
    run_id INT NOT NULL,
    step_index INT NOT NULL,
    step_type VARCHAR(100) NOT NULL,
    status VARCHAR(30) NOT NULL,
    input JSONB NOT NULL DEFAULT '{}'::jsonb,
    output JSONB NOT NULL DEFAULT '{}'::jsonb,
    error TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS automation_jobs (
    id SERIAL PRIMARY KEY,
    run_id INT NOT NULL,
    user_id INT NOT NULL,
    step_index INT NOT NULL,
    execute_at TIMESTAMP NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    attempts INT NOT NULL DEFAULT 0,
    locked_at TIMESTAMP,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_events (
    id SERIAL PRIMARY KEY,
    conversation_id INT NOT NULL,
    user_id INT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    actor_type VARCHAR(30) NOT NULL DEFAULT 'system',
    actor_id INT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS automation_settings (
    user_id INT PRIMARY KEY,
    ai_provider VARCHAR(30) NOT NULL DEFAULT 'hybrid',
    ai_model VARCHAR(255) NOT NULL DEFAULT '',
    reply_mode VARCHAR(30) NOT NULL DEFAULT 'review',
    min_confidence NUMERIC(5,4) NOT NULL DEFAULT 0.65,
    handoff_score INT NOT NULL DEFAULT 85,
    max_auto_replies_per_hour INT NOT NULL DEFAULT 5,
    blocked_terms TEXT[] NOT NULL DEFAULT '{}'::text[],
    outbound_webhook_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    outbound_webhook_url TEXT NOT NULL DEFAULT '',
    outbound_webhook_secret TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS automation_ai_calls (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    run_id INT,
    conversation_id INT,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(255) NOT NULL,
    status VARCHAR(30) NOT NULL,
    prompt_tokens INT NOT NULL DEFAULT 0,
    completion_tokens INT NOT NULL DEFAULT 0,
    latency_ms INT NOT NULL DEFAULT 0,
    output JSONB NOT NULL DEFAULT '{}'::jsonb,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS outbound_deliveries (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    message_id INT NOT NULL,
    callback_url TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    attempts INT NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    locked_at TIMESTAMP,
    response_status INT,
    response_body TEXT,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Upgrade existing local installations created by earlier init.sql versions.
ALTER TABLE leads ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS quality_score INT DEFAULT 0;
ALTER TABLE leads ALTER COLUMN followers TYPE BIGINT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE marketing_messages ADD COLUMN IF NOT EXISTS campaign_id INT;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS mode VARCHAR(20) NOT NULL DEFAULT 'automation';
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS priority VARCHAR(20) NOT NULL DEFAULT 'normal';
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS unread_count INT NOT NULL DEFAULT 0;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS intent VARCHAR(50);
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS intent_confidence NUMERIC(5,4);
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS ai_summary TEXT;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS handoff_reason TEXT;
ALTER TABLE automation_runs ADD COLUMN IF NOT EXISTS parent_run_id INT;
ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS lead_id INT;
ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS conversation_id INT;
ALTER TABLE automation_jobs ADD COLUMN IF NOT EXISTS locked_at TIMESTAMP;

-- =====================================================
-- INDEXES - Performance optimization for production
-- =====================================================

-- Leads table indexes
CREATE INDEX IF NOT EXISTS idx_leads_user_status ON leads(user_id, status);
CREATE INDEX IF NOT EXISTS idx_leads_user_platform ON leads(user_id, platform);
CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_user_platform_username
    ON leads(user_id, platform, username);
CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at DESC);

-- Tasks table indexes
CREATE INDEX IF NOT EXISTS idx_tasks_user_status ON tasks(user_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);

-- Messages table indexes
CREATE INDEX IF NOT EXISTS idx_messages_lead_id ON messages(lead_id);
CREATE INDEX IF NOT EXISTS idx_messages_account_id ON messages(account_id);
CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);

-- Accounts table indexes
CREATE INDEX IF NOT EXISTS idx_accounts_platform_status ON accounts(platform, status);
CREATE INDEX IF NOT EXISTS idx_accounts_risk_score ON accounts(risk_score);

-- Products table indexes
CREATE INDEX IF NOT EXISTS idx_products_user_id ON products(user_id);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_marketing_messages_user_id ON marketing_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_marketing_messages_lead_id ON marketing_messages(lead_id);
CREATE INDEX IF NOT EXISTS idx_marketing_messages_user_status ON marketing_messages(user_id, status);
CREATE INDEX IF NOT EXISTS idx_marketing_messages_campaign_id ON marketing_messages(campaign_id);
CREATE INDEX IF NOT EXISTS idx_marketing_campaigns_user_created_at ON marketing_campaigns(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_automation_flows_user_status ON automation_flows(user_id, status);
CREATE INDEX IF NOT EXISTS idx_conversations_user_updated_at ON conversations(user_id, updated_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_user_channel_external
    ON conversations(user_id, channel, external_id) WHERE external_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_conversation_messages_conversation_created
    ON conversation_messages(conversation_id, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_webhook_events_user_event
    ON webhook_events(user_id, event_id);
CREATE INDEX IF NOT EXISTS idx_automation_runs_user_started ON automation_runs(user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_automation_runs_flow_started ON automation_runs(flow_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_automation_run_steps_run ON automation_run_steps(run_id, step_index);
CREATE INDEX IF NOT EXISTS idx_automation_jobs_due ON automation_jobs(status, execute_at);
CREATE INDEX IF NOT EXISTS idx_conversations_user_mode_updated
    ON conversations(user_id, mode, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversation_events_conversation_created
    ON conversation_events(conversation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_automation_runs_parent ON automation_runs(parent_run_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_automation_jobs_run_step
    ON automation_jobs(run_id, step_index);
CREATE UNIQUE INDEX IF NOT EXISTS idx_automation_messages_run_step
    ON conversation_messages(
        user_id,
        (metadata->>'run_id'),
        (metadata->>'step_index')
    )
    WHERE metadata->>'source' = 'automation'
      AND metadata ? 'run_id'
      AND metadata ? 'step_index';
CREATE UNIQUE INDEX IF NOT EXISTS idx_conversation_events_run_type
    ON conversation_events(user_id, event_type, (payload->>'run_id'))
    WHERE payload ? 'run_id';
CREATE INDEX IF NOT EXISTS idx_automation_ai_calls_user_created
    ON automation_ai_calls(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_outbound_deliveries_due
    ON outbound_deliveries(status, next_attempt_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_outbound_deliveries_message
    ON outbound_deliveries(message_id);
