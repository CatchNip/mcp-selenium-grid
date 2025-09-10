import logging
import sys
from os import getenv

from rich.console import Console
from rich.logging import RichHandler

from .constants import IS_STDIO_ENABLED

LOG_LEVEL = getenv("LOG_LEVEL", "INFO")

# Create
logger = logging.getLogger(f"MCP Selenium Grid:{__name__}")
logger.setLevel(LOG_LEVEL)

rich_handler = RichHandler(
    console=Console(file=sys.stderr if IS_STDIO_ENABLED else None),
    level=LOG_LEVEL,
    markup=True,
    rich_tracebacks=True,
    tracebacks_show_locals=True,
)

logger.addHandler(rich_handler)
