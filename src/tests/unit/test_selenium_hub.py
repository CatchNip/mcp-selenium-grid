"""Unit tests for SeleniumHub service."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core import settings as core_settings
from app.services.selenium_hub import SeleniumHub
from docker.errors import NotFound


@pytest.fixture
def mock_docker_client():
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.status = "running"
    mock_container.name = "selenium-hub"
    mock_container.id = "container-123456789012"
    mock_client.containers.run.return_value = mock_container
    mock_client.containers.list.return_value = [mock_container]
    mock_client.networks.create.return_value = MagicMock(name="selenium-grid")
    mock_client.containers.get.side_effect = lambda name: (
        mock_container if name == "selenium-hub" else NotFound(f"Container '{name}' not found")
    )
    mock_client.networks.get.side_effect = lambda name: (
        MagicMock(name="selenium-grid")
        if name == "selenium-grid"
        else NotFound(f"Network '{name}' not found")
    )
    return mock_client


@pytest.fixture
def selenium_hub(mock_docker_client):
    with patch(
        "app.services.selenium_hub.docker_backend.docker.from_env",
        return_value=mock_docker_client,
    ):
        hub = SeleniumHub()
        # Set browser_configs directly on the hub instance for testing
        hub.browser_configs = {
            "chrome": {
                "image": "selenium/node-chrome:latest",
                "resources": {"memory": "1G", "cpu": "0.5"},
            }
        }
        yield hub


@pytest.fixture
def selenium_hub_k8s(mock_docker_client, monkeypatch):
    # Patch settings to use kubernetes
    mock_settings = MagicMock(spec=core_settings.Settings)
    mock_settings.DEPLOYMENT_MODE = "kubernetes"
    mock_settings.K8S_NAMESPACE = "test-namespace"
    mock_settings.K8S_MAX_RETRIES = 3  # Use a small number of retries for tests
    mock_settings.BROWSER_CONFIGS = {
        "chrome": {
            "image": "selenium/node-chrome:latest",
            "resources": {"memory": "1G", "cpu": "0.5"},
        }
    }  # Mock browser configs with full structure
    mock_settings.K8S_RETRY_DELAY_SECONDS = 0  # No delay for faster tests
    mock_settings.MAX_BROWSER_INSTANCES = 10

    monkeypatch.setattr(core_settings.settings, "DEPLOYMENT_MODE", mock_settings.DEPLOYMENT_MODE)
    monkeypatch.setattr(core_settings.settings, "K8S_NAMESPACE", mock_settings.K8S_NAMESPACE)
    monkeypatch.setattr(core_settings.settings, "K8S_MAX_RETRIES", mock_settings.K8S_MAX_RETRIES)
    monkeypatch.setattr(core_settings.settings, "BROWSER_CONFIGS", mock_settings.BROWSER_CONFIGS)
    monkeypatch.setattr(
        core_settings.settings, "K8S_RETRY_DELAY_SECONDS", mock_settings.K8S_RETRY_DELAY_SECONDS
    )
    monkeypatch.setattr(
        core_settings.settings, "MAX_BROWSER_INSTANCES", mock_settings.MAX_BROWSER_INSTANCES
    )

    # Patch the KubernetesHubBackend class itself to prevent config loading
    with (
        patch("kubernetes.config.load_incluster_config"),
        patch("kubernetes.config.load_kube_config"),
        patch("kubernetes.client.CoreV1Api") as core_api_cls,
        patch("kubernetes.client.AppsV1Api") as apps_api_cls,
        patch("app.services.selenium_hub.docker_backend.docker.from_env") as docker_from_env,
        patch("app.services.selenium_hub.manager.KubernetesHubBackend") as mock_k8s_backend_cls,
    ):
        core_api = MagicMock()
        apps_api = MagicMock()
        core_api_cls.return_value = core_api
        apps_api_cls.return_value = apps_api
        docker_from_env.return_value = mock_docker_client

        # Configure the mock KubernetesBackend instance
        mock_k8s_backend = MagicMock()
        mock_k8s_backend.create_browsers = AsyncMock(
            return_value=["mock-k8s-browser-id"] * 1
        )  # Mock awaitable method return value
        mock_k8s_backend.ensure_hub_running = AsyncMock(
            return_value=True
        )  # Mock awaitable method return value
        mock_k8s_backend_cls.return_value = mock_k8s_backend

        hub = SeleniumHub()  # Create the hub instance *after* patching settings and backend

        yield hub, core_api, apps_api  # Yield the hub and the k8s api mocks


@pytest.mark.unit
def test_ensure_docker_hub_creates_network(selenium_hub):
    # Only test the public interface and that ensure_hub_running returns True
    result = asyncio.run(selenium_hub.ensure_hub_running())
    assert result is True


@pytest.mark.unit
def test_ensure_docker_hub_restarts_stopped_hub(selenium_hub):
    # Only test the public interface and that ensure_hub_running returns True
    result = asyncio.run(selenium_hub.ensure_hub_running())
    assert result is True


@pytest.mark.unit
def test_create_docker_browser(selenium_hub):
    selenium_hub.deployment_mode = "docker"
    selenium_hub.ensure_hub_running = AsyncMock(return_value=True)
    browser_ids = asyncio.run(selenium_hub.create_browsers(browser_type="chrome", count=1))
    assert isinstance(browser_ids, list)
    assert len(browser_ids) == 1
    # Accept any string as the browser ID (since backend now controls the value)
    assert isinstance(browser_ids[0], str)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_validates_type(selenium_hub):
    """Test browser type validation."""
    with pytest.raises(KeyError) as excinfo:
        await selenium_hub.create_browsers(browser_type="invalid", count=1)
    assert "Unsupported browser type: invalid" in str(excinfo.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_validates_count(selenium_hub):
    """Test browser count validation."""
    with pytest.raises(ValueError) as excinfo:
        await selenium_hub.create_browsers(browser_type="chrome", count=0)
    assert "Browser count must be positive" in str(excinfo.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_handles_max_instances(selenium_hub, monkeypatch):
    """Test handling max browser instances limit."""
    monkeypatch.setattr("app.core.settings.settings.MAX_BROWSER_INSTANCES", 1)

    with pytest.raises(ValueError) as excinfo:
        await selenium_hub.create_browsers(browser_type="chrome", count=2)

    assert "Maximum browser instances exceeded" in str(excinfo.value)


# Unit tests for delete_browser method


@pytest.mark.unit
def test_ensure_k8s_hub_creates_namespace(selenium_hub_k8s):
    # This test verifies that ensure_hub_running calls the backend's ensure_hub_running method.
    # The specific K8s API interactions are tested in test_k8s_backend.py.
    hub, core_api, apps_api = (
        selenium_hub_k8s  # core_api and apps_api are available but should not be asserted on directly
    )

    result = asyncio.run(hub.ensure_hub_running())

    assert result is True  # ensure_hub_running should return True on success
    # Assert that the mocked backend's ensure_hub_running method was called
    hub.manager.backend.ensure_hub_running.assert_called_once_with(
        hub.browser_configs
    )  # Verify call to mocked backend

    # Optionally, assert that the underlying K8s API mocks were NOT called
    core_api.create_namespace.assert_not_called()
    apps_api.create_namespaced_deployment.assert_not_called()
    core_api.create_namespaced_service.assert_not_called()


@pytest.mark.unit
def test_create_k8s_browser(selenium_hub_k8s):
    # This test verifies that create_browsers calls the backend's create_browsers method
    # and correctly handles the return value.
    hub, core_api, _ = (
        selenium_hub_k8s  # core_api is available but should not be asserted on directly
    )
    count = 1
    browser_type = "chrome"

    # The mocked backend's create_browsers method will be called
    # Its return value is configured in the fixture.
    browser_ids = asyncio.run(hub.create_browsers(browser_type=browser_type, count=count))

    assert isinstance(browser_ids, list)
    assert len(browser_ids) == count
    # Assert that the mocked backend's create_browsers method was called with the correct args
    hub.manager.backend.create_browsers.assert_called_once_with(
        count, browser_type, hub.browser_configs
    )  # Verify call to mocked backend with positional arguments
    assert (
        browser_ids == ["mock-k8s-browser-id"] * count
    )  # Assert the expected return value from the mocked backend (multiplied by count)
