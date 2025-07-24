"""
General settings model for the Selenium Hub service.

Aggregates core configuration options, including deployment mode, hub settings,
and references to Docker and Kubernetes settings.
"""

from typing import Any

from pydantic import Field, PrivateAttr, field_validator

from app.common import getenv

from . import CustomBaseSettings, DeploymentMode
from .docker_settings import DockerSettings
from .kubernetes_settings import KubernetesSettings
from .selenium_settings import SeleniumGridSettings


class SeleniumHubGeneralSettings(CustomBaseSettings):
    """
    Main configuration model for the Selenium Hub service.

    Contains deployment mode, hub settings, and nested configuration for
    Docker and Kubernetes environments.
    """

    # Private
    _keep_original_keys: list[str] = PrivateAttr(
        default_factory=lambda: ["selenium_grid", "kubernetes", "docker"]
    )

    # Deployment Mode
    DEPLOYMENT_MODE: DeploymentMode = DeploymentMode.DOCKER

    @field_validator("DEPLOYMENT_MODE", mode="before")
    @classmethod
    def _set_deployment_mode(cls, deployment_mode: DeploymentMode, info: Any) -> DeploymentMode:
        if getenv("IS_RUNNING_IN_DOCKER").as_bool():
            return DeploymentMode.KUBERNETES
        return deployment_mode

    # Selenium Grid Settings (delegated)
    selenium_grid: SeleniumGridSettings = Field(default_factory=SeleniumGridSettings)

    # Kubernetes Settings (delegated)
    kubernetes: KubernetesSettings = Field(default_factory=KubernetesSettings)

    # Docker Settings (delegated)
    docker: DockerSettings = Field(default_factory=DockerSettings)

    # Constants for resource names
    ## Represents the K8s Deployment/Service or Docker container name for the hub
    HUB_NAME: str = "selenium-hub"
    NODE_LABEL: str = "selenium-node"
    BROWSER_LABEL: str = "browser"
