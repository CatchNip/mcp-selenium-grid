import logging
from os import getenv

from rich.logging import RichHandler

LOG_LEVEL = getenv("LOG_LEVEL", "INFO")

# Create
logger = logging.getLogger(f"MCP Selenium Grid:{__name__}")
logger.setLevel(LOG_LEVEL)

rich_handler = RichHandler(
    level=LOG_LEVEL,
    markup=True,
    rich_tracebacks=True,
    tracebacks_show_locals=True,
)

logger.addHandler(rich_handler)
