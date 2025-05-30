from typing import Any, Generator
from unittest.mock import MagicMock

import pytest
from app.core.models import BrowserConfig, ContainerResources
from app.services.selenium_hub.k8s_backend import KubernetesHubBackend
from kubernetes.client.exceptions import ApiException


# Fixture for creating a KubernetesHubBackend instance with mocked settings
@pytest.fixture
def k8s_backend(
    mock_k8s_clients: tuple[MagicMock, MagicMock], mocker: MagicMock
) -> Generator[tuple[KubernetesHubBackend, tuple[MagicMock, MagicMock]], None, None]:
    """Fixture that yields a KubernetesHubBackend instance and its mocked K8s clients."""
    with (
        mocker.patch("kubernetes.config.load_incluster_config"),
        mocker.patch("kubernetes.config.load_kube_config"),
    ):
        # Mock settings with necessary attributes
        mock_settings = mocker.MagicMock()
        mock_settings.K8S_NAMESPACE = "test-namespace"
        mock_settings.K8S_MAX_RETRIES = 3  # Use a small number of retries for tests
        mock_settings.K8S_RETRY_DELAY_SECONDS = 0  # No delay for faster tests
        mock_settings.MAX_BROWSER_INSTANCES = 10
        mock_settings.SE_NODE_MAX_SESSIONS = 5

        backend = KubernetesHubBackend(mock_settings)
        # Use the tuple from the fixture in conftest.py
        backend.k8s_core, backend.k8s_apps = mock_k8s_clients
        yield backend, mock_k8s_clients


# Fixture to patch common backend helper methods for k8s backend tests.
@pytest.fixture
def patch_backend_helpers(mocker: MagicMock) -> Any:
    """Fixture to patch common backend helper methods for k8s backend tests."""

    def _patch(backend: KubernetesHubBackend) -> None:
        # Patch backend helpers as needed for tests
        pass

    return _patch


# Unit tests for cleanup method
@pytest.mark.unit
def test_cleanup_deletes_resources(
    k8s_backend: tuple[KubernetesHubBackend, tuple[MagicMock, MagicMock]],
    mocker: MagicMock,
) -> None:
    """Test that cleanup deletes all expected Kubernetes resources."""
    backend, (mock_core_api, mock_apps_api) = k8s_backend
    mocker.patch.object(backend, "_wait_for_resource_deletion")
    mock_delete_pods = mocker.patch.object(backend.k8s_core, "delete_collection_namespaced_pod")
    mock_delete_deploy = mocker.patch.object(backend.k8s_apps, "delete_namespaced_deployment")
    mock_delete_svc = mocker.patch.object(backend.k8s_core, "delete_namespaced_service")
    backend.cleanup()
    mock_delete_pods.assert_called_once_with(
        namespace="test-namespace", label_selector="app=selenium-node"
    )
    mock_delete_deploy.assert_called_once_with(name="selenium-hub", namespace="test-namespace")
    mock_delete_svc.assert_called_once_with(name="selenium-hub", namespace="test-namespace")


@pytest.mark.unit
def test_cleanup_resources_not_found(
    k8s_backend: tuple[KubernetesHubBackend, tuple[MagicMock, MagicMock]],
    mocker: MagicMock,
) -> None:
    """Test that cleanup does not raise errors when resources are not found."""
    backend, (mock_core_api, mock_apps_api) = k8s_backend
    mocker.patch.object(backend, "_wait_for_resource_deletion")
    mock_delete_pods = mocker.patch.object(
        backend.k8s_core, "delete_collection_namespaced_pod", side_effect=ApiException(status=404)
    )
    mock_delete_deploy = mocker.patch.object(
        backend.k8s_apps, "delete_namespaced_deployment", side_effect=ApiException(status=404)
    )
    mock_delete_svc = mocker.patch.object(
        backend.k8s_core, "delete_namespaced_service", side_effect=ApiException(status=404)
    )
    backend.cleanup()
    mock_delete_pods.assert_called_once_with(
        namespace="test-namespace", label_selector="app=selenium-node"
    )
    mock_delete_deploy.assert_called_once_with(name="selenium-hub", namespace="test-namespace")
    mock_delete_svc.assert_called_once_with(name="selenium-hub", namespace="test-namespace")


