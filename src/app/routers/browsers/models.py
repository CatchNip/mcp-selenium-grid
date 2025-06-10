"""Browser-related models for MCP Server."""

from typing import List

from pydantic import BaseModel, Field

from app.core.models import BrowserInstance


class BrowserRequest(BaseModel):
    """Browser request model."""

    count: int = Field(default=1, gt=0, description="Number of browser instances to create")
    browser_type: str = Field(
        default="chrome", pattern="^(chrome|firefox|edge)$", description="Type of browser to create"
    )


class BrowserResponse(BaseModel):
    """Browser response model."""

    browsers: List[BrowserInstance]
    hub_url: str
    status: str = "created"
