"""Browser-related models for MCP Server."""

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from app.core.models import BrowserInstance


class BrowserResponseStatus(str, Enum):
    """Deployment mode enum for service configuration."""

    CREATED = "created"
    DELETED = "deleted"
    UNCHANGED = "unchanged"


class CreateBrowserRequest(BaseModel):
    """Browser request model."""

    count: int = Field(default=1, gt=0, description="Number of browser instances to create")
    browser_type: str = Field(
        default="chrome", pattern="^(chrome|firefox|edge)$", description="Type of browser to create"
    )


class CreateBrowserResponse(BaseModel):
    """Browser response model."""

    browsers: List[BrowserInstance]
    hub_url: str
    status: BrowserResponseStatus
    message: Optional[str]


class DeleteBrowserRequest(BaseModel):
    """Browser request model."""

    browsers_ids: List[str]


class DeleteBrowserResponse(BaseModel):
    """Browser response model."""

    browsers_ids: List[str]
    status: Literal[BrowserResponseStatus.DELETED, BrowserResponseStatus.UNCHANGED]
    message: Optional[str] = "Browsers deleted successfully."
