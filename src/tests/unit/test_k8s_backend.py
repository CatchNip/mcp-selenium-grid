from unittest.mock import MagicMock, patch

import pytest
from app.core.settings import Settings  # Assuming Settings can be used directly or mocked
from app.services.selenium_hub.k8s_backend import KubernetesHubBackend
from kubernetes.client.rest import ApiException


# Fixture for mocking Kubernetes client APIs
@pytest.fixture
def mock_k8s_clients():
    with (
        patch("kubernetes.client.CoreV1Api") as mock_core_api_cls,
        patch("kubernetes.client.AppsV1Api") as mock_apps_api_cls,
    ):
        mock_core_api = MagicMock()
        mock_apps_api = MagicMock()
        mock_core_api_cls.return_value = mock_core_api
        mock_apps_api_cls.return_value = mock_apps_api
        yield mock_core_api, mock_apps_api


# Fixture for creating a KubernetesHubBackend instance with mocked settings
@pytest.fixture
def k8s_backend(mock_k8s_clients, monkeypatch):
    with (
        patch("kubernetes.config.load_incluster_config"),
        patch("kubernetes.config.load_kube_config"),
    ):
        # Mock settings with necessary attributes
        mock_settings = MagicMock(spec=Settings)
        mock_settings.K8S_NAMESPACE = "test-namespace"
        mock_settings.K8S_MAX_RETRIES = 3  # Use a small number of retries for tests
        mock_settings.K8S_RETRY_DELAY_SECONDS = 0  # No delay for faster tests
        mock_settings.MAX_BROWSER_INSTANCES = 10
        mock_settings.SE_NODE_MAX_SESSIONS = 5

        backend = KubernetesHubBackend(mock_settings)
        yield backend, mock_k8s_clients


# Unit tests for cleanup method
@pytest.mark.unit
def test_cleanup_deletes_resources(k8s_backend):
    backend, (mock_core_api, mock_apps_api) = k8s_backend

    backend.cleanup()

    # Verify delete_collection_namespaced_pod is called
    mock_core_api.delete_collection_namespaced_pod.assert_called_once_with(
        namespace="test-namespace", label_selector="app=selenium-node"
    )
    # Verify delete_namespaced_deployment is called
    mock_apps_api.delete_namespaced_deployment.assert_called_once_with(
        name="selenium-hub", namespace="test-namespace"
    )
    # Verify delete_namespaced_service is called
    mock_core_api.delete_namespaced_service.assert_called_once_with(
        name="selenium-hub", namespace="test-namespace"
    )


# Unit tests for ensure_hub_running method
@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_hub_running_resources_exist(k8s_backend):
    backend, (mock_core_api, mock_apps_api) = k8s_backend

    # Simulate resources already existing
    mock_core_api.read_namespace.return_value = MagicMock()
    mock_apps_api.read_namespaced_deployment.return_value = MagicMock()
    mock_core_api.read_namespaced_service.return_value = MagicMock()

    result = await backend.ensure_hub_running({})

    assert result is True
    mock_core_api.read_namespace.assert_called_once_with("test-namespace")
    mock_apps_api.read_namespaced_deployment.assert_called_once_with(
        name="selenium-hub", namespace="test-namespace"
    )
    mock_core_api.read_namespaced_service.assert_called_once_with(
        name="selenium-hub", namespace="test-namespace"
    )
    mock_core_api.create_namespace.assert_not_called()
    mock_apps_api.create_namespaced_deployment.assert_not_called()
    mock_core_api.create_namespaced_service.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_hub_running_creates_resources(k8s_backend):
    backend, (mock_core_api, mock_apps_api) = k8s_backend

    # Simulate resources not existing (ApiException with status 404)
    mock_core_api.read_namespace.side_effect = ApiException(status=404)
    mock_apps_api.read_namespaced_deployment.side_effect = ApiException(status=404)
    mock_core_api.read_namespaced_service.side_effect = ApiException(status=404)

    # Mock create methods to return MagicMock objects (representing created resources)
    mock_core_api.create_namespace.return_value = MagicMock()
    mock_apps_api.create_namespaced_deployment.return_value = MagicMock()
    mock_core_api.create_namespaced_service.return_value = MagicMock()

    result = await backend.ensure_hub_running({})

    assert result is True
    mock_core_api.read_namespace.assert_called_once_with("test-namespace")
    mock_core_api.create_namespace.assert_called_once()  # Verify namespace is created
    mock_apps_api.read_namespaced_deployment.assert_called_once_with(
        name="selenium-hub", namespace="test-namespace"
    )
    mock_apps_api.create_namespaced_deployment.assert_called_once()  # Verify deployment is created
    mock_core_api.read_namespaced_service.assert_called_once_with(
        name="selenium-hub", namespace="test-namespace"
    )
    mock_core_api.create_namespaced_service.assert_called_once()  # Verify service is created


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_hub_running_api_error(k8s_backend):
    backend, (mock_core_api, mock_apps_api) = k8s_backend

    # Simulate an API error (e.g., Forbidden 403) when reading namespace
    api_error = ApiException(status=403, reason="Forbidden")
    mock_core_api.read_namespace.side_effect = [api_error] * backend.settings.K8S_MAX_RETRIES

    # The method should return False or raise an exception after retries
    # Based on the k8s_backend code, it catches and returns False after max retries
    result = await backend.ensure_hub_running({})

    assert result is False
    # Verify read_namespace was called multiple times due to retries
    assert mock_core_api.read_namespace.call_count == backend.settings.K8S_MAX_RETRIES
    mock_core_api.create_namespace.assert_not_called()
    mock_apps_api.read_namespaced_deployment.assert_not_called()
    mock_core_api.read_namespaced_service.assert_not_called()


