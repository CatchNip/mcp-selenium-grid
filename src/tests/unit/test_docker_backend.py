"""Unit tests for DockerHubBackend."""

import uuid
from typing import Any, Dict, Generator, List, Tuple, cast
from unittest.mock import MagicMock, patch

import pytest
from app.core.models import BrowserConfig, ContainerResources
from app.core.settings import Settings
from app.services.selenium_hub.docker_backend import DockerHubBackend
from docker.errors import APIError, NotFound

DOCKER_CONTAINER_ID_SHORTHAND_LENGTH = 12


# Define helper functions to create mock objects
def create_mock_container(
    status: str = "running",
    name: str = "mock-container",
    id: str = "container-id",
    image_tags: List[str] = ["image:latest"],
) -> MagicMock:
    mock_container = MagicMock()
    mock_container.status = status
    mock_container.name = name
    mock_container.id = id
    mock_container.image = MagicMock(tags=image_tags)
    mock_container.attrs = {
        "Config": {"Image": image_tags[0]}
    }  # Add attrs for image check in create_browsers
    mock_container.remove = MagicMock()
    mock_container.restart = MagicMock()
    mock_container.reload = MagicMock()  # Ensure reload is a fresh MagicMock for each container
    return mock_container


def create_mock_network(name: str = "mock-network", id: str = "network-id") -> MagicMock:
    mock_network = MagicMock()
    mock_network.name = name
    mock_network.id = id
    mock_network.remove = MagicMock()
    return mock_network


# Fixture for mocking Docker client
@pytest.fixture
def mock_docker_client() -> Generator[MagicMock, Any, Any]:
    mock_client = MagicMock()

    # Create specific mock containers for tests
    mock_hub_container_running = create_mock_container(
        status="running", name="selenium-hub", id="hub-container-id"
    )
    mock_hub_container_exited = create_mock_container(
        status="exited", name="selenium-hub", id="hub-container-id"
    )
    # Create a specific mock browser container instance that the fixture will return
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
    def containers_get_side_effect(name_or_id: str) -> MagicMock:
        if name_or_id == "selenium-hub":
            # In ensure_hub_running_restarts_stopped_hub, the test explicitly sets the return value. For other tests, return running.
            # Assuming the explicit return value is always a MagicMock in this test context
            return cast(
                MagicMock,
                getattr(
                    mock_client.containers.get,
                    "_explicit_return_value",
                    create_mock_container(
                        status="running", name="selenium-hub", id="hub-container-id"
                    ),  # Return a fresh mock
                ),
            )
        elif name_or_id == "existing-container-id":
            # Store the specific mock browser container instance and return it
            mock_client._returned_browser_container = mock_browser_container_running
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
def docker_backend(
    mock_docker_client: MagicMock, monkeypatch: Any
) -> Generator[Tuple[DockerHubBackend, MagicMock], Any, Any]:
    # Mock settings with necessary attributes
    mock_settings = MagicMock(spec=Settings)
    mock_settings.SELENIUM_HUB_PORT = 4444
    mock_settings.MAX_BROWSER_INSTANCES = 10
    mock_settings.SE_NODE_MAX_SESSIONS = 5

    with patch(
        "app.services.selenium_hub.docker_backend.docker.from_env", return_value=mock_docker_client
    ):
        backend = DockerHubBackend(mock_settings)
        backend.client = mock_docker_client  # Assign mock client to backend
        yield backend, mock_docker_client


@pytest.mark.unit
def test_cleanup_removes_resources(docker_backend: Tuple[DockerHubBackend, MagicMock]) -> None:
    backend, mock_client = docker_backend

    backend.cleanup()

    # Verify container and network removal attempts
    mock_client.containers.get.assert_any_call("selenium-hub")
    mock_client.networks.get.assert_any_call("selenium-grid")
    mock_client.networks.get("selenium-grid").remove.assert_called_once()


