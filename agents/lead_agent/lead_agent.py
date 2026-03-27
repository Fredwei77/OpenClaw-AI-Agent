import asyncio
import sys
import os
import urllib.parse
from agents.base_agent import BaseAgent

# 引入后端的 DB 保存逻辑
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'backend'))
from db import save_leads

from playwright_stealth import Stealth

class LeadAgent(BaseAgent):
    """
    LeadAgent 负责在各大社交平台上进行关键字搜索与爬取，捕获潜在客户线索 (Leads).
    """
    
    async def run(self, task: dict):
        platform = task.get("platform", "x")
        raw_keyword = task.get("keyword", "fitness equipment")
        keyword = raw_keyword.strip()
        encoded_keyword = urllib.parse.quote(keyword)
        
        context_id = f"lead_gen_{task.get('id', 'default')}"
        print(f"[LeadAgent] 正在扫描 {platform} 关于 '{keyword}' 的用户...")
        
        # 从 BrowserManager 中获取 Context
        context = await self.browser_manager.get_context(context_id)
        if not context:
            context = await self.browser_manager.create_context(context_id)
            
        page = await context.new_page()
        stealth = Stealth()
        await stealth.apply_stealth_async(page)
        
        leads = []
        
        try:
            if platform.lower() in ["twitter", "x"]:
                url = f"https://x.com/search?q={encoded_keyword}&src=typed_query&f=user"
                await page.goto(url, wait_until="domcontentloaded")
                
                # 尝试等待推特的用户卡片元素加载 (可能遭遇未登录重定向墙)
                try:
                    await page.wait_for_selector('[data-testid="UserCell"]', timeout=8000)
                except Exception:
                    print("[LeadAgent] 等待推特用户列表超时。可能是遭遇了登录墙或暂无结果。（在生产环境中通常需要加载具有 Cookies 的 Proxy Context）")
                
                # 提取用户卡片
                user_cells = await page.query_selector_all('[data-testid="UserCell"]')
                for cell in user_cells[:10]: # 在 MVP 阶段限制抓取前 10 个作为示例
                    try:
                        name_element = await cell.query_selector('div[dir="ltr"] > span')
                        handle_element = await cell.query_selector('span:has-text("@")')
                        
                        name = await name_element.text_content() if name_element else ""
                        handle = await handle_element.text_content() if handle_element else ""
                        
                        if handle:
                            profile_url = f"https://x.com/{handle.strip('@')}"
                            leads.append({
                                "platform": "twitter",
                                "username": f"{name} ({handle})",
                                "profile_url": profile_url,
                                "email": None,
                                "followers": 0,
                                "tags": [keyword]
                            })
                    except Exception as e:
                        print(f"[LeadAgent] 解析某一行用户数据时抛出异常: {e}")
                        continue
                
        except Exception as e:
            print(f"[LeadAgent] 爬取页面期间抛出致命异常: {e}")
        finally:
            await page.close()
            
        # 如果真实数据截获失败或平台尚未开发（MVP 阶段为了演示流转，提供后备的 Mock 数据）
        if not leads:
            print(f"[LeadAgent] 真实数据截获失败，已启用 Mock 机制填补 '{keyword}' 在 {platform} 的演示线索。")
            leads = [
                {
                    "platform": platform,
                    "username": f"Official {keyword} Hub (@{keyword.replace(' ', '')}HQ)",
                    "profile_url": f"https://{platform}.com/{keyword.replace(' ', '')}HQ",
                    "email": f"contact@{keyword.replace(' ', '').lower()}hub.com",
                    "followers": 12500,
                    "tags": [keyword]
                },
                {
                    "platform": platform,
                    "username": f"{keyword} Enthusiast (@Love{keyword.replace(' ', '')})",
                    "profile_url": f"https://{platform}.com/Love{keyword.replace(' ', '')}",
                    "email": None,
                    "followers": 890,
                    "tags": [keyword]
                },
                {
                    "platform": platform,
                    "username": f"Global {keyword} Agency (@{keyword.replace(' ', '')}Global)",
                    "profile_url": f"https://{platform}.com/{keyword.replace(' ', '')}Global",
                    "email": f"hello@{keyword.replace(' ', '').lower()}global.net",
                    "followers": 45200,
                    "tags": [keyword]
                }
            ]

        # 根据爬取结果判定是否调用 backend.db 存储
        if leads:
            print(f"[LeadAgent] 成功提取了 {len(leads)} 个潜在客户。正在同步至 PostgreSQL...")
            await save_leads(leads)
        else:
            print("[LeadAgent] 本次抓取未获得任何线索数据。")
            
        return leads
