"""
General settings model for the Selenium Hub service.

Aggregates core configuration options, including deployment mode, hub settings,
and references to Docker and Kubernetes settings.
"""

from typing import Any

from pydantic import Field, field_validator

from app.common import getenv

from . import CustomBaseSettings, DeploymentMode
from .docker_settings import DockerSettings
from .kubernetes_settings import KubernetesSettings
from .selenium_settings import SeleniumHubSettings


class SeleniumHubGeneralSettings(CustomBaseSettings):
    """
    Main configuration model for the Selenium Hub service.

    Contains deployment mode, hub settings, and nested configuration for
    Docker and Kubernetes environments.
    """

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

    # Kubernetes Settings (delegated)
    docker: DockerSettings = Field(default_factory=DockerSettings)

    # Constants for resource names
    ## Represents the K8s Deployment/Service or Docker container name for the hub
    HUB_NAME: str = Field(default="selenium-hub")
    NODE_LABEL: str = Field(default="selenium-node")
    BROWSER_LABEL: str = Field(default="browser")
