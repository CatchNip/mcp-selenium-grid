"""Selenium Hub service for managing browser instances."""

from app.core.settings import settings
from app.services.metrics import track_browser_metrics, track_hub_metrics

from .manager import SeleniumHubManager


class SeleniumHub:
    """Service for managing Selenium Grid Hub and Node instances via manager/adaptor pattern."""

    def __init__(self):
        self.deployment_mode = settings.DEPLOYMENT_MODE
        self.manager = SeleniumHubManager(self.deployment_mode, settings)
        self.browser_configs = settings.BROWSER_CONFIGS

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
