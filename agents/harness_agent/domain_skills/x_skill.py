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
        username = username.strip().lstrip("@")
        if not username or not message.strip():
            raise ValueError("X handle and message are required")

        await self.hm.navigate(f"https://x.com/{urllib.parse.quote(username, safe='')}")
        await self.hm.wait_for_load()
        await asyncio.sleep(3)

        page_info = await self.hm.get_page_info()
        current_url = str((page_info or {}).get("url") or "")
        if "/login" in current_url or "/i/flow/login" in current_url:
            raise RuntimeError("X session is not logged in")

        opened = False
        for selector in (
            '[data-testid="sendDMFromProfile"]',
            'a[href*="/messages/compose"]',
            'button[aria-label*="Message"]',
        ):
            if await self.hm.click_element(selector, timeout=3):
                opened = True
                break
        if not opened:
            raise RuntimeError("X direct-message button was not found; the recipient may not accept DMs")

        input_selector = '[data-testid="dmConversationTextInput"]'
        if not await self.hm.wait_for_element(input_selector, timeout=10, visible=True):
            raise RuntimeError("X message composer did not open")
        if not await self.hm.fill_input(input_selector, message):
            raise RuntimeError("Could not fill the X message composer")

        if not await self.hm.click_element('[data-testid="dmComposerSendButton"]', timeout=5):
            raise RuntimeError("X send button was not available")
        await asyncio.sleep(2)

        submitted = await self.hm.execute_js(
            "(()=>{const e=document.querySelector('[data-testid=\"dmConversationTextInput\"]');"
            "return !!e && !(e.innerText||e.textContent||'').trim()})()"
        )
        if not submitted:
            raise RuntimeError("X did not confirm that the message was submitted")
        return True
