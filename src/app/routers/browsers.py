"""Browser management endpoints for MCP Server."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBasicCredentials
from pydantic import BaseModel, Field

from app.core.settings import settings
from app.dependencies import verify_token
from app.services.selenium_hub import SeleniumHub

router = APIRouter()


class BrowserRequest(BaseModel):
    """Browser request model."""

    count: int = Field(default=1, gt=0, description="Number of browser instances to create")
    browser_type: str = Field(
        default="chrome", pattern="^(chrome|firefox|edge)$", description="Type of browser to create"
    )


class BrowserResponse(BaseModel):
    """Browser response model."""

    browser_ids: List[str]
    hub_url: str
    status: str = "created"


HTTP_201_CREATED = 201
HTTP_400_BAD_REQUEST = 400
HTTP_500_INTERNAL_SERVER_ERROR = 500


@router.post(
    "/browsers",
    response_model=BrowserResponse,
    status_code=HTTP_201_CREATED,
)
async def create_browsers(
    request: BrowserRequest, credentials: HTTPBasicCredentials = Depends(verify_token)
) -> BrowserResponse:
    """Create browser instances in Selenium Grid."""
    if settings.MAX_BROWSER_INSTANCES and request.count > settings.MAX_BROWSER_INSTANCES:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Maximum allowed browser instances is {settings.MAX_BROWSER_INSTANCES}",
        )

    hub = SeleniumHub()
    try:
        browser_ids = await hub.create_browsers(
            count=request.count, browser_type=request.browser_type
        )
    except Exception as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return BrowserResponse(browser_ids=browser_ids, hub_url=settings.SELENIUM_HUB_BASE_URL)


@router.get(
    "/browsers/status",
    response_model=dict,
)
async def get_hub_status(credentials: HTTPBasicCredentials = Depends(verify_token)) -> dict:
    """Get Selenium Grid status."""
    hub = SeleniumHub()
    is_running = await hub.ensure_hub_running()

    return {
        "hub_running": is_running,
        "deployment_mode": settings.DEPLOYMENT_MODE,
        "max_instances": settings.MAX_BROWSER_INSTANCES,
    }
