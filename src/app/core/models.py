"""Core data models for MCP Server."""

from docker.utils import parse_bytes
from pydantic import BaseModel, field_validator


class ContainerResources(BaseModel):
    """Resource requirements for a container instance."""

    memory: str = "1G"
    cpu: str = "1"

    @field_validator("memory")
    @classmethod
    def memory_must_be_valid_docker_memory_string(cls, value: str) -> str:
        try:
            parse_bytes(value)
        except Exception:
            raise ValueError("memory must be a valid Docker memory string, e.g. '1G', '512M'")
        return value

    @field_validator("cpu")
    @classmethod
    def cpu_must_be_integer_string(cls, value: str) -> str:
        if not str(value).isdigit():
            raise ValueError("`cpu` must be a string of digits, e.g. '1' or '2'")
        return str(value)


class BrowserConfig(BaseModel):
    """Configuration for a specific browser type."""

    image: str
    resources: ContainerResources
    port: int = 444


# Example usage (optional)
# config = BrowserConfig(
#     image="selenium/node-chrome:latest",
#     resources=ContainerResources(memory="1G", cpu=1),
#     port=4444
# )
