"""Selenium Hub service for managing browser instances."""

import asyncio

from ...core.settings import settings
from ..metrics import track_browser_metrics, track_hub_metrics
from .manager import SeleniumHubManager


class SeleniumHub:
    """Service for managing Selenium Grid Hub and Node instances via manager/adaptor pattern."""

    def __init__(self):
        self.deployment_mode = settings.DEPLOYMENT_MODE
        self.manager = SeleniumHubManager(self.deployment_mode, settings)
        self.browser_configs = {
            "chrome": {
                "image": "selenium/node-chrome:4.18.1",
                "port": 4444,
                "resources": {"memory": "2G", "cpu": "1"},
            },
            "firefox": {
                "image": "selenium/node-firefox:4.18.1",
                "port": 4444,
                "resources": {"memory": "2G", "cpu": "1"},
            },
            "edge": {
                "image": "selenium/node-edge:4.18.1",
                "port": 4444,
                "resources": {"memory": "2G", "cpu": "1"},
            },
        }

    @track_hub_metrics()
    async def ensure_hub_running(self) -> bool:
        return await self.manager.ensure_hub_running(self.browser_configs)

    @track_browser_metrics()
    async def create_browsers(self, count: int, browser_type: str) -> list:
        if not await self.ensure_hub_running():
            raise RuntimeError("Failed to ensure Selenium Hub is running")
        if count <= 0:
            raise ValueError("Browser count must be positive")
        if browser_type not in self.browser_configs:
            raise KeyError(f"Unsupported browser type: {browser_type}")
        if settings.MAX_BROWSER_INSTANCES and count > settings.MAX_BROWSER_INSTANCES:
            raise ValueError(
                f"Maximum browser instances exceeded: {count} > {settings.MAX_BROWSER_INSTANCES}"
            )
        return await self.manager.create_browsers(count, browser_type, self.browser_configs)

    async def get_browser_status(self, browser_id: str) -> dict:
        """Get status for a specific browser instance."""
        return await self.manager.get_browser_status(browser_id)

    @staticmethod
    async def _generate_id() -> str:
        # Use event loop time as a unique-ish value, but do not await
        return hex(hash(str(asyncio.get_event_loop().time())))[2:10]
