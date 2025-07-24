"""Unit tests for Kubernetes components."""

from unittest.mock import MagicMock, patch

import pytest
from app.services.selenium_hub.core.kubernetes import KubernetesConfigManager, KubernetesUrlResolver
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException
from pytest_mock import MockerFixture


class TestKubernetesConfigManager:
    """Test KubernetesConfigManager component."""

    @pytest.mark.unit
    def test_init_loads_config_and_detects_kind(self, mocker: MockerFixture) -> None:
        """Test that __init__ loads config and detects KinD cluster."""
        k8s_settings = MagicMock()
        k8s_settings.KUBECONFIG = None
        k8s_settings.CONTEXT = None

        # Mock config loading at the module level
        mock_load_incluster = mocker.patch(
            "app.services.selenium_hub.core.kubernetes.k8s_config.load_incluster_config"
        )
        mocker.patch("app.services.selenium_hub.core.kubernetes.k8s_config.load_kube_config")

        # Mock KinD detection by node name
        mock_core_api = mocker.patch(
            "app.services.selenium_hub.core.kubernetes.k8s_config.CoreV1Api"
        )
        mock_node = MagicMock()
        mock_node.metadata.name = "kind-control-plane"
        mock_core_api.return_value.list_node.return_value.items = [mock_node]

        manager = KubernetesConfigManager(k8s_settings)

        mock_load_incluster.assert_called_once()
        assert manager.is_kind is True

    @pytest.mark.unit
    def test_init_falls_back_to_kubeconfig(self, mocker: MockerFixture) -> None:
        """Test that __init__ falls back to kubeconfig when not in cluster."""
        k8s_settings = MagicMock()
        k8s_settings.KUBECONFIG = "/path/to/kubeconfig"
        k8s_settings.CONTEXT = "test-context"

        # Mock in-cluster config to fail with ConfigException, kube config to succeed
        mock_load_incluster = mocker.patch(
            "app.services.selenium_hub.core.kubernetes.k8s_config.load_incluster_config",
            side_effect=ConfigException("Not in cluster"),
        )
        mocker.patch(
            "app.services.selenium_hub.core.kubernetes.k8s_config.load_kube_config",
            return_value=None,
        )

        # Mock KinD detection to fail
        mock_core_api = mocker.patch("app.services.selenium_hub.core.kubernetes.backend.CoreV1Api")
        mock_core_api.return_value.read_node.side_effect = Exception("Not KinD")

        manager = KubernetesConfigManager(k8s_settings)

        mock_load_incluster.assert_called_once()
        assert manager.is_kind is False

    @pytest.mark.unit
    def test_init_handles_config_loading_error(self, mocker: MockerFixture) -> None:
        """Test that __init__ handles config loading errors properly."""
        k8s_settings = MagicMock()
        k8s_settings.KUBECONFIG = None
        k8s_settings.CONTEXT = None

        # Mock config loading to fail at the module level
        mocker.patch(
            "app.services.selenium_hub.core.kubernetes.k8s_config.load_incluster_config",
            side_effect=Exception("Config error"),
        )
        mocker.patch(
            "app.services.selenium_hub.core.kubernetes.k8s_config.load_kube_config",
            side_effect=Exception("Config error"),
        )

        with pytest.raises(Exception, match="Config error"):
            KubernetesConfigManager(k8s_settings)


class TestKubernetesUrlResolver:
    """Test KubernetesUrlResolver component."""

    @pytest.mark.unit
    def test_get_hub_url_kind_cluster(self, mocker: MockerFixture) -> None:
        """Test URL resolution for KinD cluster."""
        settings = MagicMock()
        settings.selenium_grid.SELENIUM_HUB_PORT = 4444
        k8s_core = MagicMock()
        is_kind = True

        resolver = KubernetesUrlResolver(settings, k8s_core, is_kind)

        url = resolver.get_hub_url()
        assert url == "http://localhost:4444"

    @pytest.mark.unit
    @patch.dict("os.environ", {"KUBERNETES_SERVICE_HOST": "10.0.0.1"})
    def test_get_hub_url_in_cluster(self, mocker: MockerFixture) -> None:
        """Test URL resolution when running in cluster."""
        settings = MagicMock()
        settings.selenium_grid.SELENIUM_HUB_PORT = 4444
        settings.kubernetes.SELENIUM_GRID_SERVICE_NAME = "selenium-hub"
        settings.kubernetes.NAMESPACE = "default"
        k8s_core = MagicMock()
        is_kind = False

        resolver = KubernetesUrlResolver(settings, k8s_core, is_kind)

        url = resolver.get_hub_url()
        assert url == "http://selenium-hub.default.svc.cluster.local:4444"

    @pytest.mark.unit
    def test_get_hub_url_nodeport_success(self, mocker: MockerFixture) -> None:
        """Test URL resolution with successful NodePort lookup."""
        settings = MagicMock()
        settings.selenium_grid.SELENIUM_HUB_PORT = 4444
        settings.kubernetes.SELENIUM_GRID_SERVICE_NAME = "selenium-hub"
        settings.kubernetes.NAMESPACE = "default"
        k8s_core = MagicMock()

        # Mock service with NodePort
        mock_service = MagicMock()
        mock_port = MagicMock()
        mock_port.port = 4444
        mock_port.node_port = 30044
        mock_service.spec.ports = [mock_port]
        k8s_core.read_namespaced_service.return_value = mock_service

        is_kind = False

        resolver = KubernetesUrlResolver(settings, k8s_core, is_kind)

        url = resolver.get_hub_url()
        assert url == "http://localhost:30044"

    @pytest.mark.unit
    def test_get_hub_url_nodeport_fallback(self, mocker: MockerFixture) -> None:
        """Test URL resolution falls back when NodePort lookup fails."""
        settings = MagicMock()
        settings.selenium_grid.SELENIUM_HUB_PORT = 4444
        settings.kubernetes.SELENIUM_GRID_SERVICE_NAME = "selenium-hub"
        settings.kubernetes.NAMESPACE = "default"
        k8s_core = MagicMock()

        # Mock service without NodePort
        mock_service = MagicMock()
        mock_port = MagicMock()
        mock_port.port = 4444
        mock_port.node_port = None
        mock_service.spec.ports = [mock_port]
        k8s_core.read_namespaced_service.return_value = mock_service

        is_kind = False

        resolver = KubernetesUrlResolver(settings, k8s_core, is_kind)

        url = resolver.get_hub_url()
        assert url == "http://localhost:4444"

    @pytest.mark.unit
    def test_get_hub_url_api_exception_fallback(self, mocker: MockerFixture) -> None:
        """Test URL resolution falls back when API call fails."""
        settings = MagicMock()
        settings.selenium_grid.SELENIUM_HUB_PORT = 4444
        settings.kubernetes.SELENIUM_GRID_SERVICE_NAME = "selenium-hub"
        settings.kubernetes.NAMESPACE = "default"
        k8s_core = MagicMock()

        # Mock API exception
        k8s_core.read_namespaced_service.side_effect = ApiException(status=404)

        is_kind = False

        resolver = KubernetesUrlResolver(settings, k8s_core, is_kind)

        url = resolver.get_hub_url()
        assert url == "http://localhost:4444"
