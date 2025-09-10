import sys
from functools import wraps
from importlib.util import find_spec
from logging import INFO, Filter, Logger, LogRecord, StreamHandler
from pathlib import Path
from shutil import which
from typing import Any, Callable, ParamSpec, TypeVar

from rich.logging import RichHandler
from typer import Exit, echo


def ensure_cli_installed(cli_name: str, install_instructions: str = "") -> str:
    """Check if a CLI tool is installed and return its path.

    Raises:
        typer.Exit: If the CLI tool is not installed or not in PATH.
    """
    cli_path: str | None = which(cli_name)
    if not cli_path:
        echo(
            f"Error: {cli_name.capitalize()} CLI is not installed or not in PATH.\n"
            f"{install_instructions}",
            err=True,
        )
        raise Exit(code=1)
    return cli_path


def resolve_module_path(module_name: str) -> Path:
    spec = find_spec(module_name)
    if spec is None or spec.origin is None:
        raise ImportError(f"Cannot find module '{module_name}'")
    return Path(spec.origin).resolve()


P = ParamSpec("P")
R = TypeVar("R")


def inject_kwargs(fn: Callable[P, R], **kwargs: Any) -> Callable[P, R]:
    """Inject kwargs to the Typer command"""

    @wraps(fn)
    def wrapper(*fn_args: P.args, **fn_kwargs: P.kwargs) -> R:
        for key, value in kwargs.items():
            if key not in fn_kwargs or fn_kwargs[key] is None:
                fn_kwargs[key] = value
        return fn(*fn_args, **fn_kwargs)

    return wrapper


def redirect_loggers_to_stderr(*loggers: Logger) -> None:
    """
    Redirect one or more loggers to stderr, disable Rich markup, and set their stream.
    """
    for logger in loggers:
        for handler in logger.handlers:
            if isinstance(handler, StreamHandler):
                handler.stream = sys.stderr
            elif isinstance(handler, RichHandler):
                handler.console.file = sys.stderr
                handler.markup = False  # disable rich markup
                handler.rich_tracebacks = False  # disable pretty tracebacks


class InfoOnlyFilter(Filter):
    def filter(self, record: LogRecord) -> bool:
        """
        Only allow INFO-level log records to pass through.
        """
        return record.levelno == INFO
