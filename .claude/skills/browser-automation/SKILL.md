# Browser Automation Best Practices

## Use Scene
当实现或调试浏览器爬虫 agent 时调用此技能。

## 上下文管理
```python
# 每个账户/会话必须使用独立的 context
context_id = f"linkedin_{user_id}_{timestamp}"
context = await browser_manager.get_or_create_context(context_id)

# 始终使用 stealth 模式
from playwright_stealth import Stealth
stealth = Stealth()
await stealth.apply_stealth_async(page)
```

## 速率限制
```python
# LinkedIn: 20 requests/hour (严格)
# Facebook: 15 requests/hour
# Twitter/X: 30 requests/hour
# Instagram: 20 requests/hour

# 使用任务队列的速率限制器
await rate_limiter.acquire()  # 超过限制时阻塞
```

## 代理配置
```python
# 代理格式：http://user:pass@host:port
proxy_config = {
    "server": proxy_url,
    "username": proxy_user,
    "password": proxy_pass
}

context = await browser.new_context(
    proxy={"server": proxy_url, "username": proxy_user, "password": proxy_pass}
)
```

## 错误处理
```python
try:
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
except TimeoutError:
    # 降级到模拟数据用于演示
    return await self._get_mock_leads(keyword, limit)
except Exception as e:
    logger.error(f"Navigation failed: {e}")
    return []
```

## 资源清理
```python
# ✅ 正确：使用 try/finally 确保清理
try:
    page = await context.new_page()
    await stealth.apply_stealth_async(page)
    # ... 执行爬取 ...
finally:
    await page.close()  # 始终关闭页面
    # Context 应该复用，不要每次创建/关闭

# ❌ 错误：在请求内启动/关闭浏览器
manager = BrowserManager()
await manager.start()  # 耗时 3-8 秒！
# ... 爬取 ...
await manager.close()  # 请求结束后关闭
```

## 页面选择器
```python
# Twitter/X 用户卡片
'[data-testid="UserCell"]'

# LinkedIn 搜索结果
'.entity-result', '.search-result__occluded-item'

# Facebook 用户卡片
'[data-pagelet="ProfileTimeline"]'

# 等待元素加载
await page.wait_for_selector('[data-testid="UserCell"]', timeout=8000)
```

## 隐私模式
```python
# 使用常驻上下文而非隐私模式
# 隐私模式每次都是全新的浏览器环境，无法保持登录态
context = await browser_manager.get_or_create_context(context_id)

# 如果需要测试无痕模式
context = await browser.new_context(
    accept_downloads=True,
    ignore_https_errors=True,
    base_url="https://www.linkedin.com"
)
```

## 浏览器引擎选择
| 平台 | 推荐引擎 | 原因 |
|------|---------|------|
| Twitter/X | Chromium | stealth 模式支持最好 |
| LinkedIn | Chromium | 需要登录态，Chromium 最稳定 |
| Facebook | Chromium | GraphQL API 可通过 CDP 访问 |
| Instagram | Chromium | 移动视图切换方便 |

## 防封策略
1. **随机化请求间隔**：每次请求后等待 2-5 秒随机时间
2. **代理轮换**：每个账户使用不同代理
3. **Profile 轮换**：不同账户使用不同的 Chrome Profile
4. **行为模拟**：随机滚动、鼠标移动
5. **请求头随机化**：使用 stealth 插件
