import time
from os import environ

from kubernetes.client import CoreV1Api

from ...common.logger import logger
from ...models.general_settings import SeleniumHubGeneralSettings
from .common.decorators import ErrorStrategy, handle_kubernetes_exceptions


class KubernetesUrlResolver:
    """Handles URL resolution for different Kubernetes environments."""

    def __init__(
        self, settings: SeleniumHubGeneralSettings, k8s_core: CoreV1Api, is_kind: bool
    ) -> None:
        self.settings = settings
        self.k8s_core = k8s_core
        self._is_kind = is_kind

    def get_hub_url(self) -> str:
        FALLBACK_URL = f"http://localhost:{self.settings.selenium_grid.SELENIUM_HUB_PORT}"

        if "KUBERNETES_SERVICE_HOST" in environ:
            return self._get_in_cluster_url()

        if self._is_kind:
            # For KinD environments, use port-forwarded URL
            FALLBACK_URL = f"http://localhost:{self.settings.kubernetes.PORT_FORWARD_LOCAL_PORT}"
            logger.info(f"Using port-forwarded URL for KinD: {FALLBACK_URL}")
            return FALLBACK_URL

        return self._get_nodeport_url(FALLBACK_URL)

    def _get_in_cluster_url(self) -> str:
        url = f"http://{self.settings.kubernetes.SELENIUM_GRID_SERVICE_NAME}.{self.settings.kubernetes.NAMESPACE}.svc.cluster.local:{self.settings.selenium_grid.SELENIUM_HUB_PORT}"
        logger.info(f"Using in-cluster DNS for Selenium Hub URL: {url}")
        return url

    def _get_nodeport_url(self, fallback_url: str) -> str:
        max_retries = 5
        retry_delay = 2
        for attempt in range(max_retries):
            try:
                url = self._try_get_nodeport_url(attempt, max_retries)
                if url:
                    return url
                if attempt < max_retries - 1:
                    logger.info(f"NodePort not yet assigned, retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
            except Exception as e:
                logger.error(
                    f"Error getting NodePort URL (attempt {attempt + 1}/{max_retries}): {e}. Fallback: {fallback_url}"
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    break
        return fallback_url

    @handle_kubernetes_exceptions(ErrorStrategy.STRICT)
    def _try_get_nodeport_url(self, attempt: int, max_retries: int) -> str | None:
        logger.info(
            f"Attempt {attempt + 1}/{max_retries}: Getting NodePort for service {self.settings.kubernetes.SELENIUM_GRID_SERVICE_NAME} in namespace {self.settings.kubernetes.NAMESPACE}"
        )
        service = self.k8s_core.read_namespaced_service(
            name=self.settings.kubernetes.SELENIUM_GRID_SERVICE_NAME,
            namespace=self.settings.kubernetes.NAMESPACE,
        )
        logger.info(f"Service type: {service.spec.type if service.spec else 'None'}")
        logger.info(
            f"Service ports: {service.spec.ports if service.spec and service.spec.ports else 'None'}"
        )
        if not service.spec or not service.spec.ports:
            return None
        for port in service.spec.ports:
            logger.info(
                f"Checking port: port={port.port}, target_port={port.target_port}, node_port={port.node_port}"
            )
            if port.node_port:
                url = f"http://localhost:{port.node_port}"
                logger.info(f"Resolved NodePort URL: {url}")
                return url
        return None
