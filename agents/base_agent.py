from abc import ABC, abstractmethod
from browser_cluster.manager.browser_manager import BrowserManager
# db interface to be injected implementation

class BaseAgent(ABC):
    """
    Abstract Base Class for all specialized AI Agents.
    Includes context for browser automation and database storage.
    """
    def __init__(self, name: str, browser_manager: BrowserManager, db):
        self.name = name
        self.browser_manager = browser_manager
        self.db = db
        self.worker = None

    @abstractmethod
    async def run(self, task: dict):
        """
        Executes the main logic for the specific agent capability.
        Must be implemented by child classes.
        """
        pass
