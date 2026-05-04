"""
Harness Social Handler - CDP-based social platform automation.

Provides follow, collect_leads, send_message operations via browser-harness CDP.
Reuses RateLimitConfig from the existing social_handler.
"""
import asyncio
import json
import random
import logging
from typing import Optional, Callable
from datetime import datetime, timedelta
from enum import Enum

from .social_handler import ActionStatus, ActionResult, RateLimitConfig

logger = logging.getLogger(__name__)


class HarnessSocialHandler:
    """
    Social platform automation via browser-harness CDP.

    Unlike the Playwright-based SocialHandler, this operates on the user's
    real Chrome browser, inheriting logged-in sessions.
    """

    def __init__(
        self,
        harness_manager,
        platform: str = "twitter",
        dry_run: bool = False,
    ):
        self.hm = harness_manager
        self.platform = platform.lower()
        self.dry_run = dry_run

        self.min_delay = 2.0
        self.max_delay = 8.0

        self._action_counts: dict[str, list[datetime]] = {}

    async def _random_delay(self, action: str = None):
        delay = random.uniform(self.min_delay, self.max_delay)
        if action == "follow":
            delay += random.uniform(1.0, 3.0)
        elif action == "message":
            delay += random.uniform(2.0, 5.0)
        await asyncio.sleep(delay)

    async def _check_rate_limit(self, action: str) -> bool:
        max_requests, window_seconds = RateLimitConfig.get_limit(self.platform, action)
        now = datetime.now()
        key = f"{self.platform}_{action}"
        cutoff = now - timedelta(seconds=window_seconds)

        if key not in self._action_counts:
            self._action_counts[key] = []

        self._action_counts[key] = [t for t in self._action_counts[key] if t > cutoff]

        if len(self._action_counts[key]) >= max_requests:
            return False

        self._action_counts[key].append(now)
        return True

    async def collect_leads(self, keyword: str, limit: int = 20) -> ActionResult:
        """
        Collect leads from the current platform by searching for keyword.

        Returns ActionResult with leads in data['leads'].
        """
        if not await self._check_rate_limit("search"):
            return ActionResult(
                status=ActionStatus.RATE_LIMITED,
                message=f"Rate limited for {self.platform} search"
            )

        try:
            await self._random_delay("search")

            if self.platform in ("twitter", "x"):
                leads = await self._collect_twitter(keyword, limit)
            elif self.platform == "linkedin":
                leads = await self._collect_linkedin(keyword, limit)
            elif self.platform == "tiktok":
                leads = await self._collect_tiktok(keyword, limit)
            else:
                return ActionResult(
                    status=ActionStatus.FAILED,
                    message=f"Unsupported platform: {self.platform}"
                )

            return ActionResult(
                status=ActionStatus.SUCCESS,
                message=f"Collected {len(leads)} leads",
                data={"leads": leads}
            )

        except Exception as e:
            logger.exception(f"Lead collection failed: {e}")
            return ActionResult(
                status=ActionStatus.FAILED,
                message=f"Collection failed: {str(e)}"
            )

    async def follow_user(self, username: str) -> ActionResult:
        """Follow a user on the current platform."""
        if self.dry_run:
            return ActionResult(status=ActionStatus.SUCCESS, message=f"[DRY RUN] Would follow {username}")

        if not await self._check_rate_limit("follow"):
            return ActionResult(status=ActionStatus.RATE_LIMITED, message="Rate limited")

        try:
            await self._random_delay("follow")

            if self.platform in ("twitter", "x"):
                return await self._follow_twitter(username)
            elif self.platform == "linkedin":
                return await self._follow_linkedin(username)
            elif self.platform == "tiktok":
                return await self._follow_tiktok(username)
            else:
                return ActionResult(status=ActionStatus.FAILED, message=f"Unsupported: {self.platform}")

        except Exception as e:
            return ActionResult(status=ActionStatus.FAILED, message=f"Follow failed: {str(e)}")

    async def send_message(self, username: str, message: str) -> ActionResult:
        """Send a direct message to a user."""
        if self.dry_run:
            return ActionResult(status=ActionStatus.SUCCESS, message=f"[DRY RUN] Would message {username}")

        if not await self._check_rate_limit("message"):
            return ActionResult(status=ActionStatus.RATE_LIMITED, message="Rate limited")

        try:
            await self._random_delay("message")

            if self.platform in ("twitter", "x"):
                return await self._dm_twitter(username, message)
            elif self.platform == "linkedin":
                return await self._dm_linkedin(username, message)
            else:
                return ActionResult(status=ActionStatus.FAILED, message=f"Unsupported: {self.platform}")

        except Exception as e:
            return ActionResult(status=ActionStatus.FAILED, message=f"Message failed: {str(e)}")

    # --- X/Twitter implementations ---

    async def _collect_twitter(self, keyword: str, limit: int) -> list[dict]:
        import urllib.parse
        url = f"https://x.com/search?q={urllib.parse.quote(keyword)}&src=typed_query&f=user"
        await self.hm.navigate(url)
        await self.hm.wait_for_load(timeout=15)
        await asyncio.sleep(8)  # X loads search results asynchronously

        # Scroll to load more results
        for _ in range(5):
            await self.hm.scroll(dy=-800)
            await asyncio.sleep(1.5)

        safe_keyword = json.dumps(keyword)
        leads = await self.hm.execute_js(
            f"""(()=>{{
                const cells = document.querySelectorAll('[data-testid="UserCell"]');
                return Array.from(cells).slice(0, {limit}).map(cell => {{
                    const link = cell.querySelector('a[role="link"]');
                    const nameEl = cell.querySelector('[data-testid="User-Name"]');
                    const bioEl = cell.querySelector('[data-testid="UserDescription"]');
                    const href = link ? link.getAttribute('href') : '';
                    return {{
                        platform: 'x',
                        username: href ? href.replace('/', '') : '',
                        profile_url: href ? 'https://x.com' + href : '',
                        email: null,
                        followers: 0,
                        tags: [{safe_keyword}],
                        bio: bioEl ? bioEl.innerText.trim() : ''
                    }};
                }}).filter(l => l.username);
            }})()"""
        )

        return leads or []

    async def _follow_twitter(self, username: str) -> ActionResult:
        await self.hm.navigate(f"https://x.com/{username}")
        await self.hm.wait_for_load()
        await asyncio.sleep(2)

        clicked = await self.hm.click_element('[data-testid$="-follow"]', timeout=5)
        if clicked:
            return ActionResult(status=ActionStatus.SUCCESS, message=f"Followed @{username}")
        return ActionResult(status=ActionStatus.FAILED, message="Follow button not found")

    async def _dm_twitter(self, username: str, message: str) -> ActionResult:
        await self.hm.navigate(f"https://x.com/messages/compose?recipient={username}")
        await self.hm.wait_for_load()
        await asyncio.sleep(3)

        filled = await self.hm.fill_input('[data-testid="dmConversationTextInput"]', message)
        if not filled:
            return ActionResult(status=ActionStatus.FAILED, message="DM input not found")

        await self.hm.press_key("Enter")
        await asyncio.sleep(1)
        return ActionResult(status=ActionStatus.SUCCESS, message=f"Sent DM to @{username}")

    # --- LinkedIn implementations ---

    async def _collect_linkedin(self, keyword: str, limit: int) -> list[dict]:
        import urllib.parse
        url = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(keyword)}"
        await self.hm.navigate(url)
        await self.hm.wait_for_load(timeout=15)
        await asyncio.sleep(8)  # LinkedIn loads results asynchronously

        # Check if login required
        page_info = await self.hm.get_page_info()
        if "login" in page_info.get("url", "").lower():
            raise RuntimeError("LinkedIn login required. Please log in to Chrome first.")

        for _ in range(5):
            await self.hm.scroll(dy=-500)
            await asyncio.sleep(1.5)

        safe_keyword = json.dumps(keyword)
        leads = await self.hm.execute_js(
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
                                platform: 'linkedin',
                                username: name.toLowerCase().replace(/\\s+/g, '_'),
                                profile_url: href.startsWith('http') ? href : 'https://www.linkedin.com' + href,
                                email: null,
                                followers: 0,
                                tags: [{safe_keyword}],
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
                        platform: 'linkedin',
                        username: name.toLowerCase().replace(/\\s+/g, '_'),
                        profile_url: href.startsWith('http') ? href : 'https://www.linkedin.com' + href,
                        email: null,
                        followers: 0,
                        tags: [{safe_keyword}],
                        title: subtitle ? subtitle.innerText.trim() : ''
                    }};
                }}).filter(Boolean);
            }})()"""
        )

        return leads or []

    async def _follow_linkedin(self, username: str) -> ActionResult:
        return ActionResult(status=ActionStatus.FAILED, message="LinkedIn follow not supported. Use connect instead.")

    async def _dm_linkedin(self, profile_url: str, message: str) -> ActionResult:
        await self.hm.navigate(profile_url)
        await self.hm.wait_for_load()
        await asyncio.sleep(2)

        clicked = await self.hm.click_element('button[aria-label*="Message"]', timeout=5)
        if not clicked:
            return ActionResult(status=ActionStatus.FAILED, message="Message button not found")

        await asyncio.sleep(2)
        await self.hm.fill_input('.msg-form__contenteditable', message)
        await self.hm.press_key("Enter")
        await asyncio.sleep(1)
        return ActionResult(status=ActionStatus.SUCCESS, message="Message sent")

    # --- TikTok implementations ---

    async def _collect_tiktok(self, keyword: str, limit: int) -> list[dict]:
        import urllib.parse
        url = f"https://www.tiktok.com/search/user?keyword={urllib.parse.quote(keyword)}"
        await self.hm.navigate(url)
        await self.hm.wait_for_load(timeout=15)
        await asyncio.sleep(3)

        for _ in range(3):
            await self.hm.scroll(dy=-500)
            await asyncio.sleep(1)

        safe_keyword = json.dumps(keyword)
        leads = await self.hm.execute_js(
            f"""(()=>{{
                const items = document.querySelectorAll('[data-e2e="search-user-item"]');
                return Array.from(items).slice(0, {limit}).map(item => {{
                    const nameEl = item.querySelector('[data-e2e="search-user-name"]');
                    const linkEl = item.querySelector('a');
                    const href = linkEl ? linkEl.getAttribute('href') : '';
                    return {{
                        platform: 'tiktok',
                        username: nameEl ? nameEl.textContent.trim().replace('@', '') : '',
                        profile_url: href.startsWith('http') ? href : (href ? 'https://www.tiktok.com' + href : ''),
                        email: null,
                        followers: 0,
                        tags: [{safe_keyword}]
                    }};
                }}).filter(l => l.username);
            }})()"""
        )

        return leads or []

    async def _follow_tiktok(self, username: str) -> ActionResult:
        await self.hm.navigate(f"https://www.tiktok.com/@{username}")
        await self.hm.wait_for_load()
        await asyncio.sleep(2)

        clicked = await self.hm.click_element('[data-e2e="follow-button"]', timeout=5)
        if clicked:
            return ActionResult(status=ActionStatus.SUCCESS, message=f"Followed @{username}")
        return ActionResult(status=ActionStatus.FAILED, message="Follow button not found")
