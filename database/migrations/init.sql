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

-- Upgrade existing local installations created by earlier init.sql versions.
ALTER TABLE leads ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS quality_score INT DEFAULT 0;
ALTER TABLE leads ALTER COLUMN followers TYPE BIGINT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE marketing_messages ADD COLUMN IF NOT EXISTS campaign_id INT;

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
