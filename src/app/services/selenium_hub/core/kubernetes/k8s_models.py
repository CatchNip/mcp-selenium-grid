from dataclasses import dataclass
from enum import Enum


class WaitingStrategy(Enum):
    """Enum for different waiting strategies."""

    POLLING = "polling"
    WATCH = "watch"


@dataclass
class WaitConfig:
    """Configuration for resource waiting."""

    timeout_seconds: int = 30
    poll_interval: int = 2
    strategy: WaitingStrategy | None = None


class ResourceType(Enum):
    """Enum for Kubernetes resource types with their default waiting strategies."""

    POD = "pod"
    DEPLOYMENT = "deployment"
    SERVICE = "service"
    NAMESPACE = "namespace"

    @property
    def default_strategy(self) -> "WaitingStrategy":
        if self == ResourceType.POD:
            return WaitingStrategy.WATCH
        return WaitingStrategy.POLLING