@pytest.mark.unit
def test_cleanup_handles_not_found(docker_backend: Tuple[DockerHubBackend, MagicMock]) -> None:
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
def test_cleanup_handles_api_error(docker_backend: Tuple[DockerHubBackend, MagicMock]) -> None:
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
async def test_ensure_hub_running_creates_resources(
    docker_backend: Tuple[DockerHubBackend, MagicMock],
) -> None:
    backend, mock_client = docker_backend

    # Simulate resources not found
    mock_client.networks.get.side_effect = NotFound("Network not found")
    mock_client.containers.get.side_effect = NotFound("Container not found")

    result = await backend.ensure_hub_running()

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
async def test_ensure_hub_running_resources_exist(
    docker_backend: Tuple[DockerHubBackend, MagicMock],
) -> None:
    backend, mock_client = docker_backend

    # Simulate resources already existing and running
    mock_client.networks.get.return_value = MagicMock(name="selenium-grid")
    mock_client.containers.get.return_value = MagicMock(status="running", name="selenium-hub")

    result = await backend.ensure_hub_running()

    assert result is True
    mock_client.networks.create.assert_not_called()
    mock_client.containers.run.assert_not_called()
    mock_client.containers.get.return_value.restart.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_hub_running_restarts_stopped_hub(
    docker_backend: Tuple[DockerHubBackend, MagicMock],
) -> None:
    backend, mock_client = docker_backend

    # Simulate hub container existing but not running
    mock_hub_container = create_mock_container(status="exited", name="selenium-hub")

    # Set an attribute on the mock client to indicate the desired return value for get('selenium-hub')
    # The fixture's side_effect will check for this attribute.
    mock_client.containers.get._explicit_return_value = mock_hub_container

    result = await backend.ensure_hub_running()

    assert result is True
    mock_client.networks.create.assert_not_called()
    mock_client.containers.run.assert_not_called()
    mock_hub_container.restart.assert_called_once()  # Assert restart was called on the specific container mock


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_hub_running_api_error(
    docker_backend: Tuple[DockerHubBackend, MagicMock],
) -> None:
    backend, mock_client = docker_backend

    # Simulate API error when getting network
    mock_client.networks.get.side_effect = APIError("Docker API Error")

    result = await backend.ensure_hub_running()

    assert result is False
    mock_client.networks.create.assert_not_called()
    mock_client.containers.get.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_success(docker_backend: Tuple[DockerHubBackend, MagicMock]) -> None:
    backend, mock_client = docker_backend

    # Define browser configurations with BrowserConfig instances
    browser_configs: Dict[str, BrowserConfig] = {
        "chrome": BrowserConfig(
            image="selenium/node-chrome:latest",
            resources=ContainerResources(memory="1G", cpu="500"),
            port=4444,
        )
    }
    count = 2
    browser_type = "chrome"

    # Ensure mock_client.images.get returns a mock image with tags
    mock_client.images.get.return_value = MagicMock(tags=[browser_configs[browser_type].image])

    # Ensure mock_client.containers.run returns a mock container with id and attrs
    mock_client.containers.run.side_effect = lambda *args, **kwargs: create_mock_container(
        id=f"container-{uuid.uuid4().hex[:8]}", image_tags=[kwargs.get("image", "image:latest")]
    )

    browser_ids = await backend.create_browsers(count, browser_type, browser_configs)

    assert isinstance(browser_ids, list)
    assert len(browser_ids) == count
    mock_client.images.get.assert_called_with(browser_configs[browser_type].image)
    assert mock_client.images.get.call_count == count
    assert mock_client.images.pull.call_count == 0
    assert mock_client.containers.run.call_count == count
    for browser_id in browser_ids:
        assert isinstance(browser_id, str)
        assert len(browser_id) == DOCKER_CONTAINER_ID_SHORTHAND_LENGTH


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_image_not_found(
    docker_backend: Tuple[DockerHubBackend, MagicMock],
) -> None:
    backend, mock_client = docker_backend

    browser_configs: Dict[str, BrowserConfig] = {
        "chrome": BrowserConfig(
            image="selenium/node-chrome:latest",
            resources=ContainerResources(memory="1G", cpu="500"),
            port=4444,
        )
    }
    count = 1
    browser_type = "chrome"

    # Simulate image not found, requiring a pull
    mock_client.images.get.side_effect = [
        NotFound("Image not found"),
        MagicMock(tags=[browser_configs[browser_type].image]),
    ]
    mock_client.containers.run.return_value = MagicMock(id="new-container-id")

    browser_ids = await backend.create_browsers(count, browser_type, browser_configs)

    assert isinstance(browser_ids, list)
    assert len(browser_ids) == count
    mock_client.images.get.assert_called_once_with(browser_configs[browser_type].image)
    mock_client.images.pull.assert_called_once_with(browser_configs[browser_type].image)
    mock_client.containers.run.assert_called_once()
    assert isinstance(browser_ids[0], str)
    assert len(browser_ids[0]) == DOCKER_CONTAINER_ID_SHORTHAND_LENGTH


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_api_error_on_image_get(
    docker_backend: Tuple[DockerHubBackend, MagicMock],
) -> None:
    backend, mock_client = docker_backend

    browser_configs: Dict[str, BrowserConfig] = {
        "chrome": BrowserConfig(
            image="selenium/node-chrome:latest",
            resources=ContainerResources(memory="1G", cpu="500"),
            port=4444,
        )
    }
    count = 1
    browser_type = "chrome"

    # Simulate API error when getting image
    mock_client.images.get.side_effect = APIError("Docker API Error")

    browser_ids = await backend.create_browsers(count, browser_type, browser_configs)

    assert isinstance(browser_ids, list)
    assert len(browser_ids) == 0  # Should skip browser creation on error
    mock_client.images.get.assert_called_once_with(browser_configs[browser_type].image)
    mock_client.images.pull.assert_not_called()
    mock_client.containers.run.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_api_error_on_container_run(
    docker_backend: Tuple[DockerHubBackend, MagicMock],
) -> None:
    backend, mock_client = docker_backend

    browser_configs: Dict[str, BrowserConfig] = {
        "chrome": BrowserConfig(
            image="selenium/node-chrome:latest",
            resources=ContainerResources(memory="1G", cpu="500"),
            port=4444,
        )
    }
    count = 1
    browser_type = "chrome"

    # Simulate API error when running container
    mock_client.images.get.return_value = MagicMock(
        tags=[browser_configs[browser_type].image]
    )  # Image exists
    mock_client.containers.run.side_effect = APIError("Docker API Error")

    browser_ids = await backend.create_browsers(count, browser_type, browser_configs)

    assert isinstance(browser_ids, list)
    assert len(browser_ids) == 0  # Should skip browser creation on error
    mock_client.images.get.assert_called_once_with(browser_configs[browser_type].image)
    mock_client.images.pull.assert_not_called()
    mock_client.containers.run.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_browser_status_found(docker_backend: Tuple[DockerHubBackend, MagicMock]) -> None:
    backend, mock_client = docker_backend
    # Create a specific mock container for this test directly (defined in fixture)
    # We rely on the fixture's side_effect to return the correct mock.
    # mock_container is created in the fixture and its reload is mocked there.

    status = await backend.get_browser_status("existing-container-id")

    # Get the mock container instance that was returned by the mocked get call
    # This should be the mock_container defined in the fixture with the mocked reload
    # Access the returned value from the call history
    returned_mock_container = mock_client.containers.get.call_args[0][0]
    # We need to retrieve the actual mock object returned by the side_effect
    # which should be the one defined in the fixture.
    # A simpler way is to check the mock object stored by the side_effect logic.
    returned_mock_container = mock_client._returned_browser_container

    print(f"Returned mock container: {returned_mock_container}")  # Debug print
    print(
        f"Returned mock container reload call count: {returned_mock_container.reload.call_count}"
    )  # Debug print

    mock_client.containers.get.assert_called_once_with("existing-container-id")
    # Assert reload was called on the mock container instance returned by get
    returned_mock_container.reload.assert_called_once()
    status_dict: Dict[str, Any] = status  # Add type hint for status
    assert status_dict["status"] == "running"
    assert status_dict["id"] == "existing-container-id"[:12].lower()
    assert status_dict["image"] == "image:latest"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_browser_status_not_found(
    docker_backend: Tuple[DockerHubBackend, MagicMock],
) -> None:
    backend, mock_client = docker_backend
    mock_client.containers.get.side_effect = NotFound("container not found")

    status = await backend.get_browser_status("non-existing-container-id")

    mock_client.containers.get.assert_called_once_with("non-existing-container-id")
    status_dict: Dict[str, Any] = status  # Add type hint for status
    assert status_dict["status"] == "not found"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_browser_status_api_error(
    docker_backend: Tuple[DockerHubBackend, MagicMock],
) -> None:
    backend, mock_client = docker_backend
    mock_client.containers.get.side_effect = APIError("Docker API Error")

    status = await backend.get_browser_status("existing-container-id")

    mock_client.containers.get.assert_called_once_with("existing-container-id")
    status_dict: Dict[str, Any] = status  # Add type hint for status
    assert status_dict["status"] == "error"
    assert "Docker API Error" in status_dict["message"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_browser_status_unexpected_error(
    docker_backend: Tuple[DockerHubBackend, MagicMock],
) -> None:
    backend, mock_client = docker_backend
    mock_client.containers.get.side_effect = Exception("Unexpected Error")

    status = await backend.get_browser_status("existing-container-id")

    mock_client.containers.get.assert_called_once_with("existing-container-id")
    status_dict: Dict[str, Any] = status  # Add type hint for status
    assert status_dict["status"] == "error"
    assert "Unexpected Error" in status_dict["message"]
