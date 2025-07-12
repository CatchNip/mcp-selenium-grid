"""Response models for MCP Server."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.services.selenium_hub.models import DeploymentMode


class HealthStatus(str, Enum):
    """Health status enum for service health checks."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class HealthCheckResponse(BaseModel):
    """Health check response model."""

    status: HealthStatus = Field(
        description="Current health status of the service",
        examples=[HealthStatus.HEALTHY, HealthStatus.UNHEALTHY],
    )
    deployment_mode: DeploymentMode = Field(
        description="Current deployment mode",
        examples=[DeploymentMode.DOCKER, DeploymentMode.KUBERNETES],
    )


class HubStatusResponse(BaseModel):
    """Hub status response model."""

    hub_running: bool = Field(description="Whether the hub container/service is running")
    hub_healthy: bool = Field(description="Whether the hub is healthy and responding to requests")
    deployment_mode: DeploymentMode = Field(
        description="Current deployment mode",
        examples=[DeploymentMode.DOCKER, DeploymentMode.KUBERNETES],
    )
    max_instances: int = Field(description="Maximum allowed browser instances")
    browsers: list[dict[str, Any]] = Field(description="List of current browser instances")
