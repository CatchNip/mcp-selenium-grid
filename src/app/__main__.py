"""Entry point for running the MCP Selenium Grid server."""

from fastapi_cli.cli import dev, run
from scripts.helm.main import create_application as create_helm_app
from typer import Typer


def create_application() -> Typer:
    __doc__title__ = """
    [bold green_yellow]MCP Selenium Grid Server[/bold green_yellow] 🚀
    Run the [turquoise4]MCP Server/REST API[/turquoise4] or manage [turquoise4]Kubernetes[/turquoise4] deployments.
    """
    __doc__ = (
        __doc__title__
        + """

    [pale_turquoise1]Model Context Protocol (MCP) server that enables AI Agents to request
    and manage Selenium browser instances through a secure API.[/pale_turquoise1]

    [italic gold1]Perfect for your automated browser testing needs![/italic gold1]

    Read more in the docs:
    [link=https://github.com/Falamarcao/mcp-selenium-grid]https://github.com/Falamarcao/mcp-selenium-grid[/link]
    """
    )

    app = Typer(
        name="mcp-selenium-grid",
        help=__doc__,
        rich_help_panel="main",
        rich_markup_mode="rich",
        add_completion=False,
        no_args_is_help=True,  # optional quality of life
        pretty_exceptions_show_locals=False,
    )

    custom_fastapi_cli = Typer(help="Custom FastAPI CLI with limited commands.")

    # Add specific commands
    custom_fastapi_cli.command(
        name="dev",
        help="Run a Selenium Grid MCP Server in [bright_green]development[/bright_green] mode",
    )(dev)
    custom_fastapi_cli.command(
        name="run",
        help="Run a Selenium Grid MCP Server in [bright_green]production[/bright_green] mode",
    )(run)

    app.add_typer(
        custom_fastapi_cli,
        name="server",
        help=__doc__,
    )

    # Import and add the Helm subcommand
    try:
        __doc__helm = (
            __doc__title__
            + """
        
        [pale_turquoise1]Manage Kubernetes deployments with Helm ☸️[/pale_turquoise1]
        [italic gold1]Prepare the kubernetes cluster to run MCP Selenium Grid![/italic gold1]
        """
        )
        # Create the Helm app and add it as a subcommand group
        helm_app = create_helm_app()
        app.add_typer(helm_app, name="helm", help=__doc__helm)

    except ImportError:
        # If Helm dependencies are not available, skip adding the commands
        pass

    return app


app = create_application()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
