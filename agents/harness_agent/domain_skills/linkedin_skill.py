"""
LinkedIn domain skill for browser-harness.
Provides people search, profile extraction, connect, and messaging.
"""
import asyncio
import json
import urllib.parse
import logging

from .base_skill import BaseDomainSkill

logger = logging.getLogger(__name__)


class LinkedInDomainSkill(BaseDomainSkill):
    platform = "linkedin"

    async def search_users(self, keyword: str, limit: int = 20) -> list[dict]:
        url = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(keyword)}"
        await self.hm.navigate(url)
        await self.hm.wait_for_load(timeout=15)
        await asyncio.sleep(8)  # LinkedIn loads results asynchronously

        # Check login
        page_info = await self.hm.get_page_info()
        if "login" in page_info.get("url", "").lower():
            raise RuntimeError("LinkedIn login required. Log in to Chrome first.")

        for _ in range(5):
            await self.hm.scroll(dy=-500)
            await asyncio.sleep(1.5)

        raw = await self.hm.execute_js(
            f"""(()=>{{
                // Try .entity-result first (old layout)
                let cards = document.querySelectorAll('.entity-result');
                if (cards.length === 0) {{
                    // Fallback: find profile links in search results
                    const main = document.querySelector('main, .scaffold-layout__main, .search-results-container') || document.body;
                    const links = main.querySelectorAll('a[href*="/in/"]');
                    const seen = new Set();
                    const results = [];
                    for (const link of links) {{
                        const href = link.getAttribute('href') || '';
                        if (!href.includes('/in/') || seen.has(href)) continue;
                        seen.add(href);
                        const name = link.innerText.trim().split('\\n')[0].trim();
                        if (name && name.length > 1 && name.length < 60) {{
                            const parent = link.closest('li, .reusable-search__result-container, div') || link.parentElement;
                            const subtitle = parent ? parent.querySelector('.entity-result__primary-subtitle, .subline-level-1, .t-14') : null;
                            results.push({{
                                username: name.toLowerCase().replace(/\\s+/g, '_'),
                                profile_url: href.startsWith('http') ? href : 'https://www.linkedin.com' + href,
                                display_name: name,
                                title: subtitle ? subtitle.innerText.trim() : ''
                            }});
                        }}
                        if (results.length >= {limit}) break;
                    }}
                    return results;
                }}
                // Old layout with .entity-result
                return Array.from(cards).slice(0, {limit}).map(card => {{
                    const titleLink = card.querySelector('.entity-result__title-text a, a[href*="/in/"]');
                    const subtitle = card.querySelector('.entity-result__primary-subtitle');
                    if (!titleLink) return null;
                    const name = titleLink.innerText.trim().split('\\n')[0].trim();
                    const href = titleLink.getAttribute('href') || '';
                    return {{
                        username: name.toLowerCase().replace(/\\s+/g, '_'),
                        profile_url: href.startsWith('http') ? href : 'https://www.linkedin.com' + href,
                        display_name: name,
                        title: subtitle ? subtitle.innerText.trim() : ''
                    }};
                }}).filter(Boolean);
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
        # For LinkedIn, username is usually a profile URL slug
        url = f"https://www.linkedin.com/in/{username}/"
        await self.hm.navigate(url)
        await self.hm.wait_for_load()
        await asyncio.sleep(3)

        safe_username = json.dumps(username)
        return await self.hm.execute_js(
            f"""(()=>{{
                const name = document.querySelector('h1');
                const title = document.querySelector('.text-body-medium.break-words');
                const location = document.querySelector('.text-body-small.inline.t-black--light.break-words');
                return {{
                    username: {safe_username},
                    display_name: name ? name.textContent.trim() : '',
                    title: title ? title.textContent.trim() : '',
                    location: location ? location.textContent.trim() : ''
                }};
            }})()"""
        ) or {}

    async def follow_user(self, username: str) -> bool:
        url = f"https://www.linkedin.com/in/{username}/"
        await self.hm.navigate(url)
        await self.hm.wait_for_load()
        await asyncio.sleep(2)
        return await self.hm.click_element('button[aria-label*="Follow"]', timeout=5)

    async def send_connect(self, profile_url: str, note: str = "") -> bool:
        await self.hm.navigate(profile_url)
        await self.hm.wait_for_load()
        await asyncio.sleep(2)

        clicked = await self.hm.click_element('button[aria-label*="Connect"]', timeout=5)
        if not clicked:
            return False

        await asyncio.sleep(2)

        if note:
            # Add a note to the connection request
            await self.hm.click_element('button[aria-label*="Add a note"]', timeout=3)
            await asyncio.sleep(1)
            await self.hm.fill_input('textarea[name="message"]', note)

        await self.hm.click_element('button[aria-label*="Send"]', timeout=5)
        await asyncio.sleep(1)
        return True

    async def send_message(self, profile_url: str, message: str) -> bool:
        await self.hm.navigate(profile_url)
        await self.hm.wait_for_load()
        await asyncio.sleep(2)

        clicked = await self.hm.click_element('button[aria-label*="Message"]', timeout=5)
        if not clicked:
            return False

        await asyncio.sleep(2)
        await self.hm.fill_input('.msg-form__contenteditable', message)
        await self.hm.press_key("Enter")
        await asyncio.sleep(1)
        return True
