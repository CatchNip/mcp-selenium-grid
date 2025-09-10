import signal
from logging import getLogger

import anyio
from asgi_lifespan import LifespanManager
from fastapi.logger import logger as fastapi_logger
from fastmcp import FastMCP

from app.common.logger import logger as app_logger
from app.main import app as fastapi_app
from app.services.selenium_hub.common.logger import logger as selenium_hub_logger

from .helpers import redirect_loggers_to_stderr


def run_stdio() -> None:
    """Run FastMCP stdio server."""

    redirect_loggers_to_stderr(
        getLogger(),  # root logger
        getLogger("uvicorn.access"),
        getLogger("client"),  # kubernetes
        getLogger("urllib3"),  # kubernetes
        getLogger("kubernetes"),
        fastapi_logger,
        app_logger,
        selenium_hub_logger,
    )

    async def run_stdio_async() -> None:
        async with LifespanManager(fastapi_app, startup_timeout=60, shutdown_timeout=10):
            with anyio.CancelScope() as cancel_scope:
                with anyio.open_signal_receiver(signal.SIGTERM, signal.SIGINT) as signals:

                    async def handle_signals() -> None:
                        async for signum in signals:
                            app_logger.info(f"Received signal {signum}, shutting down...")
                            cancel_scope.cancel()
                            break

                    async def run_server() -> None:
                        try:
                            await FastMCP.from_fastapi(fastapi_app).run_async(
                                show_banner=False,
                                transport="stdio",
                            )
                        except* anyio.get_cancelled_exc_class():
                            app_logger.warning("Cancelled, shutting down...")

                        except* Exception as e:
                            app_logger.error(f"Error, shutting down...\n{e}")
                        finally:
                            cancel_scope.cancel()

                async with anyio.create_task_group() as tg:
                    tg.start_soon(handle_signals)
                    tg.start_soon(run_server)

        app_logger.info("MCP Server shutdown completed.")

    anyio.run(run_stdio_async)
