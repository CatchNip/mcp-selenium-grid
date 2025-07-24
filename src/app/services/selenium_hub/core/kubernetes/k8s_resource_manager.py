import asyncio
import logging
import time
from typing import Callable

from kubernetes.client import AppsV1Api, CoreV1Api, V1DeleteOptions
from kubernetes.client.exceptions import ApiException
from kubernetes.client.models import (
    V1Deployment,
    V1Namespace,
    V1Pod,
    V1Service,
)

from ...models.kubernetes_settings import KubernetesSettings
from .common.constants import (
    DEFAULT_POLL_INTERVAL,
    HTTP_NOT_FOUND,
)
from .common.decorators import ErrorStrategy, handle_kubernetes_exceptions
from .k8s_models import ResourceType, WaitConfig

# Type aliases
KubernetesResource = V1Pod | V1Service | V1Deployment | V1Namespace
ResourceReadinessFunc = Callable[[KubernetesResource], bool]


def is_pod_ready(resource: KubernetesResource, name: str) -> bool:
    """Check if a pod is running and ready."""
    if not isinstance(resource, V1Pod):
        return False
    if not resource.status or not resource.metadata:
        return False
    if resource.status.phase == "Failed":
        raise RuntimeError(f"Pod {name} failed to start.")

    # Check if pod is running
    if resource.status.phase != "Running":
        return False

    # Check if all containers are ready
    if not resource.status.container_statuses:
        return False

    for container_status in resource.status.container_statuses:
        if not container_status.ready:
            return False

    return True


def is_service_ready(
    resource: KubernetesResource, name: str, k8s_core: CoreV1Api, namespace: str
) -> bool:
    """Check if a service is ready by verifying it has endpoints."""
    if not isinstance(resource, V1Service):
        return False
    if not resource.spec:
        return False

    try:
        endpoints = k8s_core.read_namespaced_endpoints(name=name, namespace=namespace)
        if not endpoints.subsets:
            return False

        for subset in endpoints.subsets:
            if subset.addresses and len(subset.addresses) > 0:
                return True

        return False
    except Exception as e:
        logging.debug(f"Error checking endpoints for service {name}: {e}")
        return False


def is_deployment_ready(resource: KubernetesResource, name: str) -> bool:
    """Check if a deployment is ready."""
    if not isinstance(resource, V1Deployment):
        return False
    if not resource.status:
        return False

    status = resource.status
    if status.ready_replicas is None:
        return False
    if status.available_replicas is None:
        return False
    if status.replicas is None:
        return False

    return status.ready_replicas == status.replicas and status.available_replicas == status.replicas


def is_namespace_ready(resource: KubernetesResource, name: str) -> bool:
    """Check if a namespace is active."""
    if not isinstance(resource, V1Namespace):
        return False
    if not resource.status:
        return False

    return resource.status.phase == "Active"


