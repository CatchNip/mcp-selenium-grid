"""MCP Server for managing Selenium Grid."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials
from fastapi_mcp import FastApiMCP
from prometheus_client import generate_latest
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.responses import Response

from app.common.toml import load_value_from_toml
from app.dependencies import get_settings, verify_token
from app.logger import logger
from app.models import HealthCheckResponse, HealthStatus, HubStatusResponse
from app.routers.browsers import router as browsers_router
from app.routers.selenium_proxy import router as selenium_proxy_router
from app.services.selenium_hub import SeleniumHub


def create_application() -> FastAPI:
    """Create FastAPI application for MCP."""
    # Initialize settings once at the start
    settings = get_settings()
    DESCRIPTION = load_value_from_toml(["project", "description"])

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
        # Initialize browsers_instances state and its async lock
        app.state.browsers_instances = {}
        app.state.browsers_instances_lock = asyncio.Lock()

        # Initialize Selenium Hub singleton
        hub = SeleniumHub(settings)  # This will create or return the singleton instance

        # Ensure hub is running and healthy before starting the application
        try:
            # First ensure the hub container/service is running
            if not await hub.ensure_hub_running():
                raise RuntimeError("Failed to ensure Selenium Hub is running")

            # Then wait for the hub to be healthy
            if not await hub.wait_for_hub_healthy(check_interval=5):
                raise RuntimeError("Selenium Hub failed to become healthy")

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize Selenium Hub: {e!s}",
            )

        yield

        # --- Server shutdown: remove Selenium Hub resources (Docker or Kubernetes) ---
        hub.cleanup()

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=DESCRIPTION,
        lifespan=lifespan,
    )

    Instrumentator().instrument(app)

    # CORS middleware
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Prometheus metrics endpoint
    @app.get("/metrics")
    async def metrics(
        credentials: HTTPAuthorizationCredentials = Depends(verify_token),
    ) -> Response:
        return Response(generate_latest(), media_type="text/plain")

    # Health check endpoint
    @app.get("/health", response_model=HealthCheckResponse)
    async def health_check(
        credentials: HTTPAuthorizationCredentials = Depends(verify_token),
    ) -> HealthCheckResponse:
        """Get the health status of the service."""
        hub = SeleniumHub()  # This will return the singleton instance
        is_healthy = await hub.check_hub_health()
        return HealthCheckResponse(
            status=HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY,
            deployment_mode=settings.DEPLOYMENT_MODE,
        )

    # Stats endpoint
    @app.get("/stats", response_model=HubStatusResponse)
    async def get_hub_stats(
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(verify_token),
    ) -> HubStatusResponse:
        """Get Selenium Grid statistics and status."""
        hub = SeleniumHub()  # This will return the singleton instance

        # First check if the hub is running
        is_running = await hub.ensure_hub_running()

        # Then check if it's healthy
        is_healthy = await hub.check_hub_health() if is_running else False

        # Get app_state.browsers_instances using lock to ensure thread safety
        app_state = request.app.state
        async with app_state.browsers_instances_lock:
            browsers = [browser.model_dump() for browser in app_state.browsers_instances.values()]

        return HubStatusResponse(
            hub_running=is_running,
            hub_healthy=is_healthy,
            deployment_mode=settings.DEPLOYMENT_MODE,
            max_instances=settings.selenium_grid.MAX_BROWSER_INSTANCES,
            browsers=browsers,
        )

    # Include browser management endpoints
    app.include_router(browsers_router, prefix=settings.API_V1_STR)
    # Include Selenium Hub proxy endpoints
    app.include_router(selenium_proxy_router)

    # --- MCP Integration ---
    mcp = FastApiMCP(
        app,
        name="MCP Selenium Grid",
        description=DESCRIPTION,
        describe_full_response_schema=True,
        describe_all_responses=True,
    )
    MCP_HTTP_PATH = "/mcp"
    MCP_SSE_PATH = "/sse"
    mcp.mount_http(mount_path=MCP_HTTP_PATH)
    mcp.mount_sse(mount_path=MCP_SSE_PATH)

    @app.api_route("/", methods=["GET", "POST"], include_in_schema=False)
    async def root_redirect(request: Request) -> Response:
        accept: str = request.headers.get("accept", "").lower()
        method: str = request.method.upper()

        logger.info(f"Received {method=} with Accept: {accept}")

        if "text/event-stream" in accept:
            # MCP allows POST or GET here
            logger.info(f"Redirecting to SSE endpoint /sse (method={method})")
            return RedirectResponse(url="/sse")
        elif "application/json" in accept:
            # JSON RPC endpoint (usually POST)
            logger.info(f"Redirecting to HTTP JSON RPC endpoint /mcp (method={method})")
            return RedirectResponse(url="/mcp")
        else:
            logger.warning(f"Unsupported Accept header or method: method={method}, accept={accept}")
            return JSONResponse({"detail": "Unsupported Accept header or method"}, status_code=405)

    # ----------------------

    return app


app = create_application()
