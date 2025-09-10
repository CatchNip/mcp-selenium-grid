from importlib.metadata import version as metadata_version
from os import environ
from typing import Annotated, Any
from warnings import filterwarnings

from fastapi_cli.cli import _run
from typer import Exit, Option, Typer, echo

from app.common.constants import STDIO_ENV_NAME
from app.common.getenv import getenv
from app.core.settings import Settings
from app.services.selenium_hub import SeleniumHub
from app.services.selenium_hub.common.logger import logger as selenium_hub_logger
from app.services.selenium_hub.models import DeploymentMode

from .constants import CLI_DESC, CLI_TITLE, FASTAPI_MODULE_PATH, SERVER_SHORT_HELP
from .helm.main import create_application as create_helm_app
from .helpers import InfoOnlyFilter
from .stdio import run_stdio


def version_callback(value: bool) -> None:
    if value:
        echo(f"mcp-selenium-grid v{metadata_version('mcp-selenium-grid')}")
        raise Exit()


def create_application() -> Typer:
    app = Typer(
        name="mcp-selenium-grid",
        help=f"{CLI_TITLE}\n{CLI_DESC}",
        rich_help_panel="main",
        rich_markup_mode="rich",
        add_completion=False,
        no_args_is_help=True,
        pretty_exceptions_show_locals=False,
    )

    @app.callback()
    def main(
        version: bool = Option(
            False,
            "--version",
            "-v",
            help="Show the version and exit.",
            is_eager=True,
            callback=version_callback,
        ),
    ) -> None:
        """Main CLI callback (used only to hook version flag)."""

    @app.command(
        name="clean",
        help="[yellow]Cleanup resources, e.g. shutdown containers.[/yellow]",
    )
    def clean(
        deployment_mode: Annotated[
            DeploymentMode,
            Option(
                "--deployment-mode",
                "-d",
                help="Deployment Mode",
            ),
        ] = DeploymentMode.DOCKER,
    ) -> None:
        filterwarnings("ignore")
        selenium_hub_logger.handlers[0].addFilter(InfoOnlyFilter())

        SeleniumHub(Settings(DEPLOYMENT_MODE=deployment_mode)).cleanup()

    # ── FastAPI Commands ──
    fastapi_cli = Typer(help="Custom FastAPI CLI with limited commands.")

    @fastapi_cli.command(
        name="run", help="Run the MCP Server in [bright_green]production[/bright_green] mode"
    )
    def run(  # noqa: PLR0913
        *,
        host: Annotated[
            str,
            Option(
                help="The host to serve on. For local development in localhost use [blue]127.0.0.1[/blue]. To enable public access, e.g. in a container, use all the IP addresses available with [blue]0.0.0.0[/blue]."
            ),
        ] = "0.0.0.0",  # noqa: S104
        port: Annotated[
            int,
            Option(
                help="The port to serve on. You would normally have a termination proxy on top (another program) handling HTTPS on port [blue]443[/blue] and HTTP on port [blue]80[/blue], transferring the communication to your app."
            ),
        ] = 8000,
        reload: Annotated[
            bool,
            Option(
                help="Enable auto-reload of the server when (code) files change. This is [bold]resource intensive[/bold], use it only during development."
            ),
        ] = False,
        workers: Annotated[
            int | None,
            Option(
                help="Use multiple worker processes. Mutually exclusive with the --reload flag.",
            ),
        ] = None,
        proxy_headers: Annotated[
            bool,
            Option(
                help="Enable/Disable X-Forwarded-Proto, X-Forwarded-For, X-Forwarded-Port to populate remote address info."
            ),
        ] = True,
        stdio: Annotated[
            bool,
            Option(
                help="Run the server using standard input/output instead of HTTP/SSE. Only protocol data is sent to stdout; logs should go to stderr."
            ),
        ] = False,
    ) -> Any:
        environ[STDIO_ENV_NAME] = str(stdio).lower()

        kwargs: dict[str, Any] = dict(
            path=FASTAPI_MODULE_PATH,
            host=host,
            port=port,
            reload=reload,
            workers=workers,
            root_path="",
            app=None,
            command="run",
            proxy_headers=proxy_headers,
        )

        run_stdio() if getenv(STDIO_ENV_NAME).as_bool() else _run(**kwargs)

    @fastapi_cli.command(
        name="dev", help="Run the MCP Server in [bright_green]development[/bright_green] mode"
    )
    def dev(
        *,
        host: Annotated[
            str,
            Option(
                help="The host to serve on. For local development in localhost use [blue]127.0.0.1[/blue]. To enable public access, e.g. in a container, use all the IP addresses available with [blue]0.0.0.0[/blue]."
            ),
        ] = "127.0.0.1",
        port: Annotated[
            int,
            Option(
                help="The port to serve on. You would normally have a termination proxy on top (another program) handling HTTPS on port [blue]443[/blue] and HTTP on port [blue]80[/blue], transferring the communication to your app."
            ),
        ] = 8000,
        reload: Annotated[
            bool,
            Option(
                help="Enable auto-reload of the server when (code) files change. This is [bold]resource intensive[/bold], use it only during development."
            ),
        ] = True,
        proxy_headers: Annotated[
            bool,
            Option(
                help="Enable/Disable X-Forwarded-Proto, X-Forwarded-For, X-Forwarded-Port to populate remote address info."
            ),
        ] = True,
        stdio: Annotated[
            bool,
            Option(
                help="Run the server using standard input/output instead of HTTP/SSE. Only protocol data is sent to stdout; logs should go to stderr."
            ),
        ] = False,
    ) -> Any:
        environ[STDIO_ENV_NAME] = str(stdio).lower()

        kwargs: dict[str, Any] = dict(
            path=FASTAPI_MODULE_PATH,
            host=host,
            port=port,
            reload=reload,
            workers=None,
            root_path="",
            app=None,
            command="dev",
            proxy_headers=proxy_headers,
        )

        run_stdio() if getenv(STDIO_ENV_NAME).as_bool() else _run(**kwargs)

    app.add_typer(
        fastapi_cli,
        name="server",
        help=f"{CLI_TITLE} - {SERVER_SHORT_HELP}",
        short_help=SERVER_SHORT_HELP,
        no_args_is_help=True,
    )

    # ── Helm Commands ──
    try:
        helm_app = create_helm_app()
        app.add_typer(
            helm_app,
            name="helm",
            no_args_is_help=True,
        )
    except ImportError:
        pass  # Helm optional

    return app


app = create_application()
