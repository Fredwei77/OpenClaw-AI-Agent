"""
TikTok domain skill for browser-harness.
Provides search and profile extraction capabilities.
"""
import asyncio
import json
import urllib.parse
import logging

from .base_skill import BaseDomainSkill

logger = logging.getLogger(__name__)


class TikTokDomainSkill(BaseDomainSkill):
    platform = "tiktok"

    async def search_users(self, keyword: str, limit: int = 15) -> list[dict]:
        url = f"https://www.tiktok.com/search/user?keyword={urllib.parse.quote(keyword)}"
        await self.hm.navigate(url)
        await self.hm.wait_for_load(timeout=15)
        await asyncio.sleep(3)

        for _ in range(3):
            await self.hm.scroll(dy=-500)
            await asyncio.sleep(1.5)

        raw = await self.hm.execute_js(
            f"""(()=>{{
                const items = document.querySelectorAll('[data-e2e="search-user-item"]');
                return Array.from(items).slice(0, {limit}).map(item => {{
                    const nameEl = item.querySelector('[data-e2e="search-user-name"]');
                    const linkEl = item.querySelector('a');
                    const descEl = item.querySelector('[data-e2e="search-user-desc"]');
                    const href = linkEl ? linkEl.getAttribute('href') : '';
                    const name = nameEl ? nameEl.textContent.trim().replace('@', '') : '';
                    return {{
                        username: name,
                        profile_url: href.startsWith('http') ? href : (href ? 'https://www.tiktok.com' + href : ''),
                        bio: descEl ? descEl.textContent.trim() : ''
                    }};
                }}).filter(l => l.username);
            }})()"""
        )

        return [
            self._make_lead(
                username=item["username"],
                profile_url=item["profile_url"],
                tags=[keyword],
            )
            for item in (raw or [])
        ]

    async def extract_profile(self, username: str) -> dict:
        await self.hm.navigate(f"https://www.tiktok.com/@{username}")
        await self.hm.wait_for_load()
        await asyncio.sleep(3)

        safe_username = json.dumps(username)
        return await self.hm.execute_js(
            f"""(()=>{{
                const stats = document.querySelectorAll('[data-e2e="video-count"], [data-e2e="followers-count"], [data-e2e="likes-count"]');
                const bio = document.querySelector('[data-e2e="user-bio"]');
                const name = document.querySelector('[data-e2e="user-subtitle"]');
                return {{
                    username: {safe_username},
                    display_name: name ? name.textContent.trim() : '',
                    bio: bio ? bio.textContent.trim() : '',
                    stats: Array.from(stats).map(s => s.textContent.trim())
                }};
            }})()"""
        ) or {}

    async def follow_user(self, username: str) -> bool:
        await self.hm.navigate(f"https://www.tiktok.com/@{username}")
        await self.hm.wait_for_load()
        await asyncio.sleep(2)
        return await self.hm.click_element('[data-e2e="follow-button"]', timeout=5)
