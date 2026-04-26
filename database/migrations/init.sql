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
    followers INT,
    tags TEXT[],
    status VARCHAR(50) DEFAULT 'new',
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
    rating NUMERIC
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

-- =====================================================
-- INDEXES - Performance optimization for production
-- =====================================================

-- Leads table indexes
CREATE INDEX IF NOT EXISTS idx_leads_user_status ON leads(user_id, status);
CREATE INDEX IF NOT EXISTS idx_leads_user_platform ON leads(user_id, platform);
CREATE INDEX IF NOT EXISTS idx_leads_platform_username ON leads(platform, username);
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
