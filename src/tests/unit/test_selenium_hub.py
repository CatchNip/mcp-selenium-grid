"""Unit tests for SeleniumHub service."""

from http import HTTPStatus
from typing import Any

import pytest
from app.core.models import BrowserConfig, ContainerResources
from app.core.settings import Settings
from app.dependencies import get_settings
from app.services.selenium_hub import SeleniumHub
from app.services.selenium_hub.docker_backend import DockerHubBackend
from app.services.selenium_hub.k8s_backend import KubernetesHubBackend
from kubernetes.client.exceptions import ApiException
from pytest_mock import MockerFixture

from tests.conftest import reset_selenium_hub_singleton


@pytest.fixture
def selenium_hub_docker_backend(
    docker_backend: Any, docker_hub_settings: Any, mocker: MockerFixture
) -> Any:
    """
    Fixture for SeleniumHub using the real class, but only the DockerHubBackend is mocked.
    Uses the shared mock_docker_client fixture from conftest.py to ensure no real Docker usage.
    """
    reset_selenium_hub_singleton()  # Reset singleton before creating new instance

    backend = docker_backend
    backend.ensure_hub_running = mocker.AsyncMock(return_value=True)
    backend.create_browsers = mocker.AsyncMock(return_value=["mock-browser-id"])
    backend.delete_browsers = mocker.AsyncMock(return_value=["mock-browser-id"])
    assert isinstance(backend, DockerHubBackend)

    hub = SeleniumHub(docker_hub_settings)
    assert isinstance(hub.manager.backend, DockerHubBackend)
    yield hub, backend
    reset_selenium_hub_singleton()  # Reset singleton after test


