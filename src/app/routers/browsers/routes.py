"""Browser management endpoints for MCP Server."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from app.core.settings import Settings
from app.dependencies import get_settings, verify_token
from app.logger import logger
from app.services.selenium_hub import SeleniumHub
from app.services.selenium_hub.models.browser import BrowserConfig, BrowserInstance

from .models import (
    BrowserResponseStatus,
    CreateBrowserRequest,
    CreateBrowserResponse,
    DeleteBrowserRequest,
    DeleteBrowserResponse,
)

router = APIRouter(prefix="/browsers", tags=["Browsers"])


@router.post(
    "/create",
    response_model=CreateBrowserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_browsers(
    fastapi_request: Request,
    request: CreateBrowserRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: HTTPAuthorizationCredentials = Depends(verify_token),
) -> CreateBrowserResponse:
    """Create browser instances in Selenium Grid."""
    if (
        settings.selenium_grid.MAX_BROWSER_INSTANCES
        and request.count > settings.selenium_grid.MAX_BROWSER_INSTANCES
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum allowed browser instances is {settings.selenium_grid.MAX_BROWSER_INSTANCES}",
        )

    # Check if requested browser type is available in configs before proceeding
    if request.browser_type not in settings.selenium_grid.BROWSER_CONFIGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported browser type: {request.browser_type}. Available: {list(settings.selenium_grid.BROWSER_CONFIGS.keys())}",
        )

    hub = SeleniumHub()  # This will return the singleton instance
    try:
        browser_ids: list[str] = await hub.create_browsers(
            count=request.count,
            browser_type=request.browser_type,
        )
        browser_config: BrowserConfig = settings.selenium_grid.BROWSER_CONFIGS[request.browser_type]
        browsers: list[BrowserInstance] = [
            BrowserInstance(id=bid, type=request.browser_type, resources=browser_config.resources)
            for bid in browser_ids
        ]
        app_state = fastapi_request.app.state
        async with app_state.browsers_instances_lock:
            for browser in browsers:
                app_state.browsers_instances[browser.id] = browser
    except Exception as e:
        # Log the error and current browser configs for diagnostics
        logger.error(
            f"Exception in create_browsers: {e}. BROWSER_CONFIGS: {settings.selenium_grid.BROWSER_CONFIGS}"
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return CreateBrowserResponse(
        browsers=browsers,
        hub_url=hub.URL,
        status=BrowserResponseStatus.CREATED,
        message="Browser(s) created successfully.",
    )


@router.post(
    "/delete",
    response_model=DeleteBrowserResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_browsers(
    request: DeleteBrowserRequest,
    fastapi_request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(verify_token),
) -> DeleteBrowserResponse:
    """Delete browser instances."""
    if not request.browsers_ids:
        return DeleteBrowserResponse(
            browsers_ids=[],
            status=BrowserResponseStatus.UNCHANGED,
            message="No Browsers to delete.",
        )

    hub = SeleniumHub()
    deleted_ids: list[str] = await hub.delete_browsers(request.browsers_ids)

    # Remove from app state if deletion was successful
    count_deleted_ids = len(deleted_ids)
    if count_deleted_ids:
        app_state = fastapi_request.app.state
        async with app_state.browsers_instances_lock:
            for id in deleted_ids:
                app_state.browsers_instances.pop(id, None)

        messages: list[str] = [f"{count_deleted_ids} browser(s) deleted successfully."]

        not_foud: int = len(request.browsers_ids) - count_deleted_ids
        if not_foud > 0:
            messages.append(f"{not_foud} browser(s) not found.")

        return DeleteBrowserResponse(
            browsers_ids=deleted_ids,
            status=BrowserResponseStatus.DELETED,
            message=" ".join(messages),
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No browsers found to delete in the list: {request.browsers_ids}",
        )
