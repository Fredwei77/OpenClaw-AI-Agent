"""
X/Twitter domain skill for browser-harness.
Provides search, profile extraction, follow, and DM capabilities.
"""
import asyncio
import json
import urllib.parse
import logging

from .base_skill import BaseDomainSkill

logger = logging.getLogger(__name__)


class XDomainSkill(BaseDomainSkill):
    platform = "x"

    async def search_users(self, keyword: str, limit: int = 20) -> list[dict]:
        url = f"https://x.com/search?q={urllib.parse.quote(keyword)}&src=typed_query&f=user"
        await self.hm.navigate(url)
        await self.hm.wait_for_load(timeout=15)
        await asyncio.sleep(8)  # X loads search results asynchronously

        # Scroll to load more
        for _ in range(5):
            await self.hm.scroll(dy=-800)
            await asyncio.sleep(1.5)

        raw = await self.hm.execute_js(
            f"""(()=>{{
                const cells = document.querySelectorAll('[data-testid="UserCell"]');
                return Array.from(cells).slice(0, {limit}).map(cell => {{
                    const link = cell.querySelector('a[role="link"]');
                    const nameEl = cell.querySelector('[data-testid="User-Name"]');
                    const bioEl = cell.querySelector('[data-testid="UserDescription"]');
                    const href = link ? link.getAttribute('href') : '';
                    return {{
                        username: href ? href.replace('/', '') : '',
                        profile_url: href ? 'https://x.com' + href : '',
                        display_name: nameEl ? nameEl.innerText.trim().split('\\n')[0] : '',
                        bio: bioEl ? bioEl.innerText.trim() : ''
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
        await self.hm.navigate(f"https://x.com/{username}")
        await self.hm.wait_for_load()
        await asyncio.sleep(4)

        safe_username = json.dumps(username)
        return await self.hm.execute_js(
            f"""(()=>{{
                const name = document.querySelector('[data-testid="UserName"]');
                const bio = document.querySelector('[data-testid="UserDescription"]');
                const followers = document.querySelector('a[href*="followers"]');
                const location = document.querySelector('[data-testid="UserLocation"]');
                return {{
                    username: {safe_username},
                    display_name: name ? name.innerText.trim().split('\\n')[0] : '',
                    bio: bio ? bio.innerText.trim() : '',
                    followers_text: followers ? followers.innerText.trim() : '0',
                    location: location ? location.innerText.trim() : ''
                }};
            }})()"""
        ) or {}

    async def follow_user(self, username: str) -> bool:
        await self.hm.navigate(f"https://x.com/{username}")
        await self.hm.wait_for_load()
        await asyncio.sleep(2)
        return await self.hm.click_element('[data-testid$="-follow"]', timeout=5)

    async def send_message(self, username: str, message: str) -> bool:
        await self.hm.navigate(f"https://x.com/messages/compose?recipient={username}")
        await self.hm.wait_for_load()
        await asyncio.sleep(3)

        if not await self.hm.fill_input('[data-testid="dmConversationTextInput"]', message):
            return False
        await self.hm.press_key("Enter")
        await asyncio.sleep(1)
        return True
