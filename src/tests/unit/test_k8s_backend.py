from unittest.mock import MagicMock

import pytest
from app.services.selenium_hub.core.kubernetes import KubernetesHubBackend, ResourceType
from app.services.selenium_hub.models.browser import BrowserConfig, BrowserType, ContainerResources
from kubernetes.client.exceptions import ApiException
from pytest_mock import MockerFixture

# NOTE: All tests must use the k8s_backend fixture to ensure proper mocking of Kubernetes API calls.
# The fixture attaches set_namespace_exists to the backend for namespace mocking. Do not instantiate KubernetesHubBackend directly in tests.

DELETE_RESOURCE_CALLS = 2
READ_RESOURCE_CALLS = 3


# Unit tests for cleanup method
@pytest.mark.unit
def test_cleanup_deletes_resources(
    k8s_backend: KubernetesHubBackend,
    mocker: MockerFixture,
) -> None:
    """Test that cleanup deletes all expected Kubernetes resources."""
    backend = k8s_backend
    mock_delete_pods = mocker.patch.object(backend.k8s_core, "delete_collection_namespaced_pod")
    mock_delete_deploy = mocker.patch.object(backend.resource_manager, "delete_resource")

    backend.cleanup()

    mock_delete_pods.assert_called_once_with(
        namespace="test-namespace", label_selector="app=selenium-node"
    )
    # Check that _delete_resource was called twice (for deployment and service)
    assert mock_delete_deploy.call_count == DELETE_RESOURCE_CALLS
    # Check the calls were made with correct parameters
    calls = mock_delete_deploy.call_args_list
    assert calls[0][0][0] == ResourceType.DEPLOYMENT
    assert calls[0][0][1] == "test-service-name"
    assert calls[1][0][0] == ResourceType.SERVICE
    assert calls[1][0][1] == "test-service-name"


@pytest.mark.unit
def test_cleanup_resources_not_found(
    k8s_backend: KubernetesHubBackend,
    mocker: MockerFixture,
) -> None:
    """Test that cleanup does not raise errors when resources are not found."""
    backend = k8s_backend
    mock_delete_pods = mocker.patch.object(
        backend.k8s_core, "delete_collection_namespaced_pod", side_effect=ApiException(status=404)
    )
    mock_delete_deploy = mocker.patch.object(
        backend.resource_manager, "delete_resource", side_effect=ApiException(status=404)
    )

    backend.cleanup()

    mock_delete_pods.assert_called_once_with(
        namespace="test-namespace", label_selector="app=selenium-node"
    )
    # Check that _delete_resource was called twice (for deployment and service)
    assert mock_delete_deploy.call_count == DELETE_RESOURCE_CALLS


# Unit tests for ensure_hub_running method
@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_hub_running_resources_exist(
    k8s_backend: KubernetesHubBackend,
    mocker: MockerFixture,
) -> None:
    """Test that ensure_hub_running returns True when resources exist."""
    backend = k8s_backend

    # Not testing readiness
    mocker.patch.object(backend.resource_manager, "wait_for_resource_ready")

    # Mock resource reading
    # backend.resource_manager.read_resource is called 3 times and find resources.
    read_resource = mocker.patch.object(backend.resource_manager, "read_resource")
    create_namespaced_deployment = mocker.patch.object(
        backend.k8s_apps, "create_namespaced_deployment"
    )
    create_namespaced_service = mocker.patch.object(backend.k8s_core, "create_namespaced_service")
    create_namespace = mocker.patch.object(backend.k8s_core, "create_namespace")

    result = await backend.ensure_hub_running()
    assert result is True

    # Read 3 times and find resources
    assert read_resource.call_count == READ_RESOURCE_CALLS

    # Nothing was created
    assert create_namespaced_deployment.call_count == 0
    assert create_namespaced_service.call_count == 0
    assert create_namespace.call_count == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_hub_running_creates_resources(
    k8s_backend: KubernetesHubBackend,
    mocker: MockerFixture,
) -> None:
    """Test that ensure_hub_running returns True when resources are created."""
    backend = k8s_backend

    # Not testing readiness
    mocker.patch.object(backend.resource_manager, "wait_for_resource_ready")

    # Mock resource creation
    # backend.resource_manager.read_resource is called 3 times and return resource not found.
    read_resource = mocker.patch.object(
        backend.resource_manager, "read_resource", side_effect=ApiException(status=404)
    )
    create_namespaced_deployment = mocker.patch.object(
        backend.k8s_apps, "create_namespaced_deployment"
    )
    create_namespaced_service = mocker.patch.object(backend.k8s_core, "create_namespaced_service")
    create_namespace = mocker.patch.object(backend.k8s_core, "create_namespace")

    result = await backend.ensure_hub_running()
    assert result is True

    # Read 3 times and don't find resources
    assert read_resource.call_count == READ_RESOURCE_CALLS

    # Creates Resources
    assert create_namespaced_deployment.call_count == 1
    assert create_namespaced_service.call_count == 1
    assert create_namespace.call_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_hub_running_api_error(
    k8s_backend: KubernetesHubBackend,
    mocker: MockerFixture,
) -> None:
    """Test that ensure_hub_running returns False on error."""
    backend = k8s_backend
    # Patch the resource manager to raise an exception
    mocker.patch.object(backend.resource_manager, "read_resource", side_effect=Exception("fail"))

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
        BrowserType.CHROME: BrowserConfig(
            image="selenium/node-chrome:latest",
            resources=ContainerResources(memory="1G", cpu="1"),
            port=4444,
        )
    }
    count = 2
    browser_type = BrowserType.CHROME

    # Mock successful pod creation
    mocker.patch.object(backend.k8s_core, "create_namespaced_pod", return_value=MagicMock())

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
    side_effects = [api_error] * (backend.settings.kubernetes.MAX_RETRIES - 1) + [MagicMock()]
    mocker.patch.object(backend.k8s_core, "create_namespaced_pod", side_effect=side_effects)
    browser_configs = {
        BrowserType.CHROME: BrowserConfig(
            image="selenium/node-chrome:latest",
            resources=ContainerResources(memory="1G", cpu="1"),
            port=4444,
        )
    }
    count = 1
    browser_type = BrowserType.CHROME
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
        BrowserType.CHROME: BrowserConfig(
            image="selenium/node-chrome:latest",
            resources=ContainerResources(memory="1G", cpu="1"),
            port=4444,
        )
    }
    count = 1
    browser_type = BrowserType.CHROME
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


# Unit tests for delete_browser method
@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_browser_success(
    k8s_backend: KubernetesHubBackend, mocker: MockerFixture
) -> None:
    """Test that delete_browser successfully deletes a browser."""
    backend = k8s_backend
    mocker.patch.object(backend.resource_manager, "delete_resource")

    result = await backend.delete_browser("test-browser-id")
    assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_browser_failure(
    k8s_backend: KubernetesHubBackend, mocker: MockerFixture
) -> None:
    """Test that delete_browser returns False on failure."""
    backend = k8s_backend
    mocker.patch.object(backend.resource_manager, "delete_resource", side_effect=Exception("fail"))

    result = await backend.delete_browser("test-browser-id")
    assert result is False
