"""Core settings for MCP Server."""

from typing import Dict, List, Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings

from app.core.env_helpers import getenv_as_bool
from app.core.models import BrowserConfig


class Settings(BaseSettings):
    """MCP Server settings."""

    # API Settings
    PROJECT_NAME: str = Field(default="MCP Selenium Server")
    VERSION: str = Field(default="0.1.0")
    API_V1_STR: str = Field(default="/api/v1")

    # Selenium Settings
    SELENIUM_HUB_PORT: int = Field(default=4444)
    SELENIUM_HUB_BASE_URL: str = Field(default="http://localhost:4444")
    MAX_BROWSER_INSTANCES: Optional[int] = Field(default=None)
    SE_NODE_MAX_SESSIONS: int = Field(default=1)

    # Deployment Settings
    DEPLOYMENT_MODE: str = Field(
        default="kubernetes" if getenv_as_bool("IS_RUNNING_IN_DOCKER") else "docker"
    )
    K8S_NAMESPACE: str = Field(default="selenium-grid")

    # Security Settings
    BACKEND_CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: ["http://localhost:8000"],
        validation_alias="ALLOWED_ORIGINS",
    )

    # Browser Configurations
    BROWSER_CONFIGS: Dict[str, BrowserConfig] = Field(
        default_factory=dict,
    )

    # API Token
    API_TOKEN: str = Field(default="CHANGE_ME")

    # Kubernetes Settings
    K8S_RETRY_DELAY_SECONDS: int = Field(default=2)
    K8S_MAX_RETRIES: int = Field(default=5)

    class Config:
        env_file = "config.yaml"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"

    @classmethod
    def parse_yaml(cls) -> "Settings":
        config_file = "config.yaml"
        with open(config_file, "r", encoding="utf-8") as file:
            yaml_data = yaml.safe_load(file)
        return cls.model_validate(yaml_data)


settings = Settings.parse_yaml()
