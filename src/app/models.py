"""Response models for MCP Server."""

from enum import Enum

from pydantic import BaseModel, Field

from app.services.selenium_hub.models import DeploymentMode
from app.services.selenium_hub.models.browser import BrowserInstance


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
    browsers: dict[str, BrowserInstance] = Field(
        description="Dict of current browser instances with id as dict key"
    )
    webdriver_remote_url: str = Field(description="URL to connect to the Grid's Hub or Router")
