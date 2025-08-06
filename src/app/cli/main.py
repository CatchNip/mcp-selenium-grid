from importlib.metadata import version as metadata_version
from typing import Any, Callable, cast

from fastapi_cli.cli import dev, run
from typer import Exit, Option, Typer, echo

from .helm.main import create_application as create_helm_app
from .utils import with_app_path

DOC_TITLE = "[bold green_yellow]MCP Selenium Grid CLI[/bold green_yellow] 🚀"
DOC_DESC = """
[pale_turquoise1]Model Context Protocol (MCP) server that enables AI Agents to request
and manage Selenium browser instances through a secure API.[/pale_turquoise1]

[italic gold1]Perfect for your automated browser testing needs![/italic gold1]

[link=https://github.com/Falamarcao/mcp-selenium-grid]https://github.com/Falamarcao/mcp-selenium-grid[/link]
"""


def version_callback(value: bool) -> None:
    if value:
        echo(f"mcp-selenium-grid v{metadata_version('mcp-selenium-grid')}")
        raise Exit()


def create_application() -> Typer:
    app = Typer(
        name="mcp-selenium-grid",
        help=f"{DOC_TITLE}\n{DOC_DESC}",
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
            help="Show the version and exit",
            is_eager=True,
            callback=version_callback,
        ),
    ) -> None:
        """Main CLI callback (used only to hook version flag)."""

    # ── FastAPI Commands ──
    fastapi_cli = Typer(help="Custom FastAPI CLI with limited commands.")

    for name, cmd, desc in [
        ("dev", dev, "Run the MCP Server in [bright_green]development[/bright_green] mode"),
        ("run", run, "Run the MCP Server in [bright_green]production[/bright_green] mode"),
    ]:
        fastapi_cli.command(name=name, help=desc)(with_app_path(cast(Callable[..., Any], cmd)))

    app.add_typer(fastapi_cli, name="server", help="Run MCP FastAPI server", no_args_is_help=True)

    # ── Helm Commands ──
    try:
        helm_app = create_helm_app()
        app.add_typer(
            helm_app,
            name="helm",
            help=f"{DOC_TITLE}\n[pale_turquoise1]Manage Kubernetes deployments with Helm ☸️[/pale_turquoise1]",
            no_args_is_help=True,
        )
    except ImportError:
        pass  # Helm optional

    return app


app = create_application()
