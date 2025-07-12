"""Core settings for MCP Server."""

from pydantic import Field, SecretStr

from app.services.selenium_hub.models.general_settings import SeleniumHubGeneralSettings


class Settings(SeleniumHubGeneralSettings):
    """MCP Server settings."""

    # API Settings
    PROJECT_NAME: str = Field(default="MCP Selenium Server")
    VERSION: str = Field(default="0.1.0")
    API_V1_STR: str = Field(default="/api/v1")

    # API Token
    API_TOKEN: SecretStr = Field(default=SecretStr("CHANGE_ME"))

    # Security Settings
    BACKEND_CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:8000"],
        validation_alias="ALLOWED_ORIGINS",
    )
