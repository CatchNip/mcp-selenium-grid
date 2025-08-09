import asyncio
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urljoin

import httpx

from ..common.logger import logger
from ..models.browser import BrowserConfigs, BrowserType


class HubBackend(ABC):
    """Abstract interface for Selenium Hub backends."""

    def __init__(self: "HubBackend", *args: Any, **kwargs: Any) -> None:
        pass

    @property
    @abstractmethod
    def URL(self) -> str:
        """Base URL for the Selenium Hub."""

    @abstractmethod
    def cleanup_hub(self) -> None:
        """Clean up Selenium Hub and its related resources."""

    @abstractmethod
    def cleanup_browsers(self) -> None:
        """Clean up all browser instances."""

    def cleanup(self) -> None:
        """Clean up all resources by first cleaning up browsers then the hub."""
        self.cleanup_browsers()
        self.cleanup_hub()

    @abstractmethod
    async def ensure_hub_running(self) -> bool:
        pass

    @abstractmethod
    async def create_browsers(
        self,
        count: int,
        browser_type: BrowserType,
        browser_configs: BrowserConfigs,
    ) -> list[str]:
        pass

    @abstractmethod
    async def delete_browser(self, browser_id: str) -> bool:
        """
        Delete a single browser by its ID. Returns True if deleted, False otherwise.
        """

    async def delete_browsers(self, browser_ids: list[str]) -> list[str]:
        """
        Delete multiple browser containers by their IDs in parallel. Returns a list of successfully deleted IDs.
        """
        results = await asyncio.gather(*(self.delete_browser(bid) for bid in browser_ids))
        return [bid for bid, ok in zip(browser_ids, results) if ok]

    async def check_hub_health(self, username: str, password: str) -> bool:
        """
        Check if the Selenium Hub is healthy and reachable by polling the status endpoint.
        Returns True if the hub responds with 200 OK, False otherwise.
        """
        url = urljoin(self.URL, "status")
        logger.info(f"{self.__class__.__name__}: Checking health for {url}")
        auth = httpx.BasicAuth(username, password)
        try:
            # Use a longer timeout for health checks to allow for startup time
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0), auth=auth) as client:
                response = await client.get(url)
                if response.status_code == httpx.codes.OK:
                    logger.info("Health check SUCCEED!")
                    return True
                else:
                    try:
                        response_body = response.text
                        logger.warning(
                            f"Health check failed with status code: {response.status_code}, response body: {response_body}"
                        )
                    except Exception:
                        logger.warning(
                            f"Health check failed with status code: {response.status_code}, could not read response body"
                        )
                    return False
        except httpx.RequestError as e:
            logger.warning(f"Health check request failed: {e or 'No error message.'}")
            return False
