"""
Settings model for Kubernetes-based Selenium Hub deployments.

Defines configuration options specific to Kubernetes environments, such as
namespace, context, and retry policies.
"""

from pathlib import Path

from pydantic import field_validator

from . import CustomBaseModel


class KubernetesSettings(CustomBaseModel):
    """
    Configuration settings for running Selenium Hub in a Kubernetes environment.

    Includes options like kubeconfig path, namespace, service name, and retry policies.
    """

    KUBECONFIG: str = ""

    @field_validator("KUBECONFIG", mode="before")
    @classmethod
    def expand_path(cls, v: str) -> str:
        if v:
            return str(Path(v).expanduser())
        return v

    CONTEXT: str = ""
    NAMESPACE: str = "selenium-grid"
    SELENIUM_GRID_SERVICE_NAME: str = "selenium-grid"
    RETRY_DELAY_SECONDS: int = 2
    MAX_RETRIES: int = 5
