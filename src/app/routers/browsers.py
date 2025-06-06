"""Browser management endpoints for MCP Server."""

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from app.core.models import BrowserInstance
from app.core.settings import Settings
from app.dependencies import verify_token
from app.services.selenium_hub import SeleniumHub

router = APIRouter(prefix="/browsers", tags=["Browsers"])


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


class HubStatusResponse(BaseModel):
    hub_running: bool
    deployment_mode: str
    max_instances: int
    browsers: list[dict[str, Any]]  # serialized BrowserInstance


@router.post(
    "/create",
    response_model=BrowserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_browsers(
    fastapi_request: Request,
    request: BrowserRequest,
    settings: Settings,
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


@router.get(
    "/status",
    response_model=HubStatusResponse,
)
async def get_hub_status(
    fastapi_request: Request,
    settings: Settings,
    credentials: HTTPAuthorizationCredentials = Depends(verify_token),
) -> HubStatusResponse:
    """Get Selenium Grid status."""
    hub = SeleniumHub()  # This will return the singleton instance
    is_running = await hub.ensure_hub_running(
        retries=settings.K8S_MAX_RETRIES if settings.DEPLOYMENT_MODE == "kubernetes" else 2,
        wait_seconds=(
            settings.K8S_RETRY_DELAY_SECONDS if settings.DEPLOYMENT_MODE == "kubernetes" else 0.0
        ),
    )

    # Get app_state.browsers_instances using lock to ensure thread safety
    app_state = fastapi_request.app.state
    async with app_state.browsers_instances_lock:
        browsers = [browser.model_dump() for browser in app_state.browsers_instances.values()]

    return HubStatusResponse(
        hub_running=is_running,
        deployment_mode=settings.DEPLOYMENT_MODE,
        max_instances=settings.MAX_BROWSER_INSTANCES,
        browsers=browsers,
    )
