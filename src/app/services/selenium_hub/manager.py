import asyncio
from typing import ClassVar

from .core.docker_backend import DockerHubBackend
from .core.hub_backend import HubBackend
from .core.kubernetes.backend import KubernetesHubBackend
from .models import DeploymentMode
from .models.browser import BrowserConfigs, BrowserType
from .models.general_settings import SeleniumHubGeneralSettings


class SeleniumHubManager:
    """Selects and delegates to the correct backend for cleanup and manages retries."""

    _BACKEND_MAP: ClassVar[dict[DeploymentMode, type[HubBackend]]] = {
        DeploymentMode.DOCKER: DockerHubBackend,
        DeploymentMode.KUBERNETES: KubernetesHubBackend,
    }

    def __init__(self, settings: SeleniumHubGeneralSettings) -> None:
        try:
            backend_cls: type[HubBackend] = self._BACKEND_MAP[settings.DEPLOYMENT_MODE]
        except KeyError:
            valid = ", ".join(mode.value for mode in self._BACKEND_MAP.keys())
            raise ValueError(
                f"Unknown backend mode: {settings.DEPLOYMENT_MODE!r}. Valid modes are: {valid}."
            )
        self.backend: HubBackend = backend_cls(settings)

    @property
    def URL(self) -> str:
        """Return the base URL for the Selenium Hub."""
        return self.backend.URL

    def cleanup(self) -> None:
        self.backend.cleanup()

    async def ensure_hub_running(self, retries: int = 2, wait_seconds: float = 0.0) -> bool:
        """
        Try to ensure the hub is running, with optional retries and wait time between attempts.
        """
        for attempt in range(retries):
            if await self.backend.ensure_hub_running():
                return True
            if attempt < retries - 1 and wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
        return False

    async def create_browsers(
        self,
        count: int,
        browser_type: BrowserType,
        browser_configs: BrowserConfigs,
    ) -> list[str]:
        if not await self.ensure_hub_running():
            raise RuntimeError("Failed to ensure Selenium Hub is running")
        return await self.backend.create_browsers(count, browser_type, browser_configs)

    async def delete_browsers(self, browser_ids: list[str]) -> list[str]:
        """
        Delete multiple browser containers by their IDs in parallel. Returns a list of successfully deleted IDs.
        """
        return await self.backend.delete_browsers(browser_ids)

    async def check_hub_health(self, username: str, password: str) -> bool:
        return await self.backend.check_hub_health(username, password)
