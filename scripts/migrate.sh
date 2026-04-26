#!/bin/bash
# OpenClaw AI Agent - 数据库迁移脚本

set -e

DATABASE_URL="${DATABASE_URL:-postgresql://postgres:openclaw@localhost:5432/openclaw_db}"

echo "🗄️  执行数据库迁移..."

# 运行 SQL 迁移文件
psql "$DATABASE_URL" -f database/migrations/init.sql

echo "✅ 数据库迁移完成!"
echo ""
echo "已创建的表:"
echo "  - users"
echo "  - accounts"
echo "  - proxies"
echo "  - leads"
echo "  - messages"
echo "  - comments"
echo "  - stores"
echo "  - products"
echo "  - ads"
echo "  - tasks"
echo ""
echo "已创建的索引:"
echo "  - idx_leads_user_status"
echo "  - idx_leads_platform_username"
echo "  - idx_tasks_user_status"
echo "  - idx_tasks_status"
echo "  - idx_messages_lead_id"
echo "  - ..."

# 可选：添加示例数据
# if [ "$1" == "--with-seed" ]; then
#     echo "📦 添加示例数据..."
#     psql "$DATABASE_URL" -f database/migrations/seed.sql
# fi
