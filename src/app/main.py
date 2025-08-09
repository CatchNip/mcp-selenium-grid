"""MCP Server for managing Selenium Grid."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator
from urllib.parse import urljoin

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials
from fastapi_mcp import AuthConfig, FastApiMCP
from prometheus_client import generate_latest
from prometheus_fastapi_instrumentator import Instrumentator

from app.common.fastapi_mcp import handle_fastapi_request
from app.common.logger import logger
from app.common.toml import load_value_from_toml
from app.dependencies import get_settings, verify_token
from app.models import HealthCheckResponse, HealthStatus, HubStatusResponse
from app.routers.browsers import router as browsers_router
from app.routers.selenium_proxy import router as selenium_proxy_router
from app.services.selenium_hub import SeleniumHub

DESCRIPTION = load_value_from_toml(["project", "description"])
SETTINGS = get_settings()
MCP_HTTP_PATH = "/mcp"
MCP_SSE_PATH = "/sse"


def create_application() -> FastAPI:
    """Create FastAPI application for MCP."""
    # Initialize settings once at the start

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
        # Initialize browsers_instances state and its async lock
        app.state.browsers_instances = {}
        app.state.browsers_instances_lock = asyncio.Lock()

        # Initialize Selenium Hub singleton
        hub = SeleniumHub(SETTINGS)  # This will create or return the singleton instance

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
        title=SETTINGS.PROJECT_NAME,
        version=SETTINGS.VERSION,
        description=DESCRIPTION,
        lifespan=lifespan,
    )

    Instrumentator().instrument(app)

    # CORS middleware
    if SETTINGS.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in SETTINGS.BACKEND_CORS_ORIGINS],
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
            deployment_mode=SETTINGS.DEPLOYMENT_MODE,
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
            deployment_mode=SETTINGS.DEPLOYMENT_MODE,
            max_instances=SETTINGS.selenium_grid.MAX_BROWSER_INSTANCES,
            browsers=browsers,
        )

    # Include browser management endpoints
    app.include_router(browsers_router, prefix=SETTINGS.API_V1_STR)
    # Include Selenium Hub proxy endpoints
    app.include_router(selenium_proxy_router)

    # --- MCP Integration ---
    mcp = FastApiMCP(
        app,
        name="MCP Selenium Grid",
        description=DESCRIPTION,
        describe_full_response_schema=True,
        describe_all_responses=True,
        auth_config=AuthConfig(
            dependencies=[Depends(verify_token)],
        ),
    )
    mcp.mount_http(mount_path=MCP_HTTP_PATH)
    mcp.mount_sse(mount_path=MCP_SSE_PATH)

    @app.api_route("/", methods=["GET", "POST"])
    async def root_proxy(
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(verify_token),
    ) -> Response:
        """
        FastApiMCP does not allow mounting directly on the root path `/`.
        However, MCP clients (especially when using uvx) expect to connect on `/`.
        This proxy handles requests on `/` and internally routes them to the proper MCP endpoints.
        For SSE (Server-Sent Events) and HTTP transports, it redirects or proxies requests accordingly,
        ensuring compatibility with client expectations without violating FastApiMCP mounting rules.
        """

        accept = request.headers.get("accept", "").lower()
        method = request.method.upper()
        session_manager = mcp._http_transport  # noqa: SLF001

        if "text/event-stream" in accept:
            if method == "GET":
                return await handle_fastapi_request(
                    name="SSE",
                    request=request,
                    target_path=MCP_SSE_PATH,
                    method=method,
                    session_manager=session_manager,
                )
            elif method == "POST":
                return await handle_fastapi_request(
                    name="SSE messages",
                    request=request,
                    target_path=urljoin(MCP_SSE_PATH, "/messages"),
                    method=method,
                    session_manager=session_manager,
                )
            else:
                return JSONResponse({"detail": "Unsupported method"}, status_code=405)
        elif "application/json" in accept:
            return await handle_fastapi_request(
                name="HTTP",
                request=request,
                target_path=MCP_HTTP_PATH,
                method=method,
                session_manager=session_manager,
            )
        else:
            logger.warning(f"Unsupported Accept header or method: method={method}, accept={accept}")
            return JSONResponse({"detail": "Unsupported Accept header or method"}, status_code=405)

    # ----------------------

    return app


app = create_application()
