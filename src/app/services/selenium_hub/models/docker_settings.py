"""
Settings model for Docker-based Selenium Hub deployments.

Defines configuration options specific to Docker environments, such as
network names and container-related settings.
"""

from . import CustomBaseModel


class DockerSettings(CustomBaseModel):
    """
    Configuration settings for running Selenium Hub in a Docker environment.

    Includes options like the Docker network name and other Docker-specific parameters.
    """

    DOCKER_NETWORK_NAME: str = "selenium-grid"
