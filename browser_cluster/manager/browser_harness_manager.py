"""
Browser Harness Manager - CDP-based browser automation via browser-harness.

Wraps the browser-harness daemon IPC protocol to provide an async interface
for OpenClaw agents. Connects to the user's real Chrome browser via CDP.
"""
import asyncio
import json
import logging
import os
import sys
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Add browser-harness source to path
_BH_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "vendor", "browser-harness", "src")
if os.path.isdir(_BH_SRC):
    sys.path.insert(0, _BH_SRC)

try:
    from browser_harness import _ipc as ipc
    from browser_harness import helpers as bh
    BH_AVAILABLE = True
except ImportError:
    BH_AVAILABLE = False
    logger.warning("browser-harness not available. Install from: https://github.com/browser-use/browser-harness")


class BrowserHarnessManager:
    """
    Manages CDP connection to Chrome via browser-harness daemon.

    Provides async wrappers around browser-harness synchronous helpers,
    with session management and lifecycle control.
    """

    def __init__(self, name: str = "openclaw"):
        self.name = name
        self._connected = False
        self._daemon_process = None

    async def start(self) -> bool:
        """Start the browser-harness daemon and connect to Chrome."""
        if not BH_AVAILABLE:
            logger.error("browser-harness package not available")
            return False

        try:
            # Check if daemon is already running
            loop = asyncio.get_running_loop()
            alive = await loop.run_in_executor(None, ipc.ping, self.name)
            if alive:
                logger.info(f"browser-harness daemon '{self.name}' already running")
                self._connected = True
                return True

            # Try to start daemon
            from browser_harness.admin import ensure_daemon
            await loop.run_in_executor(None, ensure_daemon)

            # Verify connection
            alive = await loop.run_in_executor(None, ipc.ping, self.name)
            if alive:
                self._connected = True
                logger.info("browser-harness daemon started and connected")
                return True

            logger.error("Failed to start browser-harness daemon")
            return False

        except Exception as e:
            logger.error(f"Failed to initialize browser-harness: {e}")
            return False

    async def shutdown(self):
        """Shutdown the harness manager."""
        self._connected = False
        logger.info("BrowserHarnessManager shut down")

    @property
    def is_connected(self) -> bool:
        return self._connected and BH_AVAILABLE

    async def navigate(self, url: str) -> dict:
        """Navigate to a URL."""
        return await self._run(bh.goto_url, url)

    async def get_page_info(self) -> dict:
        """Get current page info (url, title, viewport, scroll)."""
        return await self._run(bh.page_info)

    async def execute_js(self, expression: str) -> Any:
        """Execute JavaScript and return the result."""
        return await self._run(bh.js, expression)

    async def click(self, x: int, y: int, button: str = "left"):
        """Click at coordinates."""
        return await self._run(bh.click_at_xy, x, y, button)

    async def click_element(self, selector: str, timeout: float = 5.0) -> bool:
        """Click an element found by CSS selector. Returns True if found and clicked."""
        found = await self.wait_for_element(selector, timeout=timeout)
        if not found:
            return False
        coords = await self.execute_js(
            f"(()=>{{const e=document.querySelector({json.dumps(selector)});"
            f"if(!e)return null;const r=e.getBoundingClientRect();"
            f"return{{x:r.x+r.width/2,y:r.y+r.height/2}}}})()"
        )
        if not coords:
            return False
        await self.click(coords["x"], coords["y"])
        return True

    async def type_text(self, text: str):
        """Type text using keyboard events."""
        return await self._run(bh.type_text, text)

    async def fill_input(self, selector: str, text: str, clear_first: bool = True):
        """Fill an input element (works with React/Vue controlled inputs)."""
        return await self._run(bh.fill_input, selector, text, clear_first)

    async def press_key(self, key: str):
        """Press a keyboard key."""
        return await self._run(bh.press_key, key)

    async def scroll(self, x: int = 500, y: int = 500, dy: int = -300):
        """Scroll the page."""
        return await self._run(bh.scroll, x, y, dy)

    async def wait_for_element(self, selector: str, timeout: float = 10.0, visible: bool = False) -> bool:
        """Wait for an element to appear in the DOM."""
        return await self._run(bh.wait_for_element, selector, timeout, visible)

    async def wait_for_load(self, timeout: float = 15.0) -> bool:
        """Wait for page to finish loading."""
        return await self._run(bh.wait_for_load, timeout)

    async def wait_for_network_idle(self, timeout: float = 10.0) -> bool:
        """Wait for network requests to finish."""
        return await self._run(bh.wait_for_network_idle, timeout)

    async def take_screenshot(self, path: str | None = None) -> str:
        """Capture a screenshot. Returns the file path."""
        return await self._run(bh.capture_screenshot, path)

    async def list_tabs(self) -> list[dict]:
        """List all browser tabs."""
        return await self._run(bh.list_tabs, False)

    async def new_tab(self, url: str = "about:blank") -> str:
        """Open a new tab and return its targetId."""
        return await self._run(bh.new_tab, url)

    async def switch_tab(self, target_id: str):
        """Switch to a tab by targetId."""
        return await self._run(bh.switch_tab, target_id)

    async def get_element_text(self, selector: str) -> str | None:
        """Get text content of an element."""
        return await self.execute_js(
            f"(()=>{{const e=document.querySelector({json.dumps(selector)});"
            f"return e?e.textContent.trim():null}})()"
        )

    async def get_element_attr(self, selector: str, attr: str) -> str | None:
        """Get an attribute value from an element."""
        return await self.execute_js(
            f"(()=>{{const e=document.querySelector({json.dumps(selector)});"
            f"return e?e.getAttribute({json.dumps(attr)}):null}})()"
        )

    async def query_elements(self, selector: str) -> list[dict]:
        """Query all elements matching a selector, return their text and attributes."""
        return await self.execute_js(
            f"(()=>{{const els=document.querySelectorAll({json.dumps(selector)});"
            f"return Array.from(els).map(e=>({{"
            f"text:e.textContent.trim(),"
            f"href:e.getAttribute('href')||'',"
            f"dataTestId:e.getAttribute('data-testid')||''"
            f"}}))}})()"
        ) or []

    async def cdp_raw(self, method: str, **params) -> dict:
        """Send a raw CDP command."""
        return await self._run(bh.cdp, method, **params)

    async def _run(self, func, *args, **kwargs) -> Any:
        """Run a synchronous browser-harness function in a thread pool."""
        if not self._connected:
            raise RuntimeError("BrowserHarnessManager not connected. Call start() first.")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


# Global singleton
_harness_manager: Optional[BrowserHarnessManager] = None


async def get_harness_manager() -> BrowserHarnessManager:
    """Get or create the global BrowserHarnessManager."""
    global _harness_manager
    if _harness_manager is None:
        _harness_manager = BrowserHarnessManager()
    return _harness_manager


async def init_harness_manager() -> bool:
    """Initialize and start the global harness manager."""
    manager = await get_harness_manager()
    return await manager.start()


async def shutdown_harness_manager():
    """Shutdown the global harness manager."""
    global _harness_manager
    if _harness_manager:
        await _harness_manager.shutdown()
        _harness_manager = None
