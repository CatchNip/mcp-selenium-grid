import logging
from os import getenv

from rich.highlighter import Highlighter, ReprHighlighter
from rich.logging import RichHandler
from rich.text import Text

LOG_LEVEL: str = getenv("LOG_LEVEL", "INFO")


class CustomKeywordHighlighter(Highlighter):
    keywords: dict[str, str]

    def __init__(self) -> None:
        super().__init__()
        self.keywords = {
            "running": "bold green",
            "failed": "red",
            "failling": "red",
            "fail": "red",
            "success": "bold bright_green",
            "SUCCEED!": "bold bright_green",
            "selenium-hub": "bold",
            "selenium-grid": "bold",
            "DockerHubBackend": "bold",
            "KubernetesHubBackend": "bold",
            "Docker": "bold",
            "Kubernetes": "bold",
            "health": "bold",
            "Health check": "bold blue",
            "Port-forward": "bold",
            "port-forward": "bold",
        }

        self.repr_highlighter = ReprHighlighter()

    def highlight(self, text: Text) -> None:
        for keyword, style in self.keywords.items():
            text.highlight_words([keyword], style=style)

        self.repr_highlighter.highlight(text)


logger: logging.Logger = logging.getLogger(f"Selenium Grid:{__name__}")
logger.setLevel(LOG_LEVEL)

rich_handler: RichHandler = RichHandler(
    level=LOG_LEVEL,
    markup=True,
    rich_tracebacks=True,
    tracebacks_show_locals=True,
)
rich_handler.highlighter = CustomKeywordHighlighter()

logger.addHandler(rich_handler)
