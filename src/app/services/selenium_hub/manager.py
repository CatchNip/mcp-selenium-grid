import asyncio
from typing import Any, ClassVar, Dict, List, Type

from app.core.models import DeploymentMode

from .backend import HubBackend
from .docker_backend import DockerHubBackend
from .k8s_backend import KubernetesHubBackend


class SeleniumHubManager:
    """Selects and delegates to the correct backend for cleanup and manages retries."""

    _BACKEND_MAP: ClassVar[Dict[DeploymentMode, Type[HubBackend]]] = {
        DeploymentMode.DOCKER: DockerHubBackend,
        DeploymentMode.KUBERNETES: KubernetesHubBackend,
    }

    def __init__(self, settings: Any) -> None:
        try:
            backend_cls: Type[HubBackend] = self._BACKEND_MAP[settings.DEPLOYMENT_MODE]
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
        browser_type: str,
        browser_configs: Dict[str, Any],
    ) -> List[str]:
        if not await self.ensure_hub_running():
            raise RuntimeError("Failed to ensure Selenium Hub is running")
        return await self.backend.create_browsers(count, browser_type, browser_configs)

    async def delete_browsers(self, browser_ids: List[str]) -> List[str]:
        """
        Delete multiple browser containers by their IDs in parallel. Returns a list of successfully deleted IDs.
        """
        return await self.backend.delete_browsers(browser_ids)
