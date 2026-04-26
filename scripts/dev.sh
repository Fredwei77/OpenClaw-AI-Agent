#!/bin/bash
# OpenClaw AI Agent - 开发环境启动脚本

set -e

echo "🚀 启动 OpenClaw AI Agent 开发环境..."

# 1. 检查 Python 虚拟环境
if [ ! -d ".venv" ]; then
    echo "📦 创建 Python 虚拟环境..."
    python -m venv .venv
fi

# 2. 安装后端依赖
echo "📦 安装后端依赖..."
source .venv/bin/activate
pip install -r backend/requirements.txt 2>/dev/null || pip install fastapi uvicorn asyncpg python-dotenv pydantic bcrypt python-jose playwright playwright-stealth 2>/dev/null

# 3. 安装前端依赖
echo "📦 安装前端依赖..."
cd frontend
npm install 2>/dev/null || echo "跳过 npm install"
cd ..

# 4. 启动后端服务
echo "🚀 启动后端服务 (http://localhost:8000)..."
cd backend
source .venv/bin/activate
python main.py &
BACKEND_PID=$!

# 5. 启动前端开发服务器
echo "🚀 启动前端服务 (http://localhost:5173)..."
cd frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ 服务已启动!"
echo "   后端: http://localhost:8000"
echo "   前端: http://localhost:5173"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待信号
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
