"""
Settings model for Docker-based Selenium Hub deployments.

Defines configuration options specific to Docker environments, such as
network names and container-related settings.
"""

from pydantic import Field

from . import CustomBaseSettings


class DockerSettings(CustomBaseSettings):
    """
    Configuration settings for running Selenium Hub in a Docker environment.

    Includes options like the Docker network name and other Docker-specific parameters.
    """

    DOCKER_NETWORK_NAME: str = Field(default="selenium-grid")
