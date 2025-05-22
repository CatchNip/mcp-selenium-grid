"""Unit tests for DockerHubBackend."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from app.core.settings import Settings
from app.services.selenium_hub.docker_backend import DockerHubBackend
from docker.errors import APIError, NotFound


# Define helper functions to create mock objects
def create_mock_container(
    status="running", name="mock-container", id="container-id", image_tags=["image:latest"]
):
    mock_container = MagicMock(spec=object)  # Use spec=object for a more flexible mock
    mock_container.status = status
    mock_container.name = name
    mock_container.id = id
    mock_container.image = MagicMock(tags=image_tags)
    mock_container.attrs = {
        "Config": {"Image": image_tags[0]}
    }  # Add attrs for image check in create_browsers
    mock_container.remove = MagicMock()
    mock_container.restart = MagicMock()  # Add mock restart method
    mock_container.reload = MagicMock()
    return mock_container


def create_mock_network(name="mock-network", id="network-id"):
    mock_network = MagicMock()
    mock_network.name = name
    mock_network.id = id
    mock_network.remove = MagicMock()
    return mock_network


# Fixture for mocking Docker client
@pytest.fixture
def mock_docker_client():
    mock_client = MagicMock()

    # Create specific mock containers for tests
    mock_hub_container_running = create_mock_container(
        status="running", name="selenium-hub", id="hub-container-id"
    )
    mock_hub_container_exited = create_mock_container(
        status="exited", name="selenium-hub", id="hub-container-id"
    )
    mock_browser_container_running = create_mock_container(
        name="test-browser", id="existing-container-id", image_tags=["image:latest"]
    )

    mock_selenium_grid_network = create_mock_network(name="selenium-grid")

    mock_client.containers.run.return_value = create_mock_container(
        id="new-container-id"
    )  # Return a distinct mock for run
    mock_client.containers.list.return_value = [
        mock_hub_container_running,
        mock_hub_container_exited,
        mock_browser_container_running,
    ]  # Include all potential containers in list
    mock_client.networks.create.return_value = mock_selenium_grid_network

    # Configure side_effect for get to return specific mock objects based on input
    def containers_get_side_effect(name_or_id):
        if name_or_id == "selenium-hub":
            # In ensure_hub_running_restarts_stopped_hub, the test explicitly sets the return value. For other tests, return running.
            return getattr(
                mock_client.containers.get, "_explicit_return_value", mock_hub_container_running
            )
        elif name_or_id == "existing-container-id":
            return mock_browser_container_running
        raise NotFound(f"Container '{name_or_id}' not found")

    mock_client.containers.get.side_effect = containers_get_side_effect

    mock_client.networks.get.side_effect = lambda name: (
        mock_selenium_grid_network
        if name == "selenium-grid"
        else NotFound(f"Network '{name}' not found")
    )
    yield mock_client


# Fixture for creating a DockerHubBackend instance with mocked settings
@pytest.fixture
def docker_backend(mock_docker_client, monkeypatch):
    # Mock settings with necessary attributes
    mock_settings = MagicMock(spec=Settings)
    mock_settings.SELENIUM_HUB_PORT = 4444
    mock_settings.MAX_BROWSER_INSTANCES = 10
    mock_settings.SE_NODE_MAX_SESSIONS = 5

    with patch(
        "app.services.selenium_hub.docker_backend.docker.from_env", return_value=mock_docker_client
    ):
        backend = DockerHubBackend(mock_settings)
        yield backend, mock_docker_client


@pytest.mark.unit
def test_cleanup_removes_resources(docker_backend):
    backend, mock_client = docker_backend

    backend.cleanup()

    # Verify container and network removal attempts
    mock_client.containers.get.assert_any_call("selenium-hub")
    mock_client.networks.get.assert_any_call("selenium-grid")
    mock_client.networks.get("selenium-grid").remove.assert_called_once()


@pytest.mark.unit
def test_cleanup_handles_not_found(docker_backend):
    backend, mock_client = docker_backend

    # Simulate resources not found
    mock_client.containers.get.side_effect = NotFound("Container not found")
    mock_client.networks.get.side_effect = NotFound("Network not found")

    try:
        backend.cleanup()
    except Exception as e:
        pytest.fail(f"cleanup raised an unexpected exception: {e}")

    mock_client.containers.get.assert_called_once_with("selenium-hub")
    mock_client.networks.get.assert_any_call("selenium-grid")
    # When NotFound is raised by containers.get, accessing .remove on the result should not happen, so no assertion on .remove is needed here.
    # The test passes if no exception is raised.


@pytest.mark.unit
def test_cleanup_handles_api_error(docker_backend):
    backend, mock_client = docker_backend

    # Configure mock objects and their side effects for API errors
    mock_container = create_mock_container(name="selenium-hub")
    mock_container.remove.side_effect = APIError("Docker API Error")

    mock_network = create_mock_network(name="selenium-grid")
    mock_network.remove.side_effect = APIError("Docker API Error")

    # Set the side_effect for get to return the specific mock container and network
    mock_client.containers.get.side_effect = lambda name_or_id: (
        mock_container if name_or_id == "selenium-hub" else NotFound("Not Found")
    )
    mock_client.networks.get.side_effect = lambda name: (
        mock_network if name == "selenium-grid" else NotFound("Not Found")
    )

    try:
        backend.cleanup()
    except Exception as e:
        pytest.fail(f"cleanup raised an unexpected exception: {e}")

    # Assertions on the specific mock objects
    mock_client.containers.get.assert_called_once_with("selenium-hub")  # Verify get was called
    mock_client.networks.get.assert_any_call("selenium-grid")
    mock_container.remove.assert_called_once_with(
        force=True
    )  # Verify remove was called on the mock container
    mock_network.remove.assert_called_once()  # Verify remove was called on the mock network


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_hub_running_creates_resources(docker_backend):
    backend, mock_client = docker_backend

    # Simulate resources not found
    mock_client.networks.get.side_effect = NotFound("Network not found")
    mock_client.containers.get.side_effect = NotFound("Container not found")

    result = await backend.ensure_hub_running({})

    assert result is True
    mock_client.networks.create.assert_called_once_with("selenium-grid", driver="bridge")
    mock_client.containers.run.assert_called_once_with(
        "selenium/hub:4.18.1",
        name="selenium-hub",
        detach=True,
        network="selenium-grid",
        ports={f"{backend.settings.SELENIUM_HUB_PORT}/tcp": backend.settings.SELENIUM_HUB_PORT},
        environment={
            "SE_EVENT_BUS_HOST": "selenium-hub",
            "SE_EVENT_BUS_PUBLISH_PORT": "4442",
            "SE_EVENT_BUS_SUBSCRIBE_PORT": "4443",
            "SE_NODE_MAX_SESSIONS": str(backend.settings.MAX_BROWSER_INSTANCES or 10),
            "SE_NODE_OVERRIDE_MAX_SESSIONS": "true",
        },
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_hub_running_resources_exist(docker_backend):
    backend, mock_client = docker_backend

    # Simulate resources already existing and running
    mock_client.networks.get.return_value = MagicMock(name="selenium-grid")
    mock_client.containers.get.return_value = MagicMock(status="running", name="selenium-hub")

    result = await backend.ensure_hub_running({})

    assert result is True
    mock_client.networks.create.assert_not_called()
    mock_client.containers.run.assert_not_called()
    mock_client.containers.get.return_value.restart.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_hub_running_restarts_stopped_hub(docker_backend):
    backend, mock_client = docker_backend

    # Simulate hub container existing but not running
    mock_hub_container = create_mock_container(status="exited", name="selenium-hub")

    # Set an attribute on the mock client to indicate the desired return value for get('selenium-hub')
    # The fixture's side_effect will check for this attribute.
    mock_client.containers.get._explicit_return_value = mock_hub_container

    result = await backend.ensure_hub_running({})

    assert result is True
    mock_client.networks.create.assert_not_called()
    mock_client.containers.run.assert_not_called()
    mock_hub_container.restart.assert_called_once()  # Assert restart was called on the specific container mock


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_hub_running_api_error(docker_backend):
    backend, mock_client = docker_backend

    # Simulate API error when getting network
    mock_client.networks.get.side_effect = APIError("Docker API Error")

    result = await backend.ensure_hub_running({})

    assert result is False
    mock_client.networks.create.assert_not_called()
    mock_client.containers.get.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_success(docker_backend):
    backend, mock_client = docker_backend

    # Define browser configurations with the expected structure
    browser_configs = {
        "chrome": {
            "image": "selenium/node-chrome:latest",
            "resources": {"memory": "1G", "cpu": "0.5"},
        }
    }
    count = 2
    browser_type = "chrome"

    # Ensure mock_client.images.get returns a mock image with tags
    mock_client.images.get.return_value = MagicMock(tags=[browser_configs[browser_type]["image"]])

    # Ensure mock_client.containers.run returns a mock container with id and attrs
    mock_client.containers.run.side_effect = lambda *args, **kwargs: create_mock_container(
        id=f"container-{uuid.uuid4().hex[:8]}", image_tags=[kwargs.get("image", "image:latest")]
    )

    browser_ids = await backend.create_browsers(count, browser_type, browser_configs)

    assert isinstance(browser_ids, list)
    assert len(browser_ids) == count
    assert all(isinstance(id, str) for id in browser_ids)
    assert mock_client.images.get.call_count == count
    assert mock_client.containers.run.call_count == count

    # Verify calls to create containers
    for call_args in mock_client.containers.run.call_args_list:
        _, kwargs = call_args
        assert call_args[0][0] == browser_configs[browser_type]["image"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_image_not_found(docker_backend):
    backend, mock_client = docker_backend

    browser_configs = {
        "chrome": {
            "image": "selenium/node-chrome:latest",
            "resources": {"memory": "1G", "cpu": "0.5"},
        }
    }
    count = 1
    browser_type = "chrome"

    # Simulate image not found, requiring a pull
    mock_client.images.get.side_effect = [NotFound("Image not found"), MagicMock()]
    mock_client.containers.run.return_value = MagicMock(id="new-container-id")

    browser_ids = await backend.create_browsers(count, browser_type, browser_configs)

    assert isinstance(browser_ids, list)
    assert len(browser_ids) == count
    mock_client.images.get.assert_called_once_with(browser_configs[browser_type]["image"])
    mock_client.images.pull.assert_called_once_with(browser_configs[browser_type]["image"])
    mock_client.containers.run.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_api_error_on_image_get(docker_backend):
    backend, mock_client = docker_backend

    browser_configs = {
        "chrome": {
            "image": "selenium/node-chrome:latest",
            "resources": {"memory": "1G", "cpu": "0.5"},
        }
    }
    count = 1
    browser_type = "chrome"

    # Simulate API error when getting image
    mock_client.images.get.side_effect = APIError("Docker API Error")

    browser_ids = await backend.create_browsers(count, browser_type, browser_configs)

    assert isinstance(browser_ids, list)
    assert len(browser_ids) == 0  # Browser creation should be skipped
    mock_client.images.get.assert_called_once_with(browser_configs[browser_type]["image"])
    mock_client.images.pull.assert_not_called()
    mock_client.containers.run.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_api_error_on_container_run(docker_backend):
    backend, mock_client = docker_backend

    browser_configs = {
        "chrome": {
            "image": "selenium/node-chrome:latest",
            "resources": {"memory": "1G", "cpu": "0.5"},
        }
    }
    count = 1
    browser_type = "chrome"

    # Simulate API error when running container
    mock_client.containers.run.side_effect = APIError("Docker API Error")

    browser_ids = await backend.create_browsers(count, browser_type, browser_configs)

    assert isinstance(browser_ids, list)
    assert len(browser_ids) == 0  # Browser creation should be skipped
    mock_client.images.get.assert_called_once()
    mock_client.images.pull.assert_not_called()
    mock_client.containers.run.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_browser_status_found(docker_backend):
    backend, mock_client = docker_backend
    browser_id = "existing-container-id"
    mock_container = MagicMock(id=browser_id, status="running", name="test-browser")
    mock_container.image = MagicMock(tags=["image:latest"])
    mock_client.containers.get.return_value = mock_container

    status = await backend.get_browser_status(browser_id)

    assert "id" in status
    assert "status" in status
    assert "name" in status
    assert "image" in status
    assert status["status"] == "running"
    assert status["name"] == "test-browser"
    assert status["image"] == "image:latest"
    mock_client.containers.get.assert_called_once_with(browser_id)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_browser_status_not_found(docker_backend):
    backend, mock_client = docker_backend
    browser_id = "non-existing-container-id"
    mock_client.containers.get.side_effect = NotFound("Container not found")

    status = await backend.get_browser_status(browser_id)

    assert status["status"] == "not found"
    mock_client.containers.get.assert_called_once_with(browser_id)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_browser_status_api_error(docker_backend):
    backend, mock_client = docker_backend
    browser_id = "existing-container-id"
    mock_client.containers.get.side_effect = APIError("Docker API Error")

    status = await backend.get_browser_status(browser_id)

    assert status["status"] == "error"
    assert "Docker API Error" in status["message"]
    mock_client.containers.get.assert_called_once_with(browser_id)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_browser_status_unexpected_error(docker_backend):
    backend, mock_client = docker_backend
    browser_id = "existing-container-id"
    mock_client.containers.get.side_effect = Exception("Unexpected Error")

    status = await backend.get_browser_status(browser_id)

    assert status["status"] == "error"
    assert "Unexpected Error" in status["message"]
    mock_client.containers.get.assert_called_once_with(browser_id)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_unsupported_type(docker_backend):
    backend, mock_client = docker_backend
    browser_configs = {
        "chrome": {
            "image": "selenium/node-chrome:latest",
            "resources": {"memory": "1G", "cpu": "0.5"},
        }
    }
    with pytest.raises(KeyError, match="'invalid'"):
        await backend.create_browsers(1, "invalid", browser_configs)
