from typing import Any, Dict, List

from .backend import HubBackend
from .docker_backend import DockerHubBackend
from .k8s_backend import KubernetesHubBackend


class SeleniumHubManager:
    """Selects and delegates to the correct backend for cleanup and manages retries."""

    def __init__(self, mode: str, settings: Any) -> None:
        if mode == "docker":
            self.backend: HubBackend = DockerHubBackend(settings)
        elif mode == "kubernetes":
            self.backend = KubernetesHubBackend(settings)
        else:
            raise ValueError(f"Unknown backend mode: {mode}")

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
                import asyncio

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
