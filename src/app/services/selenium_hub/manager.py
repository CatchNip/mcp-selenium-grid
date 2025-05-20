from .backend import HubBackend
from .docker_backend import DockerHubBackend
from .k8s_backend import KubernetesHubBackend


class SeleniumHubManager:
    """Selects and delegates to the correct backend for cleanup."""

    def __init__(self, mode: str, settings):
        if mode == "docker":
            self.backend: HubBackend = DockerHubBackend(settings)
        elif mode == "kubernetes":
            self.backend: HubBackend = KubernetesHubBackend(settings)
        else:
            raise ValueError(f"Unknown backend mode: {mode}")

    def cleanup(self) -> None:
        self.backend.cleanup()

    async def ensure_hub_running(self, browser_configs: dict) -> bool:
        if hasattr(self.backend, "ensure_hub_running"):
            return await self.backend.ensure_hub_running(browser_configs)
        raise NotImplementedError("Backend does not implement ensure_hub_running")

    async def create_browsers(self, count: int, browser_type: str, browser_configs: dict) -> list:
        if hasattr(self.backend, "create_browsers"):
            return await self.backend.create_browsers(count, browser_type, browser_configs)
        raise NotImplementedError("Backend does not implement create_browsers")

    async def get_browser_status(self, browser_id: str) -> dict:
        if hasattr(self.backend, "get_browser_status"):
            return await self.backend.get_browser_status(browser_id)
        raise NotImplementedError("Backend does not implement get_browser_status")
