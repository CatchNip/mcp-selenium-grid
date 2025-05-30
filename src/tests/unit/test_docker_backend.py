"""Unit tests for DockerHubBackend."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from app.core.models import BrowserConfig, ContainerResources
from app.services.selenium_hub.docker_backend import DockerHubBackend
from docker.errors import APIError


@pytest.fixture
def docker_backend(mock_docker_client: MagicMock, mocker: MagicMock) -> DockerHubBackend:
    """Fixture for DockerHubBackend with a mocked Docker client."""
    mock_settings = mocker.MagicMock()
    mock_settings.DOCKER_NETWORK = "test-network"
    mock_settings.DOCKER_HUB_IMAGE = "selenium/hub:latest"
    mock_settings.DOCKER_NODE_IMAGE = "selenium/node-chrome:latest"
    mock_settings.SE_NODE_MAX_SESSIONS = 5
    backend = DockerHubBackend(mock_settings)
    # Use mocker to patch docker.from_env to return mock_docker_client
    mocker.patch("docker.from_env", return_value=mock_docker_client)
    return backend


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_hub_running_creates_network(
    docker_backend: DockerHubBackend, mocker: MagicMock
) -> None:
    mocker.patch.object(docker_backend.client.networks, "list", return_value=[])
    mocker.patch.object(docker_backend.client.networks, "create", return_value=mocker.MagicMock())
    mocker.patch.object(docker_backend.client.containers, "list", return_value=[])
    mocker.patch.object(docker_backend.client.containers, "run", return_value=mocker.MagicMock())
    result = await docker_backend.ensure_hub_running()
    assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_hub_running_restarts_stopped_hub(
    docker_backend: DockerHubBackend, mocker: MagicMock
) -> None:
    mock_container = mocker.MagicMock()
    mock_container.status = "exited"
    mocker.patch.object(docker_backend.client.containers, "list", return_value=[mock_container])
    mocker.patch.object(mock_container, "restart")
    result = await docker_backend.ensure_hub_running()
    assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browser_success(docker_backend: DockerHubBackend, mocker: MagicMock) -> None:
    mocker.patch.object(
        docker_backend.client.containers,
        "run",
        return_value=mocker.MagicMock(id="container-123456789012"),
    )
    browser_config = BrowserConfig(
        image="selenium/node-chrome:latest",
        resources=ContainerResources(memory="1G", cpu="1"),
        port=4444,
    )
    result = await docker_backend.create_browsers(1, "chrome", {"chrome": browser_config})
    assert result is not None
    assert isinstance(result[0], str)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browser_failure(docker_backend: DockerHubBackend, mocker: MagicMock) -> None:
    mocker.patch.object(docker_backend.client.containers, "run", side_effect=APIError("fail"))
    browser_config = BrowserConfig(
        image="selenium/node-chrome:latest",
        resources=ContainerResources(memory="1G", cpu="1"),
        port=4444,
    )
    result = await docker_backend.create_browsers(1, "chrome", {"chrome": browser_config})
    assert result == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browser_pulls_image_if_not_found(
    docker_backend: DockerHubBackend, mocker: MagicMock, docker_not_found: Any
) -> None:
    """
    Test that create_browsers triggers a pull if the image is not found, and does not attempt a real pull.
    """
    # Simulate image not found
    mocker.patch.object(
        docker_backend.client.images, "get", side_effect=docker_not_found("not found")
    )
    mock_image_pull = mocker.patch.object(docker_backend.client.images, "pull", return_value=None)
    mocker.patch.object(
        docker_backend.client.containers,
        "run",
        return_value=mocker.MagicMock(id="container-123456789012"),
    )
    browser_config = BrowserConfig(
        image="selenium/node-chrome:latest",
        resources=ContainerResources(memory="1G", cpu="1"),
        port=4444,
    )
    result = await docker_backend.create_browsers(1, "chrome", {"chrome": browser_config})
    assert result is not None
    assert isinstance(result[0], str)
    mock_image_pull.assert_called_once_with("selenium/node-chrome:latest")
