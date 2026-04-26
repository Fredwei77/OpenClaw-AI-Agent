# Docker & DevOps Assistant

## Use Scene
当需要部署或设置 CI/CD 流水线时使用此子代理。

## 职责

### 1. Dockerfile 生成
**Backend (FastAPI)**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY backend/ .
COPY agents/ .
COPY browser_cluster/ .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Frontend (React)**
```dockerfile
FROM node:18-alpine AS builder

WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### 2. docker-compose.yml
```yaml
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:openclaw@postgres:5432/openclaw_db
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - ENVIRONMENT=production
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  frontend:
    build:
      context: .
      dockerfile: frontend/Dockerfile
    ports:
      - "5173:80"
    depends_on:
      - backend
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: openclaw_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: openclaw
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

### 3. 健康检查端点
```python
@app.get("/health")
async def health_check():
    """Kubernetes/ Docker 健康检查"""
    try:
        # 检查数据库连接
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "production"),
        "checks": {
            "database": db_status
        }
    }
```

### 4. CI/CD GitHub Actions
```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r backend/requirements.txt
          pip install pytest pytest-asyncio

      - name: Run tests
        run: pytest backend/tests/ -v

      - name: Lint
        run: |
          cd backend
          black --check .
          ruff check .

  build-and-deploy:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker images
        run: |
          docker-compose build

      - name: Push to registry
        run: |
          echo "${{ secrets.DOCKER_TOKEN }}" | docker login
          docker push your-registry/openclaw-backend:latest
```

### 5. 环境变量验证
```python
# 启动时验证必需环境变量
REQUIRED_ENV_VARS = [
    "DATABASE_URL",
    "JWT_SECRET_KEY"
]

def validate_environment():
    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing:
        raise ValueError(f"Missing required env vars: {', '.join(missing)}")
```

## 检查清单
- [ ] Dockerfile 存在且可构建
- [ ] docker-compose.yml 配置完整
- [ ] 健康检查端点返回正确状态
- [ ] 所有环境变量有文档
- [ ] 数据库连接使用池化
- [ ] 没有硬编码的敏感信息
- [ ] CI/CD 流水线配置正确
