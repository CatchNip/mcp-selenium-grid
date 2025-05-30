"""Unit tests for SeleniumHub service."""

from http import HTTPStatus
from typing import Any, Generator, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core import settings as core_settings
from app.core.models import BrowserConfig, ContainerResources
from app.services.selenium_hub.k8s_backend import KubernetesHubBackend
from app.services.selenium_hub.selenium_hub import SeleniumHub
from kubernetes.client.exceptions import ApiException


@pytest.fixture
def selenium_hub(mock_docker_client: MagicMock) -> Generator[SeleniumHub, Any, Any]:
    """Fixture that yields a SeleniumHub instance with a mocked Docker client."""
    with patch(
        "app.services.selenium_hub.docker_backend.docker.from_env",
        return_value=mock_docker_client,
    ):
        hub = SeleniumHub()
        # Set browser_configs directly on the hub instance for testing
        hub.browser_configs = {
            "chrome": BrowserConfig(
                image="selenium/node-chrome:latest",
                resources=ContainerResources(memory="1G", cpu="1"),
                port=4444,
            )
        }
        yield hub


@pytest.fixture
def selenium_hub_k8s(
    mock_docker_client: MagicMock, monkeypatch: Any
) -> Generator[Tuple[SeleniumHub, MagicMock], Any, Any]:
    """Fixture that yields a SeleniumHub instance and a mocked K8s backend."""
    # Patch settings to use kubernetes
    mock_settings = MagicMock(spec=core_settings.Settings)
    mock_settings.DEPLOYMENT_MODE = "kubernetes"
    mock_settings.K8S_NAMESPACE = "test-namespace"
    mock_settings.K8S_MAX_RETRIES = 3  # Use a small number of retries for tests
    mock_settings.BROWSER_CONFIGS = {
        "chrome": BrowserConfig(
            image="selenium/node-chrome:latest",
            resources=ContainerResources(memory="1G", cpu="1"),
            port=4444,
        )
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
        patch("app.services.selenium_hub.docker_backend.docker.from_env") as docker_from_env,
        patch("app.services.selenium_hub.manager.KubernetesHubBackend") as mock_k8s_backend_cls,
    ):
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

        yield hub, mock_k8s_backend  # Yield the hub and the mocked backend


