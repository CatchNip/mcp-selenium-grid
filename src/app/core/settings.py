"""Core settings for MCP Server."""

from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,  # Add Optional for the new field
    Tuple,
    Type,
)

from pydantic import Field, SecretStr, ValidationInfo, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)
from typing_extensions import override

from app.core.env_helpers import getenv_as_bool
from app.core.models import BrowserConfig, ContainerResources, DeploymentMode


class Settings(BaseSettings):
    """MCP Server settings."""

    model_config = SettingsConfigDict(
        yaml_file="config.yaml",
        yaml_file_encoding="utf-8",
        alias_generator=lambda name: name.lower(),
        case_sensitive=True,
        nested_model_default_partial_update=True,
        extra="ignore",
    )

    # API Settings
    PROJECT_NAME: str = Field(default="MCP Selenium Server")
    VERSION: str = Field(default="0.1.0")
    API_V1_STR: str = Field(default="/api/v1")

    # API Token
    API_TOKEN: SecretStr = Field(default=SecretStr("CHANGE_ME"))

    # Selenium Hub Auth
    SELENIUM_HUB_USER: SecretStr = Field(default=SecretStr("user"))
    SELENIUM_HUB_PASSWORD: SecretStr = Field(default=SecretStr("CHANGE_ME"))

    # Selenium Settings
    SELENIUM_HUB_PORT: int = Field(default=4444, frozen=True)

    @model_validator(mode="after")
    def _check_selenium_hub_port_is_default(self) -> "Settings":
        """Ensure SELENIUM_HUB_PORT remains the default value."""
        default_port = 4444
        if self.SELENIUM_HUB_PORT != default_port:
            raise ValueError(
                f"SELENIUM_HUB_PORT cannot be set. Port {default_port} is hardcoded in the container image."
            )
        return self

    MAX_BROWSER_INSTANCES: int = Field(default=1)
    SE_NODE_MAX_SESSIONS: int = Field(default=1)

    # VNC Settings
    SELENIUM_HUB_VNC_PASSWORD: SecretStr = Field(default=SecretStr("secret"))
    SELENIUM_HUB_VNC_PORT: int = Field(default=7900)

    SELENIUM_HUB_VNC_VIEW_ONLY: bool = Field(default=True)

    @field_validator("SELENIUM_HUB_VNC_VIEW_ONLY", mode="after")
    @classmethod
    def _convert_vnc_view_only_to_str(cls, v: bool) -> str:
        """Convert SELENIUM_HUB_VNC_VIEW_ONLY boolean to "1" or "0" string."""
        return "1" if v else "0"

    SE_VNC_NO_PASSWORD: bool = Field(default=False)

    @field_validator("SE_VNC_NO_PASSWORD", mode="before")
    @classmethod
    def _compute_vnc_no_password(cls, v: bool, info: ValidationInfo) -> bool:
        """Compute SE_VNC_NO_PASSWORD based on SELENIUM_HUB_VNC_PASSWORD."""
        return not bool(info.data.get("SELENIUM_HUB_VNC_PASSWORD"))

    @field_validator("SE_VNC_NO_PASSWORD", mode="after")
    @classmethod
    def _convert_vnc_no_password_to_str(cls, v: bool) -> str:
        """Convert SE_VNC_NO_PASSWORD boolean to "1" or "0" string."""
        return "1" if v else "0"

    # Deployment Settings
    DEPLOYMENT_MODE: DeploymentMode = Field(
        default=DeploymentMode.KUBERNETES
        if getenv_as_bool("IS_RUNNING_IN_DOCKER")
        else DeploymentMode.DOCKER
    )

    # Kubernetes Settings
    K8S_KUBECONFIG: Optional[Path] = Field(default=None)
    K8S_CONTEXT: Optional[str] = Field(default=None)
    K8S_NAMESPACE: str = Field(default="selenium-grid")
    K8S_SELENIUM_GRID_SERVICE_NAME: str = Field(default="selenium-grid")
    K8S_RETRY_DELAY_SECONDS: int = Field(default=2)
    K8S_MAX_RETRIES: int = Field(default=5)

    # Security Settings
    BACKEND_CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: ["http://localhost:8000"],
        validation_alias="ALLOWED_ORIGINS",
    )

    # Browser Configurations
    BROWSER_CONFIGS: Dict[str, BrowserConfig] = Field(default_factory=dict)

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
        PydanticBaseSettingsSource,
        PydanticBaseSettingsSource,
        PydanticBaseSettingsSource,
        PydanticBaseSettingsSource,
        YamlConfigSettingsSource,
    ]:
        # Make init_settings and env_settings higher priority than YAML
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            YamlConfigSettingsSource(settings_cls),
        )
