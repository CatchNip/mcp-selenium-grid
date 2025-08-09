"""Core settings for MCP Server."""

from pydantic import Field, SecretStr, field_validator

from app.common.toml import load_value_from_toml
from app.services.selenium_hub.models.general_settings import SeleniumHubGeneralSettings


class Settings(SeleniumHubGeneralSettings):
    """MCP Server settings."""

    # API Settings
    PROJECT_NAME: str = "MCP Selenium Grid"
    VERSION: str = ""

    @field_validator("VERSION", mode="before")
    @classmethod
    def load_version_from_pyproject(cls, v: str) -> str:
        return v or load_value_from_toml(["project", "version"])

    API_V1_STR: str = "/api/v1"

    # API Token
    API_TOKEN: SecretStr = SecretStr("CHANGE_ME")

    # Security Settings
    BACKEND_CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:8000"],
        validation_alias="ALLOWED_ORIGINS",
    )
