from abc import ABC, abstractmethod


class HubBackend(ABC):
    """Abstract interface for Selenium Hub backends."""

    @abstractmethod
    def cleanup(self) -> None:
        pass

    @abstractmethod
    async def ensure_hub_running(self, browser_configs: dict) -> bool:
        pass

    @abstractmethod
    async def create_browsers(self, count: int, browser_type: str, browser_configs: dict) -> list:
        pass
