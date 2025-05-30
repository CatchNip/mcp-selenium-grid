"""Core settings for MCP Server."""

from typing import Any, Dict, List, Optional, Tuple, Type

from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)
from typing_extensions import override

from app.core.env_helpers import getenv_as_bool
from app.core.models import BrowserConfig, ContainerResources


class Settings(BaseSettings):
    """MCP Server settings."""

    # API Settings
    PROJECT_NAME: str = Field(default="MCP Selenium Server")
    VERSION: str = Field(default="0.1.0")
    API_V1_STR: str = Field(default="/api/v1")

    # API Token
    API_TOKEN: str = Field(default="CHANGE_ME")

    # Selenium Hub Auth
    SELENIUM_HUB_USER: str = Field(default="user")
    SELENIUM_HUB_PASSWORD: str = Field(default="CHANGE_ME")

    # Selenium Settings
    SELENIUM_HUB_PORT: int = Field(default=4444)
    MAX_BROWSER_INSTANCES: Optional[int] = Field(default=None)
    SE_NODE_MAX_SESSIONS: int = Field(default=1)

    # Deployment Settings
    DEPLOYMENT_MODE: str = Field(
        default="kubernetes" if getenv_as_bool("IS_RUNNING_IN_DOCKER") else "docker"
    )

    # Kubernetes Settings
    K8S_NAMESPACE: str = Field(default="selenium-grid")
    K8S_RETRY_DELAY_SECONDS: int = Field(default=2)
    K8S_MAX_RETRIES: int = Field(default=5)

    # Security Settings
    BACKEND_CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: ["http://localhost:8000"],
        validation_alias="ALLOWED_ORIGINS",
    )

    # Browser Configurations
    BROWSER_CONFIGS: Dict[str, BrowserConfig] = Field(default_factory=dict)

    model_config = SettingsConfigDict(
        yaml_file="config.yaml",
        yaml_file_encoding="utf-8",
        alias_generator=lambda name: name.lower(),
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("BROWSER_CONFIGS", mode="before")
    @classmethod
    def _parse_browser_configs(cls, raw: Dict[str, Any]) -> Dict[str, BrowserConfig]:
        # Transform raw dict into validated BrowserConfig objects
        configs: dict[str, BrowserConfig] = {}
        for name, cfg in (raw or {}).items():
            # container resources, if present
            if "resources" in cfg:
                cfg["resources"] = ContainerResources(**cfg["resources"])
            configs[name] = BrowserConfig(**cfg)
        return configs

    @property
    def SELENIUM_HUB_BASE_URL_DYNAMIC(self) -> str:
        """
        Dynamically determine the Selenium Hub base URL based on deployment mode.
        - For 'docker': use 'http://localhost:4444'
        - For 'kubernetes': use 'http://selenium-hub.{namespace}.svc.cluster.local:4444'
        """
        if self.DEPLOYMENT_MODE == "docker":
            return f"http://localhost:{self.SELENIUM_HUB_PORT}"
        elif self.DEPLOYMENT_MODE == "kubernetes":
            return f"http://selenium-hub.{self.K8S_NAMESPACE}.svc.cluster.local:{self.SELENIUM_HUB_PORT}"
        else:
            # fallback to localhost for unknown modes
            return f"http://localhost:{self.SELENIUM_HUB_PORT}"

    @override
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[
        YamlConfigSettingsSource,
        PydanticBaseSettingsSource,
        PydanticBaseSettingsSource,
        PydanticBaseSettingsSource,
        PydanticBaseSettingsSource,
    ]:
        # Load config.yaml first, then the default sources
        return (
            YamlConfigSettingsSource(settings_cls),
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )


settings = Settings()
