"""Selenium Hub service for managing browser instances."""

from typing import Dict

from app.core.models import BrowserConfig
from app.core.settings import settings
from app.services.metrics import track_browser_metrics, track_hub_metrics

from .manager import SeleniumHubManager


class SeleniumHub:
    """Service for managing Selenium Grid Hub and Node instances via manager/adaptor pattern."""

    def __init__(self) -> None:
        self.deployment_mode: str = settings.DEPLOYMENT_MODE
        self.manager: SeleniumHubManager = SeleniumHubManager(self.deployment_mode, settings)
        self.browser_configs: Dict[str, BrowserConfig] = settings.BROWSER_CONFIGS

    @track_hub_metrics()
    async def ensure_hub_running(self, retries: int = 2, wait_seconds: float = 0.0) -> bool:
        """
        Ensure the hub is running, delegating retry/wait logic to the manager.
        """
        return await self.manager.ensure_hub_running(retries=retries, wait_seconds=wait_seconds)

    @track_browser_metrics()
    async def create_browsers(self, count: int, browser_type: str) -> list[str]:
        if count <= 0:
            raise ValueError("Browser count must be positive")
        if browser_type not in self.browser_configs:
            raise KeyError(f"Unsupported browser type: {browser_type}")
        if settings.MAX_BROWSER_INSTANCES and count > settings.MAX_BROWSER_INSTANCES:
            raise ValueError(
                f"Maximum browser instances exceeded: {count} > {settings.MAX_BROWSER_INSTANCES}"
            )
        return await self.manager.create_browsers(count, browser_type, self.browser_configs)
