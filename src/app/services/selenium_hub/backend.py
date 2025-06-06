from abc import ABC, abstractmethod
from typing import Any, List

from app.core.models import BrowserConfig


class HubBackend(ABC):
    """Abstract interface for Selenium Hub backends."""

    def __init__(self: "HubBackend", *args: Any, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def cleanup(self) -> None:
        pass

    @abstractmethod
    async def ensure_hub_running(self) -> bool:
        pass

    @abstractmethod
    async def create_browsers(
        self, count: int, browser_type: str, browser_configs: dict[str, BrowserConfig]
    ) -> list[str]:
        pass

    @abstractmethod
    async def delete_browser(self, browser_id: str) -> bool:
        """
        Delete a single browser by its ID. Returns True if deleted, False otherwise.
        """

    async def delete_browsers(self, browser_ids: List[str]) -> List[str]:
        """
        Delete multiple browser containers by their IDs in parallel. Returns a list of successfully deleted IDs.
        """
        import asyncio

        results = await asyncio.gather(*(self.delete_browser(bid) for bid in browser_ids))
        return [bid for bid, ok in zip(browser_ids, results) if ok]
