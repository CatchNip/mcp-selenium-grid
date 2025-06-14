"""Core data models for MCP Server."""

from enum import Enum

from docker.utils import parse_bytes
from pydantic import BaseModel, Field, field_validator


class DeploymentMode(str, Enum):
    """Deployment mode enum for service configuration."""

    DOCKER = "docker"
    KUBERNETES = "kubernetes"


class ContainerResources(BaseModel):
    """Resource requirements for a container instance."""

    memory: str = Field(..., description="Memory limit (e.g., '512M', '1G')")
    cpu: str = Field(..., description="CPU limit (e.g., '1', '0.5', '500m')")

    @field_validator("memory")
    @classmethod
    def memory_must_be_valid_docker_memory_string(cls, value: str) -> str:
        """Validate memory format using Docker's parse_bytes."""
        try:
            parse_bytes(value)
            return value
        except Exception:
            raise ValueError("memory must be a valid Docker memory string, e.g. '1G', '512M'")

    @field_validator("cpu")
    @classmethod
    def cpu_must_be_valid_docker_cpu_string(cls, value: str) -> str:
        """Validate CPU format for Docker."""
        try:
            # Just validate it's a positive number
            cpu_value = float(value.rstrip("m"))
            if cpu_value <= 0:
                raise ValueError
            return value
        except ValueError:
            raise ValueError("CPU must be a valid Docker CPU string (e.g., '1', '0.5', '500m')")


class BrowserConfig(BaseModel):
    """Configuration for a specific browser type."""

    image: str
    resources: ContainerResources
    port: int = 444


class BrowserInstance(BaseModel):
    """Represents a single browser instance."""

    id: str
    type: str
    resources: ContainerResources

    @field_validator("id")
    @classmethod
    def id_must_be_non_empty_string(cls, value: str) -> str:
        if not value:
            raise ValueError("`id` must be a non-empty string")
        return value

    @field_validator("type")
    @classmethod
    def type_must_be_valid_browser_type(cls, value: str) -> str:
        valid_types = ["chrome", "firefox", "edge"]
        if value not in valid_types:
            raise ValueError(f"`type` must be one of {valid_types}")
        return value


# Example usage (optional)
# config = BrowserConfig(
#     image="selenium/node-chrome:latest",
#     resources=ContainerResources(memory="1G", cpu=1),
#     port=4444
# )
