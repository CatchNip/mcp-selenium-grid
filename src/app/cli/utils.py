from functools import wraps
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Callable


def resolve_module_path(module_name: str) -> Path:
    spec = find_spec(module_name)
    if spec is None or spec.origin is None:
        raise ImportError(f"Cannot find module '{module_name}'")
    return Path(spec.origin).resolve()


def with_app_path(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Inject the path to the FastAPI app into CLI kwargs."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        kwargs["path"] = resolve_module_path("app.main")
        return fn(*args, **kwargs)

    return wrapper
