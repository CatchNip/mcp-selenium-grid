"""Core settings for MCP Server."""

from importlib.metadata import metadata, version

from pydantic import Field, SecretStr

from app.services.selenium_hub.models.general_settings import SeleniumHubGeneralSettings


class Settings(SeleniumHubGeneralSettings):
    """MCP Server settings."""

    # Project Settings
    PACKAGE_NAME: str = "mcp-selenium-grid"
    PROJECT_NAME: str = "MCP Selenium Grid"

    @property
    def VERSION(self) -> str:
        return version(self.PACKAGE_NAME)

    @property
    def DESCRIPTION(self) -> str:
        return metadata(self.PACKAGE_NAME).get("Summary", "").strip()

    # API Settings
    API_V1_STR: str = "/api/v1"
    API_TOKEN: SecretStr = SecretStr("CHANGE_ME")
    AUTH_ENABLED: bool = True

    # Security Settings
    BACKEND_CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:8000"],
        validation_alias="ALLOWED_ORIGINS",
    )
