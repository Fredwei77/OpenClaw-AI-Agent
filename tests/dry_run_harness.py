"""
Dry-run test for browser-harness integration.
Connects to Chrome via CDP on port 9222 and tests scraping on X, LinkedIn, TikTok.
"""
import asyncio
import json
import sys
import os
import time

# Clean proxy settings to allow localhost websocket connections
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(k, None)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CDP_URL = "http://127.0.0.1:9222"


async def get_page_targets():
    """Get all page-type targets."""
    import urllib.request
    try:
        resp = urllib.request.urlopen(f"{CDP_URL}/json/list", timeout=3)
        data = json.loads(resp.read())
        resp.close()
        return [t for t in data if t.get("type") == "page"]
    except Exception as e:
        print(f"[ERROR] Cannot list targets: {e}")
        return []


async def cdp_eval(ws, expression):
    """Evaluate JS expression via CDP and return the result value."""
    cmd_id = int(time.time() * 1000) % 100000
    msg = json.dumps({
        "id": cmd_id,
        "method": "Runtime.evaluate",
        "params": {"expression": expression, "returnByValue": True, "awaitPromise": True}
    })
    await ws.send(msg)
    while True:
        resp = json.loads(await ws.recv())
        if resp.get("id") == cmd_id:
            result = resp.get("result", {}).get("result", {})
            if result.get("type") == "undefined":
                return None
            return result.get("value")


async def cdp_navigate(ws, url):
    """Navigate to URL and wait for load."""
    cmd_id = int(time.time() * 1000) % 100000 + 1
    msg = json.dumps({"id": cmd_id, "method": "Page.navigate", "params": {"url": url}})
    await ws.send(msg)
    while True:
        resp = json.loads(await ws.recv())
        if resp.get("id") == cmd_id:
            return resp


async def test_x_profile(ws):
    """Test X profile extraction on the logged-in user's own profile."""
    print("\n" + "=" * 60)
    print("[TEST] X/Twitter - Extract Profile (current user)")
    print("=" * 60)

    # Go to home to find profile link
    await cdp_navigate(ws, "https://x.com/home")
    await asyncio.sleep(4)

    # Find profile link in sidebar
    profile_link = await cdp_eval(ws,
        'document.querySelector("[data-testid=AppTabBar_Profile_Link]")?.getAttribute("href")'
    )

    if not profile_link:
        print("[WARN] Not logged into X or profile link not found.")
        return {}

    username = profile_link.strip("/")
    print(f"[INFO] Logged in as: @{username}")

    # Navigate to profile page
    await cdp_navigate(ws, f"https://x.com/{username}")
    await asyncio.sleep(5)

    # Scroll to trigger lazy loading
    for _ in range(2):
        await cdp_eval(ws, "window.scrollBy(0, 300)")
        await asyncio.sleep(1)

    safe_username = json.dumps(username)
    profile = await cdp_eval(ws, f"""(() => {{
        const name = document.querySelector('[data-testid="UserName"]');
        const bio = document.querySelector('[data-testid="UserDescription"]');
        const followers = document.querySelector('a[href*="followers"]');
        const location = document.querySelector('[data-testid="UserLocation"]');
        const joinDate = document.querySelector('[data-testid="UserJoinDate"]');
        return {{
            username: {safe_username},
            display_name: name ? name.innerText.trim().split('\\n')[0] : '',
            bio: bio ? bio.innerText.trim() : '',
            followers_text: followers ? followers.innerText.trim() : '0',
            location: location ? location.innerText.trim() : '',
            join_date: joinDate ? joinDate.innerText.trim() : ''
        }};
    }})()""")

    if profile and profile.get("display_name"):
        print(f"[SUCCESS] Profile extracted:")
        print(f"  Username:  @{profile.get('username', '?')}")
        print(f"  Name:      {profile.get('display_name', '?')}")
        print(f"  Bio:       {profile.get('bio', '')[:100]}")
        print(f"  Followers: {profile.get('followers_text', '?')}")
        print(f"  Location:  {profile.get('location', '?')}")
        print(f"  Joined:    {profile.get('join_date', '?')}")
        return profile

    print("[WARN] Could not extract profile data.")
    return {}