# Unit tests for ensure_hub_running method
@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_hub_running_resources_exist(
    k8s_backend: tuple[KubernetesHubBackend, tuple[MagicMock, MagicMock]],
    patch_backend_helpers: Any,
) -> None:
    """Test that ensure_hub_running returns True when resources exist."""
    backend, (mock_core_api, mock_apps_api) = k8s_backend
    patch_backend_helpers(backend)
    result = await backend.ensure_hub_running()
    assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_hub_running_creates_resources(
    k8s_backend: tuple[KubernetesHubBackend, tuple[MagicMock, MagicMock]],
    patch_backend_helpers: Any,
) -> None:
    """Test that ensure_hub_running returns True when resources are created."""
    backend, (mock_core_api, mock_apps_api) = k8s_backend
    patch_backend_helpers(backend)
    result = await backend.ensure_hub_running()
    assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_hub_running_api_error(
    k8s_backend: tuple[KubernetesHubBackend, tuple[MagicMock, MagicMock]],
    mocker: MagicMock,
) -> None:
    """Test that ensure_hub_running returns False on error."""
    backend, (mock_core_api, mock_apps_api) = k8s_backend
    # Patch only the namespace helper to raise
    mocker.patch.object(backend, "_ensure_namespace_exists", side_effect=Exception("fail"))
    result = await backend.ensure_hub_running()
    assert result is False


# Unit tests for create_browsers method
@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_success(
    k8s_backend: tuple[KubernetesHubBackend, tuple[MagicMock, MagicMock]],
    patch_backend_helpers: Any,
    mocker: MagicMock,
) -> None:
    """Test that create_browsers returns a list of browser IDs on success."""
    backend, (mock_core_api, mock_apps_api) = k8s_backend
    patch_backend_helpers(backend)
    mocker.patch.object(backend.k8s_core, "create_namespaced_pod", return_value=MagicMock())
    mocker.patch.object(backend.k8s_core, "read_namespaced_pod", return_value=MagicMock())
    browser_configs = {
        "chrome": BrowserConfig(
            image="selenium/node-chrome:latest",
            resources=ContainerResources(memory="1G", cpu="1"),
            port=4444,
        )
    }
    count = 2
    browser_type = "chrome"
    browser_ids = await backend.create_browsers(count, browser_type, browser_configs)
    assert isinstance(browser_ids, list)
    assert len(browser_ids) == count


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_with_retries(
    k8s_backend: tuple[KubernetesHubBackend, tuple[MagicMock, MagicMock]],
    patch_backend_helpers: Any,
    mocker: MagicMock,
) -> None:
    """Test that create_browsers retries and succeeds after failures."""
    backend, (mock_core_api, mock_apps_api) = k8s_backend
    patch_backend_helpers(backend)
    api_error = ApiException(status=500, reason="Internal Server Error")
    side_effects = [api_error] * (backend.settings.K8S_MAX_RETRIES - 1) + [MagicMock()]
    mocker.patch.object(backend.k8s_core, "create_namespaced_pod", side_effect=side_effects)
    mocker.patch.object(backend.k8s_core, "read_namespaced_pod", return_value=MagicMock())
    browser_configs = {
        "chrome": BrowserConfig(
            image="selenium/node-chrome:latest",
            resources=ContainerResources(memory="1G", cpu="1"),
            port=4444,
        )
    }
    count = 1
    browser_type = "chrome"
    browser_ids = await backend.create_browsers(count, browser_type, browser_configs)
    assert isinstance(browser_ids, list)
    assert len(browser_ids) == count


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_failure_after_retries(
    k8s_backend: tuple[KubernetesHubBackend, tuple[MagicMock, MagicMock]],
    patch_backend_helpers: Any,
) -> None:
    """Test that create_browsers returns an empty list after all retries fail."""
    backend, (mock_core_api, mock_apps_api) = k8s_backend
    patch_backend_helpers(backend)
    api_error = ApiException(status=500, reason="Internal Server Error")
    mock_core_api.create_namespaced_pod.side_effect = api_error
    browser_configs = {
        "chrome": BrowserConfig(
            image="selenium/node-chrome:latest",
            resources=ContainerResources(memory="1G", cpu="1"),
            port=4444,
        )
    }
    count = 1
    browser_type = "chrome"
    browser_ids = await backend.create_browsers(count, browser_type, browser_configs)
    assert browser_ids == []