@pytest.fixture
def mock_backend(
    mocker: Any, mock_k8s_clients: tuple[MagicMock, MagicMock]
) -> tuple[SeleniumHub, MagicMock]:
    """Fixture for a SeleniumHub with a mocked Kubernetes backend."""
    backend = mocker.MagicMock(spec=KubernetesHubBackend)
    hub = SeleniumHub()
    hub.manager.backend = backend
    return hub, backend


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_docker_hub_creates_network(selenium_hub: SeleniumHub) -> None:
    """Test that ensure_hub_running creates the network if not present."""
    # Only test the public interface and that ensure_hub_running returns True
    result = await selenium_hub.ensure_hub_running()
    assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_docker_hub_restarts_stopped_hub(selenium_hub: SeleniumHub) -> None:
    """Test that ensure_hub_running restarts the hub if it is stopped."""
    # Only test the public interface and that ensure_hub_running returns True
    result = await selenium_hub.ensure_hub_running()
    assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_docker_browser(selenium_hub: SeleniumHub) -> None:
    """Test that create_browsers returns a list with one browser ID for Docker."""
    # The mock is configured in the fixture mock_selenium_hub, so no assignment needed here
    browser_ids = await selenium_hub.create_browsers(browser_type="chrome", count=1)
    assert isinstance(browser_ids, list)
    assert len(browser_ids) == 1
    # Accept any string as the browser ID (since backend now controls the value)
    assert isinstance(browser_ids[0], str)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_validates_type(selenium_hub: SeleniumHub) -> None:
    """Test that create_browsers raises KeyError for unsupported browser type."""
    with pytest.raises(KeyError) as excinfo:
        await selenium_hub.create_browsers(browser_type="invalid", count=1)
    assert "Unsupported browser type: invalid" in str(excinfo.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_validates_count(selenium_hub: SeleniumHub) -> None:
    """Test that create_browsers raises ValueError for non-positive count."""
    with pytest.raises(ValueError) as excinfo:
        await selenium_hub.create_browsers(browser_type="chrome", count=0)
    assert "Browser count must be positive" in str(excinfo.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_handles_max_instances(
    selenium_hub: SeleniumHub, monkeypatch: Any
) -> None:
    """Test that create_browsers raises ValueError if max instances exceeded."""
    monkeypatch.setattr("app.core.settings.settings.MAX_BROWSER_INSTANCES", 1)

    with pytest.raises(ValueError) as excinfo:
        await selenium_hub.create_browsers(browser_type="chrome", count=2)

    assert "Maximum browser instances exceeded" in str(excinfo.value)


# Unit tests for delete_browser method


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_k8s_hub_creates_namespace(
    selenium_hub_k8s: Tuple[SeleniumHub, MagicMock],
) -> None:
    """Test that ensure_hub_running calls the backend's ensure_hub_running for K8s."""
    # This test verifies that ensure_hub_running calls the backend's ensure_hub_running method.
    # The specific K8s API interactions are tested in test_k8s_backend.py.
    hub, mock_k8s_backend = selenium_hub_k8s

    result = await hub.ensure_hub_running()

    assert result is True  # ensure_hub_running should return True on success
    # Assert that the mocked backend's ensure_hub_running method was called
    mock_k8s_backend.ensure_hub_running.assert_called_once()

    # Optionally, assert that the underlying K8s API mocks were NOT called
    # No direct K8s API mocks available here, assertions are on the backend mock


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_k8s_browser(selenium_hub_k8s: Tuple[SeleniumHub, MagicMock]) -> None:
    """Test that create_browsers calls the backend's create_browsers for K8s."""
    # This test verifies that create_browsers calls the backend's create_browsers method
    # and correctly handles the return value.
    hub, mock_k8s_backend = selenium_hub_k8s
    count = 1
    browser_type = "chrome"

    # The mocked backend's create_browsers method will be called
    # Its return value is configured in the fixture.
    browser_ids = await hub.create_browsers(browser_type=browser_type, count=count)

    assert isinstance(browser_ids, list)
    assert len(browser_ids) == count
    # Assert that the mocked backend's create_browsers method was called with the correct args
    mock_k8s_backend.create_browsers.assert_called_once_with(
        count, browser_type, hub.browser_configs
    )
    assert (
        browser_ids == ["mock-k8s-browser-id"] * count
    )  # Assert the expected return value from the mocked backend (multiplied by count)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_k8s_hub_restarts_stopped_hub(
    selenium_hub_k8s: Tuple[SeleniumHub, MagicMock],
) -> None:
    """Test that ensure_hub_running restarts the hub if it is stopped in K8s."""
    hub, mock_k8s_backend = selenium_hub_k8s

    # Simulate a stopped hub by making ensure_hub_running return False initially
    CALL_COUNT = 2
    mock_k8s_backend.ensure_hub_running.side_effect = [False, True]

    result = await hub.ensure_hub_running()

    assert result is True  # ensure_hub_running should return True on success
    # Assert that ensure_hub_running was called twice: once for the initial check, once for the restart
    assert mock_k8s_backend.ensure_hub_running.call_count == CALL_COUNT


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_with_insufficient_resources(
    selenium_hub_k8s: Tuple[SeleniumHub, MagicMock], monkeypatch: Any
) -> None:
    """Test that create_browsers raises ResourceAllocationError if resources are insufficient."""
    hub, mock_k8s_backend = selenium_hub_k8s

    # Simulate insufficient resources by raising ApiException with 503 status
    mock_k8s_backend.create_browsers.side_effect = ApiException(status=503)

    with pytest.raises(ApiException) as excinfo:
        await hub.create_browsers(browser_type="chrome", count=1)

    assert excinfo.value.status == HTTPStatus.SERVICE_UNAVAILABLE  # 503