async def test_x_scrape(ws):
    """Test X/Twitter user search scraping."""
    print("\n" + "=" * 60)
    print("[TEST] X/Twitter - Search Users for 'dropshipping'")
    print("=" * 60)

    keyword = "dropshipping"
    import urllib.parse
    url = f"https://x.com/search?q={urllib.parse.quote(keyword)}&src=typed_query&f=user"
    print(f"[INFO] Navigating to: {url}")

    await cdp_navigate(ws, url)
    await asyncio.sleep(8)  # X loads search results asynchronously

    # Scroll to load more results
    for _ in range(5):
        await cdp_eval(ws, "window.scrollBy(0, 800)")
        await asyncio.sleep(1.5)

    safe_keyword = json.dumps(keyword)
    results = await cdp_eval(ws, f"""(() => {{
        const cells = document.querySelectorAll('[data-testid="UserCell"]');
        return Array.from(cells).slice(0, 10).map(cell => {{
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
    }})()""")

    if results:
        print(f"\n[SUCCESS] Found {len(results)} users:")
        for i, user in enumerate(results[:10], 1):
            print(f"  {i}. @{user.get('username', '?')} - {user.get('display_name', '?')}")
            bio = user.get('bio', '')
            if bio:
                print(f"     Bio: {bio[:80]}...")
    else:
        print("[WARN] No results found.")

    return results or []


async def test_linkedin_profile(ws):
    """Test LinkedIn profile extraction."""
    print("\n" + "=" * 60)
    print("[TEST] LinkedIn - Extract Profile (current user)")
    print("=" * 60)

    # Navigate to feed to check login and find profile link
    await cdp_navigate(ws, "https://www.linkedin.com/feed/")
    await asyncio.sleep(5)

    current_url = await cdp_eval(ws, "window.location.href")
    if "login" in (current_url or "").lower():
        print("[WARN] Not logged into LinkedIn. Skipping.")
        return {}

    # Find profile link from the nav
    profile_url = await cdp_eval(ws, """(() => {
        const links = document.querySelectorAll('a[href*="/in/"]');
        for (const link of links) {
            const href = link.getAttribute('href') || '';
            if (href.includes('/in/') && !href.includes('miniProfile')) {
                return href.startsWith('http') ? href : 'https://www.linkedin.com' + href;
            }
        }
        return '';
    })()""")

    if not profile_url:
        print("[WARN] Could not find profile link on LinkedIn.")
        return {}

    print(f"[INFO] Profile URL: {profile_url}")

    # Navigate to profile
    await cdp_navigate(ws, profile_url)
    await asyncio.sleep(5)

    # Scroll to load content
    for _ in range(3):
        await cdp_eval(ws, "window.scrollBy(0, 300)")
        await asyncio.sleep(1)

    profile = await cdp_eval(ws, """(() => {
        const name = document.querySelector('h1');
        const title = document.querySelector('.text-body-medium.break-words');
        const location = document.querySelector('.text-body-small.inline.t-black--light.break-words');
        return {
            display_name: name ? name.innerText.trim() : '',
            title: title ? title.innerText.trim() : '',
            location: location ? location.innerText.trim() : ''
        };
    })()""")

    if profile and profile.get("display_name"):
        print(f"[SUCCESS] LinkedIn profile extracted:")
        print(f"  Name:     {profile.get('display_name', '?')}")
        print(f"  Title:    {profile.get('title', '?')[:100]}")
        print(f"  Location: {profile.get('location', '?')}")
        return profile

    print("[WARN] Could not extract LinkedIn profile.")
    return {}


