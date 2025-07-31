"""
Settings model for the Selenium Hub core service.

Defines configuration options for the Selenium Hub itself, such as
host, port, and hub-specific parameters.
"""

from typing import Any, cast

from pydantic import Field, SecretStr, field_validator

from . import CustomBaseModel
from .browser import BrowserConfig, BrowserConfigs, BrowserType, ContainerResources


class SeleniumGridSettings(CustomBaseModel):
    """
    Configuration settings for the Selenium Grid core service.
    """

    HUB_IMAGE: str = "selenium/hub:latest"

    # Selenium Hub Auth
    USER: SecretStr = SecretStr("user")
    PASSWORD: SecretStr = SecretStr("CHANGE_ME")

    SELENIUM_HUB_PORT: int = Field(default=4444, frozen=True)

    @field_validator("SELENIUM_HUB_PORT", mode="after")
    @classmethod
    def _check_selenium_hub_port_is_default(cls, v: int) -> int:
        default_port = 4444
        if v != default_port:
            raise ValueError(
                f"SELENIUM_HUB_PORT cannot be set. Port {default_port} is hardcoded in the container image."
            )
        return default_port

    MAX_BROWSER_INSTANCES: int = 1
    SE_NODE_MAX_SESSIONS: int = 1
    # VNC Settings
    VNC_PASSWORD: SecretStr = SecretStr("secret")
    VNC_VIEW_ONLY: bool = True
    VNC_PORT: int = 7900

    @property
    def VNC_VIEW_ONLY_STR(self) -> str:
        return "1" if self.VNC_VIEW_ONLY else "0"

    SE_VNC_NO_PASSWORD: bool = False

    @field_validator("SE_VNC_NO_PASSWORD", mode="before")
    @classmethod
    def _compute_vnc_no_password(cls, v: bool, info: Any) -> bool:
        return not bool(info.data.get("VNC_PASSWORD"))

    @property
    def SE_VNC_NO_PASSWORD_STR(self) -> str:
        return "1" if self.SE_VNC_NO_PASSWORD else "0"

    # Browser Configurations
    BROWSER_CONFIGS: BrowserConfigs = Field(default_factory=dict)

    @field_validator("BROWSER_CONFIGS", mode="before")
    @classmethod
    def _parse_browser_configs(cls, raw: dict[str, Any]) -> BrowserConfigs:
        if not raw:
            return {}
        # If already parsed (from __init__), just return as is
        if all(isinstance(cfg, BrowserConfig) for cfg in raw.values()):
            return cast(BrowserConfigs, raw)
        # Otherwise, parse from raw dict (from YAML/env)
        configs: BrowserConfigs = {}
        for name, cfg in raw.items():
            if isinstance(cfg, BrowserConfig):
                configs[BrowserType(name)] = cfg
            else:
                if "resources" in cfg:
                    cfg["resources"] = ContainerResources(**cfg["resources"])
                configs[BrowserType(name)] = BrowserConfig(**cfg)
        return configs
