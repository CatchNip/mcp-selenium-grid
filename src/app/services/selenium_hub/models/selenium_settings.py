"""
Settings model for the Selenium Hub core service.

Defines configuration options for the Selenium Hub itself, such as
host, port, and hub-specific parameters.
"""

from typing import Any

from pydantic import Field, SecretStr, field_validator

from . import CustomBaseSettings
from .browser import BrowserConfig, ContainerResources


class SeleniumHubSettings(CustomBaseSettings):
    """
    Configuration settings for the Selenium Hub core service.

    Includes host, port, and other hub-specific options.
    """

    # Selenium Hub Auth
    SELENIUM_HUB_USER: SecretStr = Field(default=SecretStr("user"))
    SELENIUM_HUB_PASSWORD: SecretStr = Field(default=SecretStr("CHANGE_ME"))

    # Selenium Settings
    SELENIUM_HUB_PORT: int = Field(default=4444, frozen=True)

    @field_validator("SELENIUM_HUB_PORT")
    @classmethod
    def _check_selenium_hub_port_is_default(cls, v: int) -> int:
        default_port = 4444
        if v != default_port:
            raise ValueError(
                f"SELENIUM_HUB_PORT cannot be set. Port {default_port} is hardcoded in the container image."
            )
        return default_port

    MAX_BROWSER_INSTANCES: int = Field(default=1)
    SE_NODE_MAX_SESSIONS: int = Field(default=1)

    # VNC Settings
    SELENIUM_HUB_VNC_PASSWORD: SecretStr = Field(default=SecretStr("secret"))
    SELENIUM_HUB_VNC_PORT: int = Field(default=7900)
    SELENIUM_HUB_VNC_VIEW_ONLY: bool = Field(default=True)

    @property
    def SELENIUM_HUB_VNC_VIEW_ONLY_STR(self) -> str:
        return "1" if self.SELENIUM_HUB_VNC_VIEW_ONLY else "0"

    SE_VNC_NO_PASSWORD: bool = Field(default=False)

    @field_validator("SE_VNC_NO_PASSWORD", mode="before")
    @classmethod
    def _compute_vnc_no_password(cls, v: bool, info: Any) -> bool:
        return not bool(info.data.get("SELENIUM_HUB_VNC_PASSWORD"))

    @property
    def SE_VNC_NO_PASSWORD_STR(self) -> str:
        return "1" if self.SE_VNC_NO_PASSWORD else "0"

    # Browser Configurations
    BROWSER_CONFIGS: dict[str, BrowserConfig] = Field(default_factory=dict)

    @field_validator("BROWSER_CONFIGS", mode="before")
    @classmethod
    def _parse_browser_configs(cls, raw: dict[str, Any]) -> dict[str, BrowserConfig]:
        configs: dict[str, BrowserConfig] = {}
        for name, cfg in (raw or {}).items():
            if "resources" in cfg:
                cfg["resources"] = ContainerResources(**cfg["resources"])
            configs[name] = BrowserConfig(**cfg)
        return configs