async def test_linkedin_scrape(ws):
    """Test LinkedIn people search scraping."""
    print("\n" + "=" * 60)
    print("[TEST] LinkedIn - Search People for 'ecommerce'")
    print("=" * 60)

    keyword = "ecommerce"
    import urllib.parse
    url = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(keyword)}"
    print(f"[INFO] Navigating to: {url}")

    await cdp_navigate(ws, url)
    await asyncio.sleep(8)

    # Check login
    current_url = await cdp_eval(ws, "window.location.href")
    if "login" in (current_url or "").lower():
        print("[WARN] Redirected to login page.")
        return []

    # Scroll to load more
    for _ in range(5):
        await cdp_eval(ws, "window.scrollBy(0, 500)")
        await asyncio.sleep(1.5)

    # Try multiple selectors for LinkedIn search results
    results = await cdp_eval(ws, """(() => {
        // Try .entity-result first (old layout)
        let cards = document.querySelectorAll('.entity-result');
        if (cards.length === 0) {
            // Fallback: find all profile links in search results
            const main = document.querySelector('main, .scaffold-layout__main, .search-results-container') || document.body;
            const links = main.querySelectorAll('a[href*="/in/"]');
            const seen = new Set();
            const results = [];
            for (const link of links) {
                const href = link.getAttribute('href') || '';
                if (!href.includes('/in/') || seen.has(href)) continue;
                seen.add(href);
                const name = link.innerText.trim().split('\\n')[0].trim();
                if (name && name.length > 1 && name.length < 60) {
                    const parent = link.closest('li, .reusable-search__result-container, div') || link.parentElement;
                    const subtitle = parent ? parent.querySelector('.entity-result__primary-subtitle, .subline-level-1, .t-14') : null;
                    results.push({
                        username: name.toLowerCase().replace(/\\s+/g, '_'),
                        profile_url: href.startsWith('http') ? href : 'https://www.linkedin.com' + href,
                        display_name: name,
                        title: subtitle ? subtitle.innerText.trim() : ''
                    });
                }
                if (results.length >= 10) break;
            }
            return results;
        }
        // Old layout with .entity-result
        return Array.from(cards).slice(0, 10).map(card => {
            const titleLink = card.querySelector('.entity-result__title-text a, a[href*="/in/"]');
            const subtitle = card.querySelector('.entity-result__primary-subtitle');
            if (!titleLink) return null;
            const name = titleLink.innerText.trim().split('\\n')[0].trim();
            const href = titleLink.getAttribute('href') || '';
            return {
                username: name.toLowerCase().replace(/\\s+/g, '_'),
                profile_url: href.startsWith('http') ? href : 'https://www.linkedin.com' + href,
                display_name: name,
                title: subtitle ? subtitle.innerText.trim() : ''
            };
        }).filter(Boolean);
    })()""")

    if results:
        print(f"\n[SUCCESS] Found {len(results)} people:")
        for i, person in enumerate(results[:10], 1):
            print(f"  {i}. {person.get('display_name', '?')} (@{person.get('username', '?')})")
            title = person.get('title', '')
            if title:
                print(f"     Title: {title[:80]}...")
    else:
        print("[WARN] No results found.")

    return results or []


async def main():
    print("=" * 60)
    print("  OpenClaw Browser-Harness Dry-Run Test")
    print("  Chrome CDP: 127.0.0.1:9222")
    print("=" * 60)

    # Check CDP connection
    import urllib.request
    try:
        resp = urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=3)
        data = json.loads(resp.read())
        resp.close()
        print(f"\n[OK] Chrome connected: {data.get('Browser', '?')}")
    except Exception as e:
        print(f"\n[FATAL] Cannot connect to Chrome debug port 9222: {e}")
        return

    try:
        import websockets
    except ImportError:
        print("[FATAL] websockets package not installed. Run: pip install websockets")
        return

    # List tabs
    print("\n[INFO] Open tabs:")
    pages = await get_page_targets()
    for p in pages:
        print(f"  - {p['title'][:50]} ({p['url'][:60]})")

    x_tab = next((p for p in pages if "x.com" in p.get("url", "") or "twitter.com" in p.get("url", "")), None)
    li_tab = next((p for p in pages if "linkedin.com" in p.get("url", "")), None)

    results = {}

    # Test X
    if x_tab:
        print(f"\n[3/6] Connecting to X tab...")
        try:
            async with websockets.connect(x_tab["webSocketDebuggerUrl"], max_size=10 * 1024 * 1024) as ws:
                await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
                await ws.recv()
                await ws.send(json.dumps({"id": 2, "method": "Page.enable"}))
                await ws.recv()

                results["x_profile"] = await test_x_profile(ws)
                results["x_scrape"] = await test_x_scrape(ws)
        except Exception as e:
            print(f"[ERROR] X test failed: {e}")
    else:
        print("\n[3/6] [SKIP] No X/Twitter tab found")

    # Test LinkedIn
    if li_tab:
        print(f"\n[4/6] Connecting to LinkedIn tab...")
        try:
            async with websockets.connect(li_tab["webSocketDebuggerUrl"], max_size=10 * 1024 * 1024) as ws:
                await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
                await ws.recv()
                await ws.send(json.dumps({"id": 2, "method": "Page.enable"}))
                await ws.recv()

                results["li_profile"] = await test_linkedin_profile(ws)
                results["li_scrape"] = await test_linkedin_scrape(ws)
        except Exception as e:
            print(f"[ERROR] LinkedIn test failed: {e}")
    else:
        print("\n[4/6] [SKIP] No LinkedIn tab found")

    # Summary
    print("\n" + "=" * 60)
    print("  DRY-RUN SUMMARY")
    print("=" * 60)

    total_leads = 0
    for key, data in results.items():
        if isinstance(data, list):
            count = len(data)
            total_leads += count
            print(f"  {key}: {count} results")
        elif isinstance(data, dict) and data:
            print(f"  {key}: OK (extracted)")
        else:
            print(f"  {key}: No data")

    print(f"\n  Total leads found: {total_leads}")
    print(f"  Mode: DRY RUN (no data saved to database)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
