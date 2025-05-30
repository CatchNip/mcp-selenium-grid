"""Pytest configuration file."""

import logging
from typing import Any, Dict, Generator, Optional
from unittest.mock import MagicMock

import docker
import pytest
from app.main import app
from docker.errors import NotFound  # Add NotFound for mocking
from fastapi.testclient import TestClient


def pytest_configure(config: Any) -> None:
    """Configure pytest."""
    # No deprecated asyncio_default_fixture_loop_scope config
    # No-op


# ==============================================================================
# UNIT TEST FIXTURES AND MOCKS (pytest-mock style)
# ==============================================================================


@pytest.fixture
def mock_docker_client(mocker: Any) -> MagicMock:
    """
    Single, DRY fixture for a fully mocked Docker client for all unit tests.
    Uses helper functions for per-test container/network customization.
    """
    client: MagicMock = mocker.MagicMock(name="DockerClientMock")
    # Containers
    containers = mocker.MagicMock(name="ContainersMock")
    containers.list.return_value = []
    containers.get.side_effect = containers.run.side_effect = containers.create.side_effect = (
        lambda *args, **kwargs: create_mock_container(mocker)
    )
    client.containers = containers
    # Networks
    networks = mocker.MagicMock(name="NetworksMock")
    networks.list.return_value = []
    networks.get.side_effect = networks.create.side_effect = (
        lambda *args, **kwargs: create_mock_network(mocker)
    )
    client.networks = networks
    # Images
    images = mocker.MagicMock(name="ImagesMock")
    images.get.return_value = mocker.MagicMock(name="ImageMock")
    images.pull.return_value = mocker.MagicMock(name="ImagePullMock")
    client.images = images
    # API
    api = mocker.MagicMock(name="ApiMock")
    api.create_container.return_value = {"Id": "mock-container-id"}
    api.create_network.return_value = {"Id": "mock-network-id"}
    client.api = api
    # Patch docker.from_env everywhere
    mocker.patch("docker.from_env", return_value=client)
    mocker.patch("app.services.selenium_hub.docker_backend.docker.from_env", return_value=client)
    return client


@pytest.fixture
def docker_not_found() -> type:
    """Fixture to provide docker.errors.NotFound exception class for use in tests."""
    return NotFound


@pytest.fixture
def mock_k8s_clients(mocker: Any) -> tuple[MagicMock, MagicMock]:
    """Fixture that returns MagicMock CoreV1Api and AppsV1Api clients."""
    core = mocker.MagicMock()
    apps = mocker.MagicMock()
    return core, apps


def create_mock_container(
    mocker: Any,
    status: str = "running",
    name: str = "mock-container",
    id: str = "container-id",
    image_tags: Optional[list[str]] = None,
) -> MagicMock:
    """Create a MagicMock Docker container with the given attributes."""
    if image_tags is None:
        image_tags = ["image:latest"]
    mock_container = mocker.MagicMock()
    mock_container.status = status
    mock_container.name = name
    mock_container.id = id
    mock_container.image = mocker.MagicMock(tags=image_tags)
    mock_container.attrs = {"Config": {"Image": image_tags[0]}}
    mock_container.remove = mocker.MagicMock()
    mock_container.restart = mocker.MagicMock()
    mock_container.reload = mocker.MagicMock()
    return mock_container  # type: ignore[no-any-return]


def create_mock_network(
    mocker: Any, name: str = "mock-network", id: str = "network-id"
) -> MagicMock:
    """Create a MagicMock Docker network with the given attributes."""
    mock_network = mocker.MagicMock()
    mock_network.name = name
    mock_network.id = id
    mock_network.remove = mocker.MagicMock()
    return mock_network  # type: ignore[no-any-return]


# ==============================================================================
# INTEGRATION TEST FIXTURES
# ==============================================================================


# ==============================================================================
# E2E TEST FIXTURES
# ==============================================================================


# ==============================================================================
# SHARED TEST FIXTURES
# ==============================================================================


@pytest.fixture(scope="session")
def client() -> TestClient:
    """Create a test client for the FastAPI app with dependency override for verify_token."""
    from app.dependencies import verify_token
    from fastapi.testclient import TestClient

    async def always_valid_token(token: Optional[str] = None) -> Dict[str, str]:
        return {"sub": "test-agent"}

    app.dependency_overrides[verify_token] = always_valid_token
    return TestClient(app)


@pytest.fixture
def auth_headers() -> Dict[str, str]:
    """Create authentication headers for API requests."""
    from app.core.settings import settings

    return {"Authorization": f"Bearer {settings.API_TOKEN}"}


@pytest.fixture
def cleanup_docker_browsers() -> Generator[None, Any, None]:
    """Cleanup Docker containers created by browser tests after each test."""
    client = docker.from_env()
    before = {c.id for c in client.containers.list(all=True)}
    yield
    after = {c.id for c in client.containers.list(all=True)}
    new = after - before
    for cid in new:
        try:
            container = client.containers.get(cid)
            image = getattr(container.image, "tags", [])
            # Remove if container image is a Selenium browser node
            if any(tag.startswith("selenium/node-") for tag in image):
                container.remove(force=True)
        except Exception:
            logging.exception("Exception occurred while cleaning up container")