class KubernetesResourceManager:
    """Simplified Kubernetes resource manager with minimal code."""

    def __init__(
        self, k8s_settings: KubernetesSettings, k8s_core: CoreV1Api, k8s_apps: AppsV1Api
    ) -> None:
        self.k8s_settings = k8s_settings
        self.k8s_core = k8s_core
        self.k8s_apps = k8s_apps
        self.namespace = k8s_settings.NAMESPACE
        self.max_retries = k8s_settings.MAX_RETRIES
        self.retry_delay = k8s_settings.RETRY_DELAY_SECONDS

    @handle_kubernetes_exceptions(ErrorStrategy.STRICT)
    def read_resource(self, resource_type: ResourceType, name: str) -> KubernetesResource:
        """Read a Kubernetes resource."""
        match resource_type:
            case ResourceType.POD:
                return self.k8s_core.read_namespaced_pod(name, self.namespace)
            case ResourceType.DEPLOYMENT:
                return self.k8s_apps.read_namespaced_deployment(name, self.namespace)
            case ResourceType.SERVICE:
                return self.k8s_core.read_namespaced_service(name, self.namespace)
            case ResourceType.NAMESPACE:
                return self.k8s_core.read_namespace(name)
            case _:
                raise ValueError(f"Unsupported resource type: {resource_type}")

    @handle_kubernetes_exceptions(ErrorStrategy.STRICT)
    def delete_resource(self, resource_type: ResourceType, name: str) -> None:
        """Delete a Kubernetes resource and wait for deletion."""
        match resource_type:
            case ResourceType.POD:
                self.k8s_core.delete_namespaced_pod(name, self.namespace, body=V1DeleteOptions())
            case ResourceType.DEPLOYMENT:
                self.k8s_apps.delete_namespaced_deployment(name, self.namespace)
            case ResourceType.SERVICE:
                self.k8s_core.delete_namespaced_service(name, self.namespace)
            case ResourceType.NAMESPACE:
                self.k8s_core.delete_namespace(name)
            case _:
                raise ValueError(f"Unsupported resource type: {resource_type}")

        self._wait_for_deletion(resource_type, name)

    def _wait_for_deletion(self, resource_type: ResourceType, name: str) -> None:
        """Wait for resource deletion to complete."""
        logging.info(f"Waiting for {resource_type.value} {name} to be deleted...")
        for _ in range(self.max_retries):
            try:
                self.read_resource(resource_type, name)
                time.sleep(self.retry_delay)
            except ApiException as e:
                if e.status == HTTP_NOT_FOUND:
                    logging.info(f"{resource_type.value} {name} deleted successfully.")
                    return
                raise
            except Exception as e:
                logging.exception(f"Error waiting for {resource_type.value} {name} deletion: {e}")
                raise
        logging.warning(f"Timeout waiting for {resource_type.value} {name} to be deleted.")

    async def wait_for_resource_ready(
        self,
        resource_type: ResourceType,
        name: str,
        check_ready_func: ResourceReadinessFunc | None = None,
        config: WaitConfig | None = None,
    ) -> None:
        """Wait for a resource to be ready using polling."""
        if config is None:
            config = WaitConfig()

        logging.info(f"Waiting for {resource_type.value} {name} to be ready...")

        try:
            async with asyncio.timeout(config.timeout_seconds):
                while True:
                    if await self._check_resource_ready(resource_type, name, check_ready_func):
                        logging.info(f"{resource_type.value} {name} is ready.")
                        return
                    await asyncio.sleep(config.poll_interval or DEFAULT_POLL_INTERVAL)
        except asyncio.TimeoutError:
            logging.error(f"Timeout waiting for {resource_type.value} {name} to be ready.")
            raise

    async def _check_resource_ready(
        self,
        resource_type: ResourceType,
        name: str,
        check_ready_func: ResourceReadinessFunc | None,
    ) -> bool:
        """Check if a resource is ready."""
        try:
            resource = self.read_resource(resource_type, name)
            if check_ready_func:
                return check_ready_func(resource)
            else:
                return self._is_resource_ready_by_type(resource_type, resource, name)
        except ApiException as e:
            if e.status == HTTP_NOT_FOUND:
                logging.info(f"{resource_type.value} {name} not found yet, waiting...")
                return False
            logging.error(f"Error checking {resource_type.value} {name} readiness: {e}")
            return False
        except Exception as e:
            logging.exception(
                f"Unexpected error during polling for {resource_type.value} {name}: {e}"
            )
            return False

    def _is_resource_ready_by_type(
        self, resource_type: ResourceType, resource: KubernetesResource, name: str
    ) -> bool:
        """Check if a resource is ready using the appropriate checker."""
        match resource_type:
            case ResourceType.POD:
                return is_pod_ready(resource, name)
            case ResourceType.SERVICE:
                return is_service_ready(resource, name, self.k8s_core, self.namespace)
            case ResourceType.DEPLOYMENT:
                return is_deployment_ready(resource, name)
            case ResourceType.NAMESPACE:
                return is_namespace_ready(resource, name)
            case _:
                logging.warning(f"Unknown resource type {resource_type.value} for {name}")
                return False

    async def sleep(self, attempt: int) -> None:
        """Sleep with exponential backoff."""
        delay = self.retry_delay * (2**attempt)
        logging.info(f"Retrying in {delay} seconds...", stacklevel=2)
        await asyncio.sleep(delay)
