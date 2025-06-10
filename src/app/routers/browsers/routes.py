"""Browser management endpoints for MCP Server."""

from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

from app.core.models import BrowserInstance
from app.core.settings import Settings
from app.dependencies import get_settings, verify_token
from app.routers.browsers.models import BrowserRequest, BrowserResponse
from app.services.selenium_hub import SeleniumHub


class BrowserStatusResponse(BaseModel):
    """Browser status response model."""

    status: str
    details: Dict[str, Any]


class BrowserHealthResponse(BaseModel):
    """Browser health response model."""

    cpu_usage: float
    memory_usage: float


class BrowserDeleteResponse(BaseModel):
    """Browser delete response model."""

    success: bool
    message: str


router = APIRouter(prefix="/browsers", tags=["Browsers"])


@router.post(
    "/create",
    response_model=BrowserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_browsers(
    fastapi_request: Request,
    request: BrowserRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: HTTPAuthorizationCredentials = Depends(verify_token),
) -> BrowserResponse:
    """Create browser instances in Selenium Grid."""
    if settings.MAX_BROWSER_INSTANCES and request.count > settings.MAX_BROWSER_INSTANCES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum allowed browser instances is {settings.MAX_BROWSER_INSTANCES}",
        )

    # Check if requested browser type is available in configs before proceeding
    if request.browser_type not in settings.BROWSER_CONFIGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported browser type: {request.browser_type}. Available: {list(settings.BROWSER_CONFIGS.keys())}",
        )

    hub = SeleniumHub()  # This will return the singleton instance
    try:
        browser_ids = await hub.create_browsers(
            count=request.count,
            browser_type=request.browser_type,
        )
        browser_config = settings.BROWSER_CONFIGS[request.browser_type]
        browsers = [
            BrowserInstance(id=bid, type=request.browser_type, resources=browser_config.resources)
            for bid in browser_ids
        ]
        app_state = fastapi_request.app.state
        async with app_state.browsers_instances_lock:
            for browser in browsers:
                app_state.browsers_instances[browser.id] = browser
    except Exception as e:
        # Log the error and current browser configs for diagnostics
        import logging

        logging.error(
            f"Exception in create_browsers: {e}. BROWSER_CONFIGS: {settings.BROWSER_CONFIGS}"
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return BrowserResponse(browsers=browsers, hub_url=settings.SELENIUM_HUB_BASE_URL_DYNAMIC)


@router.delete(
    "/{browser_id}",
    response_model=BrowserDeleteResponse,
)
async def delete_browser(
    browser_id: str,
    fastapi_request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: HTTPAuthorizationCredentials = Depends(verify_token),
) -> BrowserDeleteResponse:
    """Delete a specific browser instance."""
    hub = SeleniumHub()
    deleted_ids = await hub.delete_browsers([browser_id])
    success = browser_id in deleted_ids

    # Remove from app state if deletion was successful
    if success:
        app_state = fastapi_request.app.state
        async with app_state.browsers_instances_lock:
            app_state.browsers_instances.pop(browser_id, None)

    return BrowserDeleteResponse(
        success=success,
        message="Browser deleted successfully" if success else "Failed to delete browser",
    )
