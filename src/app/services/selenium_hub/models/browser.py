"""
Data models for browser configuration and capabilities.

Defines schemas for representing browser types, versions, and capabilities
used by the Selenium Hub for browser management and orchestration.
"""

from enum import Enum

from docker.utils import parse_bytes
from pydantic import BaseModel, Field, field_validator


class ContainerResources(BaseModel):
    """Resource requirements for a container instance."""

    memory: str = Field(..., description="Memory limit (e.g., '512M', '1G')")
    cpu: str = Field(..., description="CPU limit (e.g., '1', '0.5', '500m')")

    @field_validator("memory")
    @classmethod
    def memory_must_be_valid_docker_memory_string(cls, value: str) -> str:
        try:
            parse_bytes(value)
            return value
        except Exception:
            raise ValueError("memory must be a valid Docker memory string, e.g. '1G', '512M'")

    @field_validator("cpu")
    @classmethod
    def cpu_must_be_valid_docker_cpu_string(cls, value: str) -> str:
        try:
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


class BrowserType(Enum):
    CHROME = "chrome"
    UNDETECTED_CHROME = "undetected-chrome"
    FIREFOX = "firefox"
    EDGE = "edge"

    def __str__(self) -> str:
        return f"browser-{self.value}"


type BrowserConfigs = dict[BrowserType, BrowserConfig]


class BrowserInstance(BaseModel):
    """Represents a single browser instance."""

    id: str
    type: BrowserType
    resources: ContainerResources

    @field_validator("id")
    @classmethod
    def id_must_be_non_empty_string(cls, value: str) -> str:
        if not value:
            raise ValueError("`id` must be a non-empty string")
        return value
