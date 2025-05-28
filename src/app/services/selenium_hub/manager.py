from typing import Any, Dict, List

from .backend import HubBackend
from .docker_backend import DockerHubBackend
from .k8s_backend import KubernetesHubBackend


class SeleniumHubManager:
    """Selects and delegates to the correct backend for cleanup."""

    def __init__(self, mode: str, settings: Any) -> None:
        if mode == "docker":
            self.backend: HubBackend = DockerHubBackend(settings)
        elif mode == "kubernetes":
            self.backend = KubernetesHubBackend(settings)
        else:
            raise ValueError(f"Unknown backend mode: {mode}")

    def cleanup(self) -> None:
        self.backend.cleanup()

    async def ensure_hub_running(self, browser_configs: Dict[str, Any]) -> bool:
        return await self.backend.ensure_hub_running()

    async def create_browsers(
        self, count: int, browser_type: str, browser_configs: Dict[str, Any]
    ) -> List[str]:
        return await self.backend.create_browsers(count, browser_type, browser_configs)
