import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext

class BrowserManager:
    def __init__(self, user_data_dir: str = None, proxy: dict = None):
        self.playwright = None
        self.browser: Browser = None
        self.contexts: dict[str, BrowserContext] = {}
        self.user_data_dir = user_data_dir
        self.proxy_config = proxy
        self.persistent_context = None

    async def start(self):
        self.playwright = await async_playwright().start()
        
        launch_options = {
            "headless": False if self.user_data_dir else True,
            "viewport": {"width": 1280, "height": 720}
        }
        
        if self.proxy_config:
            launch_options["proxy"] = {"server": self.proxy_config["host"]}
            if self.proxy_config.get("username"):
                launch_options["proxy"]["username"] = self.proxy_config["username"]
                launch_options["proxy"]["password"] = self.proxy_config["password"]

        if self.user_data_dir:
            self.persistent_context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                **launch_options
            )
            print(f"[BrowserManager] Initialized with persistent user data dir: {self.user_data_dir}")
        else:
            # For non-persistent, proxy goes into new_context later or launch options
            self.browser = await self.playwright.chromium.launch(headless=True)
            print("[BrowserManager] Initialized (Ephemeral).")

    async def create_context(self, context_id: str, proxy: dict = None) -> BrowserContext:
        """Create an isolated browser context for an account session."""
        if not self.playwright:
            await self.start()
            
        if self.user_data_dir and self.persistent_context:
            self.contexts[context_id] = self.persistent_context
            return self.persistent_context
            
        kwargs = {"viewport": {"width": 1280, "height": 720}}
        use_proxy = proxy or self.proxy_config
        if use_proxy:
            kwargs["proxy"] = {"server": use_proxy["host"], "username": use_proxy.get("username", ""), "password": use_proxy.get("password", "")}
            
        context = await self.browser.new_context(**kwargs)
        self.contexts[context_id] = context
        return context

    async def get_context(self, context_id: str) -> BrowserContext:
        return self.contexts.get(context_id)

    async def close(self):
        for ctx_id, context in list(self.contexts.items()):
            if not self.user_data_dir:
                await context.close()
                
        if self.persistent_context:
            await self.persistent_context.close()
            
        if self.browser:
            await self.browser.close()
            
        if self.playwright:
            await self.playwright.stop()

# Global browser manager instance
browser_manager = BrowserManager()
