from dataclasses import dataclass
from enum import Enum
from typing import Optional


@dataclass
class WaitConfig:
    """Configuration for resource waiting."""

    timeout_seconds: int = 30
    poll_interval: int = 2
    strategy: Optional["WaitingStrategy"] = None


class WaitingStrategy(Enum):
    """Enum for different waiting strategies."""

    POLLING = "polling"
    WATCH = "watch"


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
