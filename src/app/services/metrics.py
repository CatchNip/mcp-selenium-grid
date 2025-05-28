"""Metrics collection for Selenium Hub service."""

from functools import wraps
from typing import Any, Callable, Coroutine


def track_browser_metrics() -> Callable[
    [Callable[..., Coroutine[Any, Any, Any]]], Callable[..., Coroutine[Any, Any, Any]]
]:
    """Decorator for tracking browser-related metrics."""

    def decorator(
        func: Callable[..., Coroutine[Any, Any, Any]],
    ) -> Callable[..., Coroutine[Any, Any, Any]]:
        @wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            try:
                result = await func(self, *args, **kwargs)
                return result
            except Exception:
                raise

        return wrapper

    return decorator


def track_hub_metrics() -> Callable[
    [Callable[..., Coroutine[Any, Any, Any]]], Callable[..., Coroutine[Any, Any, Any]]
]:
    """Decorator for tracking hub-related metrics."""

    def decorator(
        func: Callable[..., Coroutine[Any, Any, Any]],
    ) -> Callable[..., Coroutine[Any, Any, Any]]:
        @wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            try:
                result = await func(self, *args, **kwargs)
                return result
            except Exception:
                raise

        return wrapper

    return decorator
