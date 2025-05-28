from abc import ABC, abstractmethod

from app.core.models import BrowserConfig


class HubBackend(ABC):
    """Abstract interface for Selenium Hub backends."""

    @abstractmethod
    def cleanup(self) -> None:
        pass

    @abstractmethod
    async def ensure_hub_running(self) -> bool:
        pass

    @abstractmethod
    async def create_browsers(
        self, count: int, browser_type: str, browser_configs: dict[str, "BrowserConfig"]
    ) -> list[str]:
        pass
