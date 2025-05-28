from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from app.core.models import BrowserConfig, ContainerResources
from app.core.settings import Settings  # Assuming Settings can be used directly or mocked
from app.services.selenium_hub.k8s_backend import KubernetesHubBackend
from kubernetes.client.exceptions import ApiException


# Fixture for mocking Kubernetes client APIs
@pytest.fixture
def mock_k8s_clients() -> Generator[tuple[MagicMock, MagicMock], None, None]:
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
def k8s_backend(
    mock_k8s_clients: tuple[MagicMock, MagicMock], monkeypatch: object
) -> Generator[tuple[KubernetesHubBackend, tuple[MagicMock, MagicMock]], None, None]:
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
def test_cleanup_deletes_resources(
    k8s_backend: tuple[KubernetesHubBackend, tuple[MagicMock, MagicMock]],
) -> None:
    backend, (mock_core_api, mock_apps_api) = k8s_backend

    # Patch _wait_for_resource_deletion to avoid real waiting
    with (
        patch.object(backend, "_wait_for_resource_deletion"),
        patch.object(backend.k8s_core, "delete_collection_namespaced_pod") as mock_delete_pods,
        patch.object(backend.k8s_apps, "delete_namespaced_deployment") as mock_delete_deploy,
        patch.object(backend.k8s_core, "delete_namespaced_service") as mock_delete_svc,
    ):
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
) -> None:
    backend, (mock_core_api, mock_apps_api) = k8s_backend

    # Patch internal helpers to simulate resources exist
    with (
        patch.object(backend, "_ensure_namespace_exists"),
        patch.object(backend, "_ensure_deployment_exists"),
        patch.object(backend, "_ensure_service_exists"),
    ):
        result = await backend.ensure_hub_running()

    assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_hub_running_creates_resources(
    k8s_backend: tuple[KubernetesHubBackend, tuple[MagicMock, MagicMock]],
) -> None:
    backend, (mock_core_api, mock_apps_api) = k8s_backend

    # Patch internal helpers to simulate creation
    with (
        patch.object(backend, "_ensure_namespace_exists"),
        patch.object(backend, "_ensure_deployment_exists"),
        patch.object(backend, "_ensure_service_exists"),
    ):
        result = await backend.ensure_hub_running()

    assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_hub_running_api_error(
    k8s_backend: tuple[KubernetesHubBackend, tuple[MagicMock, MagicMock]],
) -> None:
    backend, (mock_core_api, mock_apps_api) = k8s_backend

    # Patch internal helpers to simulate error and retries
    with patch.object(backend, "_ensure_namespace_exists", side_effect=Exception("fail")):
        result = await backend.ensure_hub_running()
    assert result is False


# Unit tests for create_browsers method
@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_success(
    k8s_backend: tuple[KubernetesHubBackend, tuple[MagicMock, MagicMock]],
) -> None:
    backend, (mock_core_api, mock_apps_api) = k8s_backend

    # Patch create_namespaced_pod to succeed and patch pod status to simulate running pods
    with (
        patch.object(backend, "_ensure_namespace_exists"),
        patch.object(backend, "_ensure_deployment_exists"),
        patch.object(backend, "_ensure_service_exists"),
        patch.object(backend.k8s_core, "create_namespaced_pod", return_value=MagicMock()),
    ):
        # Patch pod status to simulate running pods
        with patch.object(backend.k8s_core, "read_namespaced_pod", return_value=MagicMock()):
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
) -> None:
    backend, (mock_core_api, mock_apps_api) = k8s_backend

    # Patch create_namespaced_pod to fail then succeed and patch pod status to simulate running pod
    api_error = ApiException(status=500, reason="Internal Server Error")
    side_effects = [api_error] * (backend.settings.K8S_MAX_RETRIES - 1) + [MagicMock()]
    with (
        patch.object(backend, "_ensure_namespace_exists"),
        patch.object(backend, "_ensure_deployment_exists"),
        patch.object(backend, "_ensure_service_exists"),
        patch.object(backend.k8s_core, "create_namespaced_pod", side_effect=side_effects),
    ):
        with patch.object(backend.k8s_core, "read_namespaced_pod", return_value=MagicMock()):
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
) -> None:
    backend, (mock_core_api, mock_apps_api) = k8s_backend

    # Patch create_namespaced_pod to always fail
    api_error = ApiException(status=500, reason="Internal Server Error")
    mock_core_api.create_namespaced_pod.side_effect = api_error
    with (
        patch.object(backend, "_ensure_namespace_exists"),
        patch.object(backend, "_ensure_deployment_exists"),
        patch.object(backend, "_ensure_service_exists"),
    ):
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


# Add a test for cleanup when resources are not found to ensure it doesn't raise errors
@pytest.mark.unit
def test_cleanup_resources_not_found(
    k8s_backend: tuple[KubernetesHubBackend, tuple[MagicMock, MagicMock]],
) -> None:
    backend, (mock_core_api, mock_apps_api) = k8s_backend

    # Patch _wait_for_resource_deletion to avoid real waiting
    with (
        patch.object(backend, "_wait_for_resource_deletion"),
        patch.object(backend.k8s_core, "delete_collection_namespaced_pod") as mock_delete_pods,
        patch.object(backend.k8s_apps, "delete_namespaced_deployment") as mock_delete_deploy,
        patch.object(backend.k8s_core, "delete_namespaced_service") as mock_delete_svc,
    ):
        mock_delete_pods.side_effect = ApiException(status=404)
        mock_delete_deploy.side_effect = ApiException(status=404)
        mock_delete_svc.side_effect = ApiException(status=404)
        backend.cleanup()
        mock_delete_pods.assert_called_once_with(
            namespace="test-namespace", label_selector="app=selenium-node"
        )
        mock_delete_deploy.assert_called_once_with(name="selenium-hub", namespace="test-namespace")
        mock_delete_svc.assert_called_once_with(name="selenium-hub", namespace="test-namespace")
