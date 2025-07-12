"""
Settings model for Kubernetes-based Selenium Hub deployments.

Defines configuration options specific to Kubernetes environments, such as
namespace, context, and retry policies.
"""

from pathlib import Path

from pydantic import Field, field_validator

from . import CustomBaseSettings


class KubernetesSettings(CustomBaseSettings):
    """
    Configuration settings for running Selenium Hub in a Kubernetes environment.

    Includes options like kubeconfig path, namespace, service name, and retry policies.
    """

    K8S_KUBECONFIG: str = ""

    @field_validator("K8S_KUBECONFIG", mode="before")
    @classmethod
    def expand_path(cls, v: str) -> str:
        if v:
            return str(Path(v).expanduser())
        return v

    K8S_CONTEXT: str = Field(default="")
    K8S_NAMESPACE: str = Field(default="selenium-grid")
    K8S_SELENIUM_GRID_SERVICE_NAME: str = Field(default="selenium-grid")
    K8S_RETRY_DELAY_SECONDS: int = Field(default=2)
    K8S_MAX_RETRIES: int = Field(default=5)
