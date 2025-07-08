"""Selenium Hub service for managing browser instances."""

import asyncio
import logging
from typing import Optional
from urllib.parse import urljoin

import httpx

from app.core.settings import Settings
from app.services.metrics import track_browser_metrics, track_hub_metrics

from .manager import SeleniumHubManager


class SeleniumHub:
    """
    Service for managing Selenium Grid Hub and Node instances via manager/adaptor pattern.

    This class implements the Singleton pattern to ensure only one instance manages the Selenium Grid Hub
    and its browser nodes across the application.

    The singleton instance is created on first instantiation and reused for subsequent calls.
    The initialization of instance variables only happens once, even if the constructor is called multiple times.
    Settings provided after initialization will update the existing instance.

    Attributes:
        settings (Settings): Application settings used to configure the hub and browsers
        _manager (SeleniumHubManager): Manager instance that handles the actual hub operations
        browser_configs (Dict[str, BrowserConfig]): Configuration for supported browser types

    Class Variables:
        _instance (Optional[SeleniumHub]): The singleton instance of the class
        _initialized (bool): Flag indicating whether the instance has been initialized
    """

    _instance: Optional["SeleniumHub"] = None
    _initialized: bool = False

    def __new__(cls, settings: Optional[Settings] = None) -> "SeleniumHub":
        """
        Create or return the singleton instance.

        Args:
            settings (Optional[Settings]): Application settings. Required for first initialization.

        Returns:
            SeleniumHub: The singleton instance

        Raises:
            ValueError: If settings is None during first initialization
        """
        if cls._instance is None:
            if settings is None:
                raise ValueError("Settings must be provided for first initialization")
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """
        Initialize or update the singleton instance.

        If this is the first initialization:
        - Creates a new instance with the provided settings
        - Initializes the manager and browser configs

        If the instance already exists:
        - Updates the settings using Pydantic's model methods
        - Reinitializes the manager with new settings
        - Updates browser configs if needed

        Args:
            settings (Optional[Settings]): Application settings. Required for first initialization.

        Raises:
            ValueError: If settings is None during first initialization
            ValidationError: If any of the updated values are invalid
        """
        if not self._initialized:
            if settings is None:
                raise ValueError("Settings must be provided for first initialization")
            self.settings: Settings = settings
            self._manager: SeleniumHubManager = SeleniumHubManager(self.settings)
            self._initialized = True
        elif settings is not None:
            # Update settings
            self.settings = settings

            # Reinitialize manager with updated settings
            self._manager = SeleniumHubManager(self.settings)

    @property
    def URL(self) -> str:
        """
        Get the base URL for the Selenium Hub.

        Returns:
            str: The base URL for the Selenium Hub
        """
        return self._manager.URL

    @track_hub_metrics()
    async def check_hub_health(self) -> bool:
        """
        Check if the Selenium Hub is healthy and reachable by polling the status endpoint.

        Returns:
            bool: True if the hub responds with 200 OK, False otherwise.
        """
        url = urljoin(self._manager.URL, "status")
        auth = httpx.BasicAuth(
            self.settings.SELENIUM_HUB_USER.get_secret_value(),
            self.settings.SELENIUM_HUB_PASSWORD.get_secret_value(),
        )
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(2.0), auth=auth) as client:
                response = await client.get(url)
                if response.status_code == httpx.codes.OK:
                    return True
                else:
                    logging.error(
                        f"Hub health check failed with status code: {response.status_code}"
                    )
                    return False
        except httpx.RequestError:
            return False

    @track_hub_metrics()
    async def ensure_hub_running(self) -> bool:
        """
        Ensure the hub container/service is running.
        This only checks if the container/service exists and is running.

        Returns:
            bool: True if the hub container/service is running, False otherwise.
        """
        return await self._manager.ensure_hub_running()

    @track_hub_metrics()
    async def wait_for_hub_healthy(self, check_interval: float = 1.0) -> bool:
        """
        Wait for the hub to be healthy and reachable.
        Uses asyncio.timeout() to limit the total wait time.

        Args:
            check_interval (float): Time between health checks in seconds.

        Returns:
            bool: True if the hub becomes healthy within the timeout, False otherwise.
        """
        try:
            async with asyncio.timeout(30):  # 30 second default timeout
                while True:
                    if await self.check_hub_health():
                        return True
                    await asyncio.sleep(check_interval)
        except asyncio.TimeoutError:
            return False

    @track_browser_metrics()
    async def create_browsers(self, count: int, browser_type: str) -> list[str]:
        """
        Create the specified number of browser instances of the given type.

        Args:
            count (int): Number of browser instances to create
            browser_type (str): Type of browser to create (must be in browser_configs)

        Returns:
            list[str]: List of created browser IDs

        Raises:
            ValueError: If count is not positive or exceeds MAX_BROWSER_INSTANCES
            KeyError: If browser_type is not supported
        """
        if count <= 0:
            raise ValueError("Browser count must be positive")
        if browser_type not in self.settings.BROWSER_CONFIGS:
            raise KeyError(f"Unsupported browser type: {browser_type}")
        if self.settings.MAX_BROWSER_INSTANCES and count > self.settings.MAX_BROWSER_INSTANCES:
            raise ValueError(
                f"Maximum browser instances exceeded: {count} > {self.settings.MAX_BROWSER_INSTANCES}"
            )
        return await self._manager.create_browsers(
            count, browser_type, self.settings.BROWSER_CONFIGS
        )

    @track_browser_metrics()
    async def delete_browsers(self, browser_ids: list[str]) -> list[str]:
        """
        Delete the specified browser instances.

        Args:
            browser_ids (list[str]): List of browser IDs to delete

        Returns:
            list[str]: List of successfully deleted browser IDs
        """
        if not browser_ids:
            return []
        return await self._manager.delete_browsers(browser_ids)
