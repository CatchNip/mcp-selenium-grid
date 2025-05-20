"""MCP Server for managing Selenium Grid instances."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mcp import FastApiMCP

from .api import browsers
from .core.settings import settings
from .services.selenium_hub.manager import SeleniumHubManager
from .services.selenium_hub.selenium_hub import SeleniumHub

HTTP_500_INTERNAL_SERVER_ERROR = 500


def create_application() -> FastAPI:
    """Create FastAPI application for MCP."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            hub = SeleniumHub()
            await hub.ensure_hub_running()
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

    # CORS middleware
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        hub = SeleniumHub()
        is_running = await hub.ensure_hub_running()
        return {
            "status": "healthy" if is_running else "unhealthy",
            "deployment_mode": settings.DEPLOYMENT_MODE,
        }

    # Include browser management endpoints
    app.include_router(browsers.router, prefix=settings.API_V1_STR)

    # --- MCP Integration ---
    mcp = FastApiMCP(app)
    mcp.mount()  # Mounts at /mcp by default
    # ----------------------

    return app


app = create_application()
