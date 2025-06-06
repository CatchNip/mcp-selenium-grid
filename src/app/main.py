"""MCP Server for managing Selenium Grid instances."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials
from fastapi_mcp import FastApiMCP
from prometheus_client import generate_latest
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.responses import Response

from app.dependencies import get_settings, verify_token
from app.routers import browsers
from app.routers.selenium_proxy import router as selenium_proxy_router
from app.services.selenium_hub.manager import SeleniumHubManager
from app.services.selenium_hub.selenium_hub import SeleniumHub


def create_application() -> FastAPI:
    """Create FastAPI application for MCP."""
    # Initialize settings once at the start
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
        # Initialize browsers_instances state and its async lock
        app.state.browsers_instances = {}
        app.state.browsers_instances_lock = asyncio.Lock()

        # Initialize Selenium Hub singleton
        # and ensure it is running before starting the application
        try:
            hub = SeleniumHub(settings)  # This will create or return the singleton instance
            await hub.ensure_hub_running(
                retries=5,
                wait_seconds=2.0,
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize Selenium Hub: {e!s}",
            )
        yield
        # --- Server shutdown: remove Selenium Hub resources (Docker or Kubernetes) ---
        manager = SeleniumHubManager(settings)
        manager.cleanup()

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="MCP Server for managing Selenium Grid instances",
        lifespan=lifespan,
        dependencies=[Depends(get_settings)],
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
    def metrics(credentials: HTTPAuthorizationCredentials = Depends(verify_token)) -> Response:
        return Response(generate_latest(), media_type="text/plain")

    # Health check endpoint
    @app.get("/health")
    async def health_check(
        credentials: HTTPAuthorizationCredentials = Depends(verify_token),
    ) -> Dict[str, Any]:
        hub = SeleniumHub()  # This will return the singleton instance
        is_running = await hub.ensure_hub_running()
        return {
            "status": "healthy" if is_running else "unhealthy",
            "deployment_mode": settings.DEPLOYMENT_MODE,
        }

    # Include browser management endpoints
    app.include_router(browsers.router, prefix=settings.API_V1_STR)
    # Include Selenium Hub proxy endpoints
    app.include_router(selenium_proxy_router)

    # --- MCP Integration ---
    mcp = FastApiMCP(app)
    mcp.mount()  # Mounts at /mcp by default
    # ----------------------

    return app


app = create_application()
