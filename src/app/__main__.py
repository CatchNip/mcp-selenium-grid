"""Entry point for running the MCP Selenium Grid server."""

from .cli import mcp_selenium_grid_cli


def main() -> None:
    mcp_selenium_grid_cli()


if __name__ == "__main__":
    main()
