"""Decorators for Kubernetes operations."""

import asyncio
import logging
from enum import Enum
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar

from kubernetes.client.exceptions import ApiException

from .constants import HTTP_NOT_FOUND

# Type variables for generic decorator
P = ParamSpec("P")
R = TypeVar("R")


class ErrorStrategy(Enum):
    """Error handling strategies for Kubernetes operations."""

    STRICT = "strict"  # Re-raise all errors
    GRACEFUL = "graceful"  # Ignore 404s, re-raise others
    RETURN_FALSE = "return_false"  # Return False on any error


def _handle_exceptions(func_name: str, strategy: ErrorStrategy, e: Exception) -> Any:
    """Handle exceptions based on strategy."""
    if isinstance(e, ApiException):
        if e.status == HTTP_NOT_FOUND:
            match strategy:
                case ErrorStrategy.GRACEFUL:
                    logging.info(f"Resource not found in {func_name}: {e}")
                    return None
                case ErrorStrategy.RETURN_FALSE:
                    logging.info(f"Resource not found in {func_name}: {e}")
                    return False
                case _:  # STRICT
                    logging.info(f"Resource not found in {func_name}: {e}")
                    raise e
        else:
            match strategy:
                case ErrorStrategy.RETURN_FALSE:
                    logging.error(f"Kubernetes API error in {func_name}: {e}")
                    return False
                case _:  # STRICT or GRACEFUL
                    logging.error(f"Kubernetes API error in {func_name}: {e}")
                    raise e
    else:
        match strategy:
            case ErrorStrategy.RETURN_FALSE:
                logging.exception(f"Error in {func_name}: {e}")
                return False
            case _:  # STRICT or GRACEFUL
                logging.exception(f"Unexpected error in {func_name}: {e}")
                raise e


def handle_kubernetes_exceptions(
    strategy: ErrorStrategy = ErrorStrategy.STRICT,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Flexible decorator for Kubernetes operations with configurable exception handling.

    Args:
        strategy: Exception handling strategy to apply
            - STRICT: Re-raise all exceptions (default)
            - GRACEFUL: Ignore 404s, re-raise other exceptions (for cleanup operations)
            - RETURN_FALSE: Return False on any exception (for status operations)
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                result = _handle_exceptions(func.__name__, strategy, e)
                if result is not None:
                    return result  # type: ignore[no-any-return]
                # If result is None, it means the exception was handled gracefully
                return None  # type: ignore[return-value]

        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return await func(*args, **kwargs)  # type: ignore[misc,no-any-return]
            except Exception as e:
                result = _handle_exceptions(func.__name__, strategy, e)
                if result is not None:
                    return result  # type: ignore[no-any-return]
                # If result is None, it means the exception was handled gracefully
                return None  # type: ignore[return-value]

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper  # type: ignore[return-value]

    return decorator