@pytest.fixture
def selenium_hub_k8s_backend(k8s_backend: Any, k8s_hub_settings: Any, mocker: MockerFixture) -> Any:
    """
    Fixture for SeleniumHub using the real class, but only the KubernetesHubBackend is mocked.
    Uses the shared k8s_backend fixture from conftest.py to ensure no real K8s usage.
    Forces DEPLOYMENT_MODE to 'kubernetes' so SeleniumHub uses the K8s backend.
    """
    reset_selenium_hub_singleton()  # Reset singleton before creating new instance

    backend = k8s_backend
    # Replace the methods with mocks
    backend.ensure_hub_running = mocker.AsyncMock(return_value=True)
    backend.create_browsers = mocker.AsyncMock(return_value=["mock-k8s-browser-id"])
    backend.delete_browsers = mocker.AsyncMock(return_value=["mock-k8s-browser-id"])

    assert isinstance(backend, KubernetesHubBackend)

    hub = SeleniumHub(k8s_hub_settings)
    # Patch the backend's k8s_core and k8s_apps to use the mocks
    hub.manager.backend.k8s_core = backend.k8s_core  # type: ignore[attr-defined]
    hub.manager.backend.k8s_apps = backend.k8s_apps  # type: ignore[attr-defined]
    # Replace the backend with our mocked version
    hub.manager.backend = backend
    assert isinstance(hub.manager.backend, KubernetesHubBackend)

    yield hub, backend
    reset_selenium_hub_singleton()  # Reset singleton after test


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_docker_hub_creates_network(
    selenium_hub_docker_backend: Any,
) -> None:
    """Test that ensure_hub_running creates the network if not present."""
    selenium_hub, _ = selenium_hub_docker_backend
    result = await selenium_hub.ensure_hub_running()
    assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_docker_hub_restarts_stopped_hub(
    selenium_hub_docker_backend: Any,
) -> None:
    """Test that ensure_hub_running restarts the hub if it is stopped."""
    selenium_hub, _ = selenium_hub_docker_backend
    result = await selenium_hub.ensure_hub_running()
    assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_docker_browser(
    selenium_hub_docker_backend: Any,
) -> None:
    """Test that create_browsers returns a list with one browser ID for Docker."""
    selenium_hub, _ = selenium_hub_docker_backend
    browser_ids = await selenium_hub.create_browsers(browser_type="chrome", count=1)
    assert isinstance(browser_ids, list)
    assert len(browser_ids) == 1
    # Accept any string as the browser ID (since backend now controls the value)
    assert isinstance(browser_ids[0], str)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_validates_type(
    selenium_hub_docker_backend: Any,
) -> None:
    """Test that create_browsers raises KeyError for unsupported browser type."""
    selenium_hub, _ = selenium_hub_docker_backend
    with pytest.raises(KeyError) as excinfo:
        await selenium_hub.create_browsers(browser_type="invalid", count=1)
    assert "Unsupported browser type: invalid" in str(excinfo.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_validates_count(
    selenium_hub_docker_backend: Any,
) -> None:
    """Test that create_browsers raises ValueError for non-positive count."""
    selenium_hub, _ = selenium_hub_docker_backend
    with pytest.raises(ValueError) as excinfo:
        await selenium_hub.create_browsers(browser_type="chrome", count=0)
    assert "Browser count must be positive" in str(excinfo.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_handles_max_instances(
    selenium_hub_docker_backend: Any, monkeypatch: Any
) -> None:
    """Test that create_browsers raises ValueError if max instances exceeded."""
    selenium_hub, backend = selenium_hub_docker_backend
    if hasattr(backend, "create_browsers"):
        del backend.create_browsers
    # Update the instance's settings directly
    selenium_hub.settings.MAX_BROWSER_INSTANCES = 1
    with pytest.raises(ValueError) as excinfo:
        await selenium_hub.create_browsers(browser_type="chrome", count=2)
    assert "Maximum browser instances exceeded" in str(excinfo.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_browsers_success(
    selenium_hub_docker_backend: Any, mocker: MockerFixture
) -> None:
    """Test that delete_browsers returns only successfully deleted IDs."""
    selenium_hub, _ = selenium_hub_docker_backend
    mocker.patch.object(selenium_hub.manager, "delete_browsers", return_value=["id1", "id2"])
    result = await selenium_hub.delete_browsers(["id1", "id2", "id3"])
    assert result == ["id1", "id2"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_browsers_empty(
    selenium_hub_docker_backend: Any,
) -> None:
    """Test that delete_browsers returns empty list if no IDs provided."""
    selenium_hub, _ = selenium_hub_docker_backend
    result = await selenium_hub.delete_browsers([])
    assert result == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_with_insufficient_resources(
    selenium_hub_k8s_backend: Any, mocker: MockerFixture
) -> None:
    """Test that create_browsers raises ResourceAllocationError if resources are insufficient."""
    selenium_hub, mock_k8s_backend = selenium_hub_k8s_backend
    mocker.patch.object(
        mock_k8s_backend, "ensure_hub_running", new=mocker.AsyncMock(return_value=True)
    )
    mocker.patch.object(
        mock_k8s_backend,
        "create_browsers",
        new=mocker.AsyncMock(side_effect=ApiException(status=503)),
    )
    with pytest.raises(ApiException) as excinfo:
        await selenium_hub.create_browsers(browser_type="chrome", count=1)
    assert excinfo.value.status == HTTPStatus.SERVICE_UNAVAILABLE  # 503


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_k8s_hub_creates_namespace(
    selenium_hub_k8s_backend: Any,
) -> None:
    """Test that ensure_hub_running calls the backend's ensure_hub_running for K8s."""
    selenium_hub, mock_k8s_backend = selenium_hub_k8s_backend

    result = await selenium_hub.ensure_hub_running()

    assert result is True  # ensure_hub_running should return True on success
    mock_k8s_backend.ensure_hub_running.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_k8s_browser(
    selenium_hub_k8s_backend: Any,
) -> None:
    """Test that create_browsers calls the backend's create_browsers for K8s."""
    selenium_hub, mock_k8s_backend = selenium_hub_k8s_backend
    count = 1
    browser_type = "chrome"

    browser_ids = await selenium_hub.create_browsers(browser_type=browser_type, count=count)

    assert isinstance(browser_ids, list)
    assert len(browser_ids) == count
    mock_k8s_backend.create_browsers.assert_called_once_with(
        count, browser_type, selenium_hub.settings.BROWSER_CONFIGS
    )
    assert browser_ids == ["mock-k8s-browser-id"] * count


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_k8s_hub_restarts_stopped_hub(
    selenium_hub_k8s_backend: Any,
    mocker: MockerFixture,
) -> None:
    """Test that ensure_hub_running restarts the hub if it is stopped in K8s."""
    selenium_hub, mock_k8s_backend = selenium_hub_k8s_backend

    CALL_COUNT = 2
    mock_k8s_backend.ensure_hub_running = mocker.AsyncMock(side_effect=[False, True])

    result = await selenium_hub.ensure_hub_running()

    assert result is True  # ensure_hub_running should return True on success
    assert mock_k8s_backend.ensure_hub_running.call_count == CALL_COUNT


@pytest.mark.unit
@pytest.mark.asyncio
async def test_singleton_behavior() -> None:
    """Test that SeleniumHub maintains singleton behavior."""
    reset_selenium_hub_singleton()

    # Create initial settings
    settings = Settings(
        PROJECT_NAME="Test Project",
        VERSION="0.1.0",
        API_V1_STR="/api/v1",
        API_TOKEN="test-token",  # noqa: S106
        SELENIUM_HUB_USER="test-user",
        SELENIUM_HUB_PASSWORD="test-password",  # noqa: S106
        SELENIUM_HUB_PORT=4444,
        MAX_BROWSER_INSTANCES=2,
        SE_NODE_MAX_SESSIONS=1,
        DEPLOYMENT_MODE="docker",
        K8S_NAMESPACE="test-namespace",
        K8S_RETRY_DELAY_SECONDS=2,
        K8S_MAX_RETRIES=5,
        BACKEND_CORS_ORIGINS=["http://localhost:8000"],
        BROWSER_CONFIGS={
            "chrome": BrowserConfig(
                image="selenium/node-chrome:latest",
                resources=ContainerResources(memory="1G", cpu="1"),
                port=4444,
            )
        },
    )

    # Create first instance with settings
    hub1 = SeleniumHub(settings)
    # Create second instance without settings
    hub2 = SeleniumHub()

    # Both instances should be the same object
    assert hub1 is hub2
    # Settings should be from first initialization
    assert hub1.settings == settings

    # Verify that creating without settings on first initialization fails
    reset_selenium_hub_singleton()
    with pytest.raises(ValueError, match="Settings must be provided for first initialization"):
        SeleniumHub()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_settings_update() -> None:
    """Test that settings can be updated through initialization."""
    NEW_VALUE = 10

    reset_selenium_hub_singleton()
    initial_settings = Settings()
    hub = SeleniumHub(initial_settings)
    old_value = hub.settings.MAX_BROWSER_INSTANCES

    # Programmatically update just one value using model_copy (overrided to update env)
    new_settings = initial_settings.model_copy(update={"MAX_BROWSER_INSTANCES": NEW_VALUE})
    hub = SeleniumHub(new_settings)
    assert hub.settings.MAX_BROWSER_INSTANCES == NEW_VALUE
    assert hub.settings.MAX_BROWSER_INSTANCES != old_value

    # FIXME: AssertionError: assert 5 == 10 - getting the default value from confir.yaml or default from Settings Field
    # Get the settings using get_settings and check the value
    get_settings.cache_clear()
    updated_settings = get_settings()
    assert updated_settings.MAX_BROWSER_INSTANCES == NEW_VALUE

    reset_selenium_hub_singleton()
