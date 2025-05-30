"""MCP Server for managing Selenium Grid instances."""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials
from fastapi_mcp import FastApiMCP
from prometheus_client import generate_latest
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.responses import Response

from app.core.settings import settings
from app.dependencies import verify_token
from app.routers import browsers
from app.routers.selenium_proxy import router as selenium_proxy_router
from app.services.selenium_hub.manager import SeleniumHubManager
from app.services.selenium_hub.selenium_hub import SeleniumHub

HTTP_500_INTERNAL_SERVER_ERROR = 500


def create_application() -> FastAPI:
    """Create FastAPI application for MCP."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
        try:
            hub = SeleniumHub()
            await hub.ensure_hub_running(
                retries=5,
                wait_seconds=2.0,
            )
        except Exception as e:
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize Selenium Hub: {e!s}",
            )
        yield
        # --- MCP Server shutdown: remove Selenium Hub resources (Docker or Kubernetes) ---
        manager = SeleniumHubManager(settings.DEPLOYMENT_MODE, settings)
        manager.cleanup()

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="MCP Server for managing Selenium Grid instances",
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
    def metrics(credentials: HTTPAuthorizationCredentials = Depends(verify_token)) -> Response:
        return Response(generate_latest(), media_type="text/plain")

    # Health check endpoint
    @app.get("/health")
    async def health_check(
        credentials: HTTPAuthorizationCredentials = Depends(verify_token),
    ) -> Dict[str, Any]:
        hub = SeleniumHub()
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