# Unit tests for create_browsers method
@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_success(k8s_backend):
    backend, (mock_core_api, mock_apps_api) = k8s_backend

    # Mock create_namespaced_pod to succeed
    mock_core_api.create_namespaced_pod.return_value = MagicMock()

    browser_configs = {
        "chrome": {
            "image": "selenium/node-chrome:latest",
            "resources": {"memory": "1G", "cpu": "0.5"},
        }
    }
    count = 2
    browser_type = "chrome"

    browser_ids = await backend.create_browsers(count, browser_type, browser_configs)

    assert isinstance(browser_ids, list)
    assert len(browser_ids) == count
    assert all(
        isinstance(id, str) and id.startswith(f"selenium-node-{browser_type}-")
        for id in browser_ids
    )
    assert (
        mock_core_api.create_namespaced_pod.call_count == count
    )  # Verify create is called for each browser

    # Optional: Add more assertions to check the details of the calls to create_namespaced_pod
    # For example, check pod metadata (name, labels) and container spec (image, ports, env, resources, probes)
    # This would require inspecting mock_core_api.create_namespaced_pod.call_args_list


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_with_retries(k8s_backend):
    backend, (mock_core_api, mock_apps_api) = k8s_backend

    # Simulate ApiException for the first few create calls, then succeed
    # Using side_effect with a list of return values/exceptions
    api_error = ApiException(status=500, reason="Internal Server Error")
    side_effects = [api_error] * (backend.settings.K8S_MAX_RETRIES - 1) + [MagicMock()]
    mock_core_api.create_namespaced_pod.side_effect = side_effects

    browser_configs = {
        "chrome": {
            "image": "selenium/node-chrome:latest",
            "resources": {"memory": "1G", "cpu": "0.5"},
        }
    }
    count = 1  # Test with one browser to keep it simple
    browser_type = "chrome"

    browser_ids = await backend.create_browsers(count, browser_type, browser_configs)

    assert isinstance(browser_ids, list)
    assert len(browser_ids) == count
    assert all(
        isinstance(id, str) and id.startswith(f"selenium-node-{browser_type}-")
        for id in browser_ids
    )
    # Verify create_namespaced_pod was called MAX_RETRIES times for the single browser
    assert mock_core_api.create_namespaced_pod.call_count == backend.settings.K8S_MAX_RETRIES


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_failure_after_retries(k8s_backend):
    backend, (mock_core_api, mock_apps_api) = k8s_backend

    # Simulate ApiException for all create calls
    api_error = ApiException(status=500, reason="Internal Server Error")
    mock_core_api.create_namespaced_pod.side_effect = api_error

    browser_configs = {
        "chrome": {
            "image": "selenium/node-chrome:latest",
            "resources": {"memory": "1G", "cpu": "0.5"},
        }
    }
    count = 1  # Test with one browser
    browser_type = "chrome"

    with pytest.raises(RuntimeError, match="Failed to create pod after multiple retries"):
        await backend.create_browsers(count, browser_type, browser_configs)

    # Verify create_namespaced_pod was called MAX_RETRIES times
    assert mock_core_api.create_namespaced_pod.call_count == backend.settings.K8S_MAX_RETRIES


# Add a test for cleanup when resources are not found to ensure it doesn't raise errors
@pytest.mark.unit
def test_cleanup_resources_not_found(k8s_backend):
    backend, (mock_core_api, mock_apps_api) = k8s_backend

    # Simulate resources not being found (ApiException with status 404)
    mock_core_api.delete_collection_namespaced_pod.side_effect = ApiException(status=404)
    mock_apps_api.delete_namespaced_deployment.side_effect = ApiException(status=404)
    mock_core_api.delete_namespaced_service.side_effect = ApiException(status=404)
    # Also mock read calls in _wait_for_resource_deletion to raise 404 immediately
    mock_core_api.read_namespaced_pod.side_effect = ApiException(status=404)
    mock_apps_api.read_namespaced_deployment.side_effect = ApiException(status=404)
    mock_core_api.read_namespaced_service.side_effect = ApiException(status=404)

    # cleanup should complete without raising exceptions
    try:
        backend.cleanup()
    except Exception as e:
        pytest.fail(f"cleanup raised an unexpected exception: {e}")

    # Verify delete methods were called
    mock_core_api.delete_collection_namespaced_pod.assert_called_once_with(
        namespace="test-namespace", label_selector="app=selenium-node"
    )
    mock_apps_api.delete_namespaced_deployment.assert_called_once_with(
        name="selenium-hub", namespace="test-namespace"
    )
    mock_core_api.delete_namespaced_service.assert_called_once_with(
        name="selenium-hub", namespace="test-namespace"
    )
    # Verify that the read calls in the wait loop were not made when delete returns 404
    assert (
        mock_apps_api.read_namespaced_deployment.call_count == 0
    )  # Read should not be called if delete returns 404
    assert (
        mock_core_api.read_namespaced_service.call_count == 0
    )  # Read should not be called if delete returns 404
    # Pod read should not be called in cleanup's wait logic as collection delete is used
    mock_core_api.read_namespaced_pod.assert_not_called()
