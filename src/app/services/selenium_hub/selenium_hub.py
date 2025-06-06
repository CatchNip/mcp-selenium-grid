"""Selenium Hub service for managing browser instances."""

from typing import Optional

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
        manager (SeleniumHubManager): Manager instance that handles the actual hub operations
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
            self.manager: SeleniumHubManager = SeleniumHubManager(self.settings)
            self._initialized = True
        elif settings is not None:
            # Update settings
            self.settings = settings

            # Reinitialize manager with updated settings
            self.manager = SeleniumHubManager(self.settings)

    @track_hub_metrics()
    async def ensure_hub_running(self, retries: int = 2, wait_seconds: float = 0.0) -> bool:
        """
        Ensure the hub is running, delegating retry/wait logic to the manager.

        Args:
            retries (int): Number of retry attempts if hub is not running
            wait_seconds (float): Time to wait between retries

        Returns:
            bool: True if hub is running, False otherwise
        """
        return await self.manager.ensure_hub_running(retries=retries, wait_seconds=wait_seconds)

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
        return await self.manager.create_browsers(
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
        return await self.manager.delete_browsers(browser_ids)
