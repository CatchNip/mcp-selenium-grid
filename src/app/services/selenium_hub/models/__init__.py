"""
Core models and base settings for the Selenium Hub service.

This module defines the deployment mode enumeration and the base settings class
used throughout the Selenium Hub configuration system.
"""

from enum import Enum
from typing import Type

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)
from typing_extensions import override


class DeploymentMode(str, Enum):
    """
    Enum representing the deployment mode for the Selenium Hub service.

    Used to distinguish between Docker and Kubernetes deployment environments.
    """

    DOCKER = "docker"
    KUBERNETES = "kubernetes"


class CustomBaseSettings(BaseSettings):
    """
    MCP Server settings.

    Inherit from this class to define configuration models that load from YAML,
    environment variables, and other sources.

    Example:
        class MySettings(CustomBaseSettings):
            MY_VAR: str = Field(default="value")
    """

    model_config = SettingsConfigDict(
        yaml_file="config.yaml",
        yaml_file_encoding="utf-8",
        alias_generator=lambda name: name.lower(),
        case_sensitive=False,
        nested_model_default_partial_update=True,
        extra="ignore",
        env_prefix="",
    )

    @override
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[
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
