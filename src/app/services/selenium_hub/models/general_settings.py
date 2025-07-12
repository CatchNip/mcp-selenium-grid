"""
General settings model for the Selenium Hub service.

Aggregates core configuration options, including deployment mode, hub settings,
and references to Docker and Kubernetes settings.
"""

from typing import Any, Type

from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from app.common import getenv

from . import DeploymentMode
from .docker_settings import DockerSettings
from .kubernetes_settings import KubernetesSettings
from .selenium_settings import SeleniumHubSettings


class SeleniumHubGeneralSettings(BaseSettings):
    """
    Main configuration model for the Selenium Hub service.

    Contains deployment mode, hub settings, and nested configuration for
    Docker and Kubernetes environments.
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

    # Deployment Mode
    DEPLOYMENT_MODE: DeploymentMode = Field(default=DeploymentMode.DOCKER)

    @field_validator("DEPLOYMENT_MODE", mode="before")
    @classmethod
    def _set_deployment_mode(cls, deployment_mode: DeploymentMode, info: Any) -> DeploymentMode:
        if getenv("IS_RUNNING_IN_DOCKER").as_bool():
            return DeploymentMode.KUBERNETES
        return deployment_mode

    # Selenium Hub Settings (delegated)
    selenium_hub: SeleniumHubSettings = Field(default_factory=SeleniumHubSettings)

    # Kubernetes Settings (delegated)
    kubernetes: KubernetesSettings = Field(default_factory=KubernetesSettings)

    # Docker Settings (delegated)
    docker: DockerSettings = Field(default_factory=DockerSettings)

    # Constants for resource names
    ## Represents the K8s Deployment/Service or Docker container name for the hub
    HUB_NAME: str = Field(default="selenium-hub")
    NODE_LABEL: str = Field(default="selenium-node")
    BROWSER_LABEL: str = Field(default="browser")

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
