from browser_cluster.manager.browser_manager import BrowserManager
from playwright.async_api import Page, BrowserContext

class BrowserWorker:
    def __init__(self, context_id: str, browser_manager: BrowserManager):
        self.context_id = context_id
        self.browser_manager = browser_manager

    async def execute_task(self, url: str):
        context: BrowserContext = await self.browser_manager.get_context(self.context_id)
        if not context:
            # If Context doesn't exist, create an empty one first. 
            # In a real scenario proxy configurations are attached to context creation.
            context = await self.browser_manager.create_context(self.context_id)

        page: Page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded")
            content = await page.content()
            return content
        finally:
            await page.close()
