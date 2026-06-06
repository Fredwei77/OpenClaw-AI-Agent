# Security Best Practices

## Use Scene
当实现认证、支付或敏感数据处理时调用此技能。

## JWT 安全
```python
# ✅ 正确：完整验证
from jose import jwt
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"

try:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    user_id = payload.get("sub")
except jwt.ExpiredSignatureError:
    raise HTTPException(status_code=401, detail="Token expired")
except jwt.JWTError:
    raise HTTPException(status_code=401, detail="Invalid token")

# ❌ 错误：不验证签名
payload = jwt.decode(token, "any-secret", options={"verify_signature": False})
```

## 密码处理
```python
# ✅ 正确：使用 bcrypt
import bcrypt
salt = bcrypt.gensalt()
hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
is_valid = bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# ❌ 错误：使用简单哈希
import hashlib
hashed = hashlib.sha256(password.encode()).hexdigest()  # 不安全！
```

## 环境变量
```python
# ✅ 正确：从环境变量读取
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL must be set")

# ❌ 错误：硬编码
DATABASE_URL = "postgresql://user:password@localhost/db"  # 危险！
```

## SQL 注入防护
```python
# ✅ 正确：参数化查询
await conn.fetch("SELECT * FROM leads WHERE id = $1", lead_id)
await conn.fetch("SELECT * FROM leads WHERE platform = $1", platform)

# ❌ 错误：字符串拼接
query = f"SELECT * FROM leads WHERE id = {lead_id}"  # SQL 注入风险！
```

## CORS 配置
```python
# ✅ 生产环境：指定具体来源
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourapp.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# ❌ 开发环境外禁止使用 "*"
allow_origins=["*"]  # 只用于开发！
```

## API 密钥保护
```bash
# .gitignore 必须包含
.env
.env.*
!.env.example
*.local
credentials.json
*secret*
*.pem
*.key
```

## 敏感数据日志
```python
# ✅ 正确：日志中隐藏敏感信息
logger.info(f"User {user_id} logged in successfully")
# ❌ 错误：记录密码或 token
logger.info(f"Login attempt for {email} with password {password}")
```

## 输入验证
```python
from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    email: EmailStr  # 自动验证邮箱格式
    password: str = Field(..., min_length=6)  # 最小长度
    role: Literal["user", "moderator"] = "user"
```

## Rate Limiting
```python
# 防止暴力破解
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@router.post("/login")
@limiter.limit("5/minute")  # 每分钟最多 5 次尝试
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    ...
```

## 安全检查清单
- [ ] JWT secret 从环境变量读取
- [ ] 密码使用 bcrypt 哈希
- [ ] SQL 使用参数化查询
- [ ] CORS 配置特定来源
- [ ] 敏感文件在 .gitignore 中
- [ ] 没有硬编码的凭据
- [ ] API 有速率限制
- [ ] 用户输入有验证
