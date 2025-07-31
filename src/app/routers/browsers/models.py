"""Browser-related models for MCP Server."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from app.services.selenium_hub.models.browser import BrowserInstance, BrowserType


class BrowserResponseStatus(str, Enum):
    """Deployment mode enum for service configuration."""

    CREATED = "created"
    DELETED = "deleted"
    UNCHANGED = "unchanged"


class CreateBrowserRequest(BaseModel):
    """Browser request model."""

    count: int = Field(default=1, gt=0, description="Number of browser instances to create")
    browser_type: BrowserType = Field(
        default=BrowserType.CHROME, description="Type of browser to create"
    )


class CreateBrowserResponse(BaseModel):
    """Browser response model."""

    browsers: list[BrowserInstance]
    hub_url: str
    status: BrowserResponseStatus
    message: str | None


class DeleteBrowserRequest(BaseModel):
    """Browser request model."""

    browsers_ids: list[str]


class DeleteBrowserResponse(BaseModel):
    """Browser response model."""

    browsers_ids: list[str]
    status: Literal[BrowserResponseStatus.DELETED, BrowserResponseStatus.UNCHANGED]
    message: str | None = "Browsers deleted successfully."
