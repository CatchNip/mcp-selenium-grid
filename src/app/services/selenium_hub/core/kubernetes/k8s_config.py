import os

from kubernetes.client import CoreV1Api, V1ObjectMeta
from kubernetes.config.config_exception import ConfigException
from kubernetes.config.incluster_config import load_incluster_config
from kubernetes.config.kube_config import load_kube_config

from ...common.logger import logger
from ...models.kubernetes_settings import KubernetesSettings


class KubernetesConfigManager:
    """Handles Kubernetes configuration loading and cluster detection."""

    def __init__(self, k8s_settings: KubernetesSettings) -> None:
        self.k8s_settings = k8s_settings
        self._is_kind = False
        self._load_config()
        self._detect_kind_cluster()

    def _load_config(self) -> None:
        try:
            try:
                logger.info("Trying in-cluster config...")
                load_incluster_config()
                logger.info("Loaded in-cluster config.")
            except ConfigException:
                kubeconfig_path = self.k8s_settings.KUBECONFIG
                logger.info(f"In-cluster config failed, trying kubeconfig: '{kubeconfig_path}'")
                if kubeconfig_path:
                    logger.info(f"KUBECONFIG path: {kubeconfig_path}")
                    logger.info(f"KUBECONFIG exists: {os.path.exists(kubeconfig_path)}")
                else:
                    logger.info("KUBECONFIG is empty, will use default kubeconfig resolution.")
                load_kube_config(
                    config_file=kubeconfig_path,
                    context=self.k8s_settings.CONTEXT,
                )
                logger.info(f"Loaded kubeconfig from {kubeconfig_path}")
        except Exception as e:
            logger.exception(f"Failed to load Kubernetes configuration: {e}")
            raise

    def _detect_kind_cluster(self) -> None:
        try:
            core_api = CoreV1Api()
            nodes = core_api.list_node().items
            self._is_kind = False
            for node in nodes:
                meta: V1ObjectMeta | None = node.metadata
                name: str = getattr(meta, "name", "")
                if name and name.endswith("-control-plane"):
                    self._is_kind = True
                    break
            if self._is_kind:
                logger.info("KinD cluster detected via node name suffix '-control-plane'.")
        except Exception:
            self._is_kind = False

    @property
    def is_kind(self) -> bool:
        return self._is_kind
