"""Metrics collection for Selenium Hub service."""

from prometheus_client import Counter, Gauge, Histogram
from prometheus_client.utils import INF

# Browser metrics
BROWSER_INSTANCES = Gauge(
    "selenium_browser_instances", "Number of browser instances", ["browser_type", "deployment_mode"]
)

BROWSER_CREATION_TIME = Histogram(
    "selenium_browser_creation_seconds",
    "Time spent creating browser instances",
    ["browser_type", "deployment_mode"],
    buckets=(1, 2, 5, 10, 30, 60, INF),
)

BROWSER_CREATION_ERRORS = Counter(
    "selenium_browser_creation_errors_total",
    "Number of browser creation errors",
    ["browser_type", "deployment_mode", "error_type"],
)

# Hub metrics
HUB_STATUS = Gauge(
    "selenium_hub_status",
    "Status of Selenium Hub (1 for running, 0 for not running)",
    ["deployment_mode"],
)

HUB_OPERATION_TIME = Histogram(
    "selenium_hub_operation_seconds",
    "Time spent on hub operations",
    ["operation", "deployment_mode"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, INF),
)

# Resource metrics
RESOURCE_USAGE = Gauge(
    "selenium_resource_usage",
    "Resource usage by browser instances",
    ["resource_type", "browser_type", "deployment_mode"],
)


def track_browser_metrics():
    """Decorator for tracking browser-related metrics."""

    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            browser_type = kwargs.get("browser_type", args[1] if len(args) > 1 else "unknown")

            with BROWSER_CREATION_TIME.labels(
                browser_type=browser_type, deployment_mode=self.deployment_mode
            ).time():
                try:
                    result = await func(self, *args, **kwargs)
                    BROWSER_INSTANCES.labels(
                        browser_type=browser_type, deployment_mode=self.deployment_mode
                    ).inc()
                    return result
                except Exception as e:
                    BROWSER_CREATION_ERRORS.labels(
                        browser_type=browser_type,
                        deployment_mode=self.deployment_mode,
                        error_type=type(e).__name__,
                    ).inc()
                    raise

        return wrapper

    return decorator


def track_hub_metrics():
    """Decorator for tracking hub-related metrics."""

    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            operation = func.__name__

            with HUB_OPERATION_TIME.labels(
                operation=operation, deployment_mode=self.deployment_mode
            ).time():
                try:
                    result = await func(self, *args, **kwargs)
                    HUB_STATUS.labels(deployment_mode=self.deployment_mode).set(1 if result else 0)
                    return result
                except Exception:
                    HUB_STATUS.labels(deployment_mode=self.deployment_mode).set(0)
                    raise

        return wrapper

    return decorator
