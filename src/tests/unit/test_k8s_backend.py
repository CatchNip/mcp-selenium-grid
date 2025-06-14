from unittest.mock import MagicMock

import pytest
from app.core.models import BrowserConfig, ContainerResources
from app.services.selenium_hub.k8s_backend import KubernetesHubBackend
from kubernetes.client.exceptions import ApiException
from pytest_mock import MockerFixture

# NOTE: All tests must use the k8s_backend fixture to ensure proper mocking of Kubernetes API calls.
# The fixture attaches set_namespace_exists to the backend for namespace mocking. Do not instantiate KubernetesHubBackend directly in tests.


# Unit tests for cleanup method
@pytest.mark.unit
def test_cleanup_deletes_resources(
    k8s_backend: KubernetesHubBackend,
    mocker: MockerFixture,
) -> None:
    """Test that cleanup deletes all expected Kubernetes resources."""
    backend = k8s_backend
    mock_delete_pods = mocker.patch.object(backend.k8s_core, "delete_collection_namespaced_pod")
    mock_delete_deploy = mocker.patch.object(backend.k8s_apps, "delete_namespaced_deployment")
    mock_delete_svc = mocker.patch.object(backend.k8s_core, "delete_namespaced_service")
    backend.cleanup()
    mock_delete_pods.assert_called_once_with(
        namespace="test-namespace", label_selector="app=selenium-node"
    )
    mock_delete_deploy.assert_called_once_with(name="test-service-name", namespace="test-namespace")
    mock_delete_svc.assert_called_once_with(name="test-service-name", namespace="test-namespace")


@pytest.mark.unit
def test_cleanup_resources_not_found(
    k8s_backend: KubernetesHubBackend,
    mocker: MockerFixture,
) -> None:
    """Test that cleanup does not raise errors when resources are not found."""
    backend = k8s_backend
    # mocker.patch.object(backend, "_wait_for_resource_deletion")
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
    mock_delete_deploy.assert_called_once_with(name="test-service-name", namespace="test-namespace")
    mock_delete_svc.assert_called_once_with(name="test-service-name", namespace="test-namespace")


# Unit tests for ensure_hub_running method
@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_hub_running_resources_exist(
    k8s_backend: KubernetesHubBackend,
    mocker: MockerFixture,
) -> None:
    """Test that ensure_hub_running returns True when resources exist."""
    backend = k8s_backend
    # mocker.patch.object(backend.k8s_core, "read_namespace", return_value=MagicMock())
    result = await backend.ensure_hub_running()
    assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_hub_running_creates_resources(
    k8s_backend: KubernetesHubBackend,
    mocker: MockerFixture,
) -> None:
    """Test that ensure_hub_running returns True when resources are created."""
    backend = k8s_backend
    mocker.patch.object(backend.k8s_core, "read_namespace", side_effect=ApiException(status=404))
    result = await backend.ensure_hub_running()
    assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_hub_running_api_error(
    k8s_backend: KubernetesHubBackend,
    mocker: MockerFixture,
) -> None:
    """Test that ensure_hub_running returns False on error."""
    backend = k8s_backend
    # Patch only the deployment helper (first in the chain) to raise. ; Any exception will do
    mocker.patch.object(backend, "_ensure_deployment_exists", side_effect=Exception("fail"))
    result = await backend.ensure_hub_running()
    assert result is False


# Unit tests for create_browsers method
@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_success(
    k8s_backend: KubernetesHubBackend,
    mocker: MockerFixture,
) -> None:
    """Test that create_browsers returns a list of browser IDs on success."""
    backend = k8s_backend
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
    k8s_backend: KubernetesHubBackend,
    mocker: MockerFixture,
) -> None:
    """Test that create_browsers retries and succeeds after failures."""
    backend = k8s_backend
    api_error = ApiException(status=500, reason="Internal Server Error")
    side_effects = [api_error] * (backend.settings.K8S_MAX_RETRIES - 1) + [MagicMock()]
    mocker.patch.object(backend.k8s_core, "create_namespaced_pod", side_effect=side_effects)
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
    k8s_backend: KubernetesHubBackend,
    mocker: MockerFixture,
) -> None:
    """Test that create_browsers returns an empty list after all retries fail."""
    backend = k8s_backend
    api_error = ApiException(status=500, reason="Internal Server Error")
    mocker.patch.object(backend.k8s_core, "create_namespaced_pod", side_effect=api_error)
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


# Unit tests for delete_browsers method
@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_browsers_success(
    k8s_backend: KubernetesHubBackend, mocker: MockerFixture
) -> None:
    """Test that delete_browsers successfully deletes specified browsers."""
    backend = k8s_backend
    mocker.patch.object(backend, "delete_browser", side_effect=lambda bid: bid != "fail")
    ids = ["ok1", "fail", "ok2"]
    result = await backend.delete_browsers(ids)
    assert result == ["ok1", "ok2"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_browsers_empty(
    k8s_backend: KubernetesHubBackend,
) -> None:
    """Test that delete_browsers handles empty input without errors."""
    backend = k8s_backend
    result = await backend.delete_browsers([])
    assert result == []
