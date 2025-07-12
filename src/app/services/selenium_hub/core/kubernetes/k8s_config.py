import logging
from typing import Any

from kubernetes.client import CoreV1Api, V1ObjectMeta
from kubernetes.config.config_exception import ConfigException
from kubernetes.config.incluster_config import load_incluster_config
from kubernetes.config.kube_config import load_kube_config


class KubernetesConfigManager:
    """Handles Kubernetes configuration loading and cluster detection."""

    def __init__(self, k8s_settings: Any) -> None:
        self.k8s_settings = k8s_settings
        self._is_kind = False
        self._load_config()
        self._detect_kind_cluster()

    def _load_config(self) -> None:
        try:
            try:
                load_incluster_config()
            except ConfigException:
                load_kube_config(
                    config_file=self.k8s_settings.K8S_KUBECONFIG,
                    context=self.k8s_settings.K8S_CONTEXT,
                )
        except Exception as e:
            logging.exception(f"Failed to load Kubernetes configuration: {e}")
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
                logging.info("KinD cluster detected via node name suffix '-control-plane'.")
        except Exception:
            self._is_kind = False

    @property
    def is_kind(self) -> bool:
        return self._is_kind
