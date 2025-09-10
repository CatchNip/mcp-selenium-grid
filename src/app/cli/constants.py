from .helpers import resolve_module_path

CLI_TITLE = "[bold green_yellow]MCP Selenium Grid CLI[/bold green_yellow] 🚀"
CLI_DESC = """
[pale_turquoise1]Model Context Protocol (MCP) server that enables AI Agents to request
and manage Selenium browser instances through a secure API.[/pale_turquoise1]

[italic gold1]Perfect for your automated browser testing needs![/italic gold1]

[link=https://github.com/CatchNip/mcp-selenium-grid]https://github.com/CatchNip/mcp-selenium-grid[/link]
"""
SERVER_SHORT_HELP = (
    "[pale_turquoise1]Run the MCP Server in HTTP/SSE or STDIO mode[/pale_turquoise1]."
)
FASTAPI_MODULE_PATH = resolve_module_path("app.main")
