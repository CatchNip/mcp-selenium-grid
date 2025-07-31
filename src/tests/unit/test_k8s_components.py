"""Unit tests for Kubernetes components."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.selenium_hub.core.kubernetes import (
    KubernetesConfigManager,
    KubernetesUrlResolver,
    PortForwardManager,
)
from app.services.selenium_hub.models.general_settings import SeleniumHubGeneralSettings
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException
from pytest_mock import MockerFixture


class TestKubernetesConfigManager:
    """Test KubernetesConfigManager component."""

    @pytest.mark.unit
    def test_init_loads_config_and_detects_kind(self, mocker: MockerFixture) -> None:
        """Test that __init__ loads config and detects KinD cluster."""
        k8s_settings = mocker.MagicMock()
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
        mock_node = mocker.MagicMock()
        mock_node.metadata.name = "kind-control-plane"
        mock_core_api.return_value.list_node.return_value.items = [mock_node]

        manager = KubernetesConfigManager(k8s_settings)

        mock_load_incluster.assert_called_once()
        assert manager.is_kind is True

    @pytest.mark.unit
    def test_init_falls_back_to_kubeconfig(self, mocker: MockerFixture) -> None:
        """Test that __init__ falls back to kubeconfig when not in cluster."""
        k8s_settings = mocker.MagicMock()
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
        k8s_settings = mocker.MagicMock()
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

    @pytest.fixture
    def settings(self, mocker: MockerFixture) -> SeleniumHubGeneralSettings:
        settings: MagicMock = mocker.MagicMock()
        settings.selenium_grid.SELENIUM_HUB_PORT = 4444
        settings.kubernetes.SELENIUM_GRID_SERVICE_NAME = "selenium-hub"
        settings.kubernetes.NAMESPACE = "default"
        return settings

    @pytest.fixture
    def k8s_core(self, mocker: MockerFixture) -> MagicMock:
        k8s_core: MagicMock = mocker.MagicMock()
        return k8s_core

    @pytest.fixture
    def service_with_nodeport(self, mocker: MockerFixture) -> MagicMock:
        # Mock service with NodePort
        mock_service: MagicMock = mocker.MagicMock()
        mock_port = mocker.MagicMock()
        mock_port.port = 4444
        mock_port.node_port = 30044
        mock_service.spec.ports = [mock_port]
        return mock_service

    @pytest.mark.unit
    def test_get_hub_url_kind_cluster(
        self, settings: SeleniumHubGeneralSettings, k8s_core: MagicMock
    ) -> None:
        """Test URL resolution for KinD cluster."""
        is_kind = True

        resolver = KubernetesUrlResolver(settings, k8s_core, is_kind)

        url = resolver.get_hub_url()
        assert url == f"http://localhost:{settings.kubernetes.PORT_FORWARD_LOCAL_PORT}"

    @pytest.mark.unit
    @patch.dict("os.environ", {"KUBERNETES_SERVICE_HOST": "10.0.0.1"})
    def test_get_hub_url_in_cluster(
        self, settings: SeleniumHubGeneralSettings, k8s_core: MagicMock
    ) -> None:
        """Test URL resolution when running in cluster."""
        is_kind = False

        resolver = KubernetesUrlResolver(settings, k8s_core, is_kind)

        url = resolver.get_hub_url()
        assert url == "http://selenium-hub.default.svc.cluster.local:4444"

    @pytest.mark.unit
    def test_get_hub_url_nodeport_success(
        self,
        settings: SeleniumHubGeneralSettings,
        k8s_core: MagicMock,
        service_with_nodeport: MagicMock,
    ) -> None:
        """Test URL resolution with successful NodePort lookup."""

        # Mock service with NodePort
        k8s_core.read_namespaced_service.return_value = service_with_nodeport

        is_kind = False

        resolver = KubernetesUrlResolver(settings, k8s_core, is_kind)

        url = resolver.get_hub_url()
        assert url == "http://localhost:30044"

    @pytest.mark.unit
    def test_get_hub_url_nodeport_fallback(
        self,
        settings: SeleniumHubGeneralSettings,
        k8s_core: MagicMock,
        service_with_nodeport: MagicMock,
    ) -> None:
        # Mock service without NodePort
        service_with_nodeport.spec.ports[0].node_port = None
        k8s_core.read_namespaced_service.return_value = service_with_nodeport

        is_kind = False

        resolver = KubernetesUrlResolver(settings, k8s_core, is_kind)

        url = resolver.get_hub_url()
        assert url == "http://localhost:4444"

    @pytest.mark.unit
    def test_get_hub_url_api_exception_fallback(
        self, settings: SeleniumHubGeneralSettings, k8s_core: MagicMock
    ) -> None:
        """Test URL resolution falls back when API call fails."""

        # Mock API exception
        k8s_core.read_namespaced_service.side_effect = ApiException(status=404)

        is_kind = False

        resolver = KubernetesUrlResolver(settings, k8s_core, is_kind)

        url = resolver.get_hub_url()
        assert url == "http://localhost:4444"


class TestPortForwardManager:
    """Test PortForwardManager component."""

    PID_OK = 12345
    PID_FAIL = 54321

    @pytest.fixture
    def mock_pidfile(self, mocker: MockerFixture) -> MagicMock:
        """Fixture for a mocked PidFile."""
        mock: MagicMock = mocker.patch(
            "app.services.selenium_hub.core.kubernetes.k8s_port_forwarder.PidFile"
        ).return_value
        mock.exists_and_alive.return_value = False
        mock.read.return_value = None
        return mock

    @pytest.fixture
    def mock_subprocess_popen(
        self, mocker: MockerFixture
    ) -> MagicMock:  # TODO: fix tests to mock Popen
        """Fixture for a mocked subproces.Popen."""
        mock_process = mocker.MagicMock()
        mock_process.pid = self.PID_OK
        mock_process.poll.return_value = None  # is_alive
        mock_process.returncode.return_value = 0  # exit_code

        mock_subprocess_popen = mocker.patch(
            "app.services.selenium_hub.core.kubernetes.k8s_port_forwarder.Popen"
        )
        mock_subprocess_popen.return_value = mock_process

        return mock_subprocess_popen

    @pytest.fixture
    def mock_is_process_running(self, mocker: MockerFixture) -> MagicMock:
        """Fixture for a mocked is_process_running_with_cmdline."""
        return mocker.patch(
            "app.services.selenium_hub.core.kubernetes.k8s_port_forwarder.is_process_running_with_cmdline",
            return_value=False,
        )

    @pytest.fixture
    def mock_terminate_pid(self, mocker: MockerFixture) -> MagicMock:
        """Fixture for a mocked terminate_pid."""
        return mocker.patch(
            "app.services.selenium_hub.core.kubernetes.k8s_port_forwarder.terminate_pid"
        )

    @pytest.fixture
    def mock_health_check(self, mocker: MockerFixture) -> AsyncMock:
        """Fixture for a mocked async health check function."""
        mock: AsyncMock = mocker.AsyncMock(return_value=True)
        return mock

    @pytest.fixture
    def manager(  # noqa: PLR0913
        self,
        mock_pidfile: MagicMock,
        mock_subprocess_popen: MagicMock,
        mock_is_process_running: MagicMock,
        mock_terminate_pid: MagicMock,
        mock_health_check: MagicMock,
        mocker: MockerFixture,
    ) -> PortForwardManager:
        """Fixture for a PortForwardManager instance with all dependencies mocked."""

        return PortForwardManager(
            service_name="test-service",
            namespace="test-ns",
            local_port=8080,
            remote_port=80,
            check_health=mock_health_check,
            max_retries=2,
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_start_success_on_first_try(
        self,
        manager: PortForwardManager,
        mock_health_check: MagicMock,
        mock_subprocess_popen: MagicMock,
        mock_pidfile: MagicMock,
    ) -> None:
        """Test that start succeeds on the first attempt if everything is clean."""
        result = await manager.start()

        assert result is True
        mock_subprocess_popen.assert_called_once()
        mock_pidfile.write.assert_called_once_with(self.PID_OK)
        mock_health_check.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_start_reuses_existing_healthy_process(
        self,
        manager: PortForwardManager,
        mock_is_process_running: MagicMock,
        mock_health_check: MagicMock,
        mock_subprocess_popen: MagicMock,
        mock_pidfile: MagicMock,
    ) -> None:
        """Test that an existing, healthy port-forward process is reused."""
        mock_is_process_running.return_value = True
        mock_pidfile.exists_and_alive.return_value = True
        mock_pidfile.read.return_value = self.PID_OK

        result = await manager.start()

        assert result is True
        mock_health_check.assert_called_once()
        mock_subprocess_popen.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_start_cleans_up_existing_unhealthy_process(  # noqa: PLR0913
        self,
        manager: PortForwardManager,
        mock_is_process_running: MagicMock,
        mock_health_check: MagicMock,
        mock_subprocess_popen: MagicMock,
        mock_pidfile: MagicMock,
        mock_terminate_pid: MagicMock,
    ) -> None:
        """Test that an existing but unhealthy process is stopped and restarted."""
        mock_is_process_running.return_value = True

        EXPECTED_HEALTH_CHECK_CALL_COUNT = 2
        mock_health_check.side_effect = [False, True]  # Fails first, then succeeds
        mock_pidfile.read.return_value = self.PID_FAIL

        result = await manager.start()

        assert result is True
        assert mock_health_check.call_count == EXPECTED_HEALTH_CHECK_CALL_COUNT
        # Called once to stop the old one
        mock_terminate_pid.assert_called_once_with(self.PID_FAIL)
        mock_pidfile.remove.assert_called_once()
        # Called twice to start. see: mock_health_check.side_effect
        assert mock_subprocess_popen.call_count == EXPECTED_HEALTH_CHECK_CALL_COUNT

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_start_fails_after_retries(
        self,
        manager: PortForwardManager,
        mock_health_check: MagicMock,
        mock_subprocess_popen: MagicMock,
    ) -> None:
        """Test that start fails after all retries if health check never passes."""
        mock_health_check.side_effect = [False] * manager.max_retries * 2  # More than max_retries

        result = await manager.start()

        assert result is False
        assert mock_health_check.call_count == manager.max_retries
        assert mock_subprocess_popen.call_count == manager.max_retries

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_start_fails_if_kubectl_not_found(
        self,
        manager: PortForwardManager,
        mock_subprocess_popen: MagicMock,
    ) -> None:
        """Test that start fails gracefully if kubectl command is not found."""
        mock_subprocess_popen.side_effect = FileNotFoundError

        result = await manager.start()

        assert result is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_start_handles_process_exiting_early(
        self,
        mocker: MockerFixture,
        manager: PortForwardManager,
        mock_subprocess_popen: MagicMock,
        mock_health_check: MagicMock,
    ) -> None:
        """Test retry logic when the kubectl process exits prematurely."""
        EXPECTED_KUBECTL_CALL_COUNT = 2

        # Process is not alive, exited with error (exit_code 1)
        mock_process_fail = mocker.MagicMock()
        mock_process_fail.pid = self.PID_FAIL
        mock_process_fail.poll.return_value = 1
        mock_process_fail.returncode.return_value = 1

        # Process is alive (still running), no exit_code.
        mock_process_ok = mocker.MagicMock()
        mock_process_ok.pid = self.PID_OK
        mock_process_ok.poll.return_value = None
        mock_process_ok.returncode.return_value = None

        mock_subprocess_popen.side_effect = [mock_process_fail, mock_process_ok]

        result = await manager.start()

        assert result is True
        assert mock_subprocess_popen.call_count == EXPECTED_KUBECTL_CALL_COUNT
        assert mock_health_check.call_count == 1  # Only once after the new start

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reuses_existing_healthy_process_without_starting_new_one(
        self,
        manager: PortForwardManager,
        mock_pidfile: MagicMock,
        mock_is_process_running: MagicMock,
        mock_subprocess_popen: MagicMock,
        mock_health_check: AsyncMock,
    ) -> None:
        """Test that an existing healthy port-forward is reused and kubectl is NOT called."""

        # Simulate that pidfile exists and process is alive
        mock_pidfile.exists_and_alive.return_value = True
        mock_pidfile.read.return_value = self.PID_OK
        mock_is_process_running.return_value = True
        mock_health_check.return_value = True  # Health check passes

        result = await manager.start()

        assert result is True
        mock_subprocess_popen.assert_not_called()
        mock_health_check.assert_called_once()

    @pytest.mark.unit
    def test_stop_terminates_process_and_cleans_pidfile(
        self,
        mocker: MockerFixture,
        manager: PortForwardManager,
        mock_pidfile: MagicMock,
    ) -> None:
        """Test that stop terminates the running process and removes the pidfile."""
        mock_process = mocker.MagicMock()
        manager.process = mock_process

        manager.stop()

        mock_process.terminate.assert_called_once()
        mock_pidfile.remove.assert_called_once()

    @pytest.mark.unit
    def test_stop_terminates_from_pidfile_if_no_process_object(
        self,
        manager: PortForwardManager,
        mock_pidfile: MagicMock,
        mock_terminate_pid: MagicMock,
    ) -> None:
        """Test that stop can kill a process using the PID from the pidfile."""
        manager.process = None
        mock_pidfile.read.return_value = 98765

        manager.stop()

        mock_terminate_pid.assert_called_once_with(98765)
        mock_pidfile.remove.assert_called_once()
