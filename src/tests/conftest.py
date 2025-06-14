"""Pytest configuration file."""

from typing import Any, Dict, Generator, Optional, Tuple
from unittest.mock import MagicMock

import app.core.settings as core_settings
import pytest
from app.core.models import BrowserConfig, ContainerResources, DeploymentMode
from app.core.settings import Settings
from app.dependencies import get_settings
from app.services.selenium_hub import SeleniumHub
from app.services.selenium_hub.docker_backend import DockerHubBackend
from app.services.selenium_hub.k8s_backend import KubernetesHubBackend
from docker.errors import NotFound  # Add NotFound for mocking
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.testclient import TestClient
from httpx import BasicAuth
from pydantic import SecretStr
from pytest import FixtureRequest
from pytest_mock import MockerFixture


def pytest_configure(config: Any) -> None:
    """Configure pytest."""
    # No deprecated asyncio_default_fixture_loop_scope config
    # No-op


# ==============================================================================
# UNIT TEST FIXTURES AND MOCKS
# ==============================================================================


# DOCKER ========================================================================


def create_mock_container(
    mocker: MockerFixture,
    status: str = "running",
    name: str = "mock-container",
    id: str = "container-id",
    image_tags: Optional[list[str]] = None,
) -> MagicMock:
    """Create a MagicMock Docker container with the given attributes."""
    if image_tags is None:
        image_tags = ["image:latest"]
    mock_container: MagicMock = mocker.MagicMock()
    mock_container.status = status
    mock_container.name = name
    mock_container.id = id
    mock_container.image = mocker.MagicMock(tags=image_tags)
    mock_container.attrs = {"Config": {"Image": image_tags[0]}}
    mock_container.remove = mocker.MagicMock()
    mock_container.restart = mocker.MagicMock()
    mock_container.reload = mocker.MagicMock()
    return mock_container


def create_mock_network(
    mocker: MockerFixture, name: str = "mock-network", id: str = "network-id"
) -> MagicMock:
    """Create a MagicMock Docker network with the given attributes."""
    mock_network: MagicMock = mocker.MagicMock()
    mock_network.name = name
    mock_network.id = id
    mock_network.remove = mocker.MagicMock()
    return mock_network


@pytest.fixture
def mock_docker_client(mocker: MockerFixture) -> MagicMock:
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
def docker_hub_settings(mocker: MockerFixture) -> MagicMock:
    """Fixture to provide a mocked settings object for DockerHubBackend."""
    settings: MagicMock = mocker.MagicMock(spec=core_settings.Settings())
    settings.DEPLOYMENT_MODE = DeploymentMode.DOCKER
    settings.DOCKER_NETWORK = "test-network"
    settings.DOCKER_HUB_IMAGE = "selenium/hub:latest"
    settings.DOCKER_NODE_IMAGE = "selenium/node-chrome:latest"
    settings.MAX_BROWSER_INSTANCES = 8
    settings.SE_NODE_MAX_SESSIONS = 5
    settings.BROWSER_CONFIGS = {
        "chrome": BrowserConfig(
            image="selenium/node-chrome:latest",
            resources=ContainerResources(memory="512M", cpu="0.5"),
            port=4444,
        )
    }  # Mock browser configs with full structure
    settings.SELENIUM_HUB_USER = SecretStr("test-user")
    settings.SELENIUM_HUB_PASSWORD = SecretStr("test-password")
    return settings


@pytest.fixture
def docker_backend(
    mock_docker_client: MagicMock, docker_hub_settings: Settings, mocker: MockerFixture
) -> DockerHubBackend:
    """Fixture for DockerHubBackend with a mocked Docker client."""
    backend = DockerHubBackend(docker_hub_settings)
    # Use mocker to patch docker.from_env to return mock_docker_client
    mocker.patch("docker.from_env", return_value=mock_docker_client)
    return backend


# KUBERNETES ====================================================================


@pytest.fixture
def mock_k8s_apis(mocker: MockerFixture) -> Tuple[MagicMock, MagicMock]:
    """
    Patches CoreV1Api and AppsV1Api so they use MagicMocks for the entire session.
    """

    # Patch kubernetes config loading functions to prevent real K8s environment access
    mocker.patch("kubernetes.config.load_incluster_config", return_value=None)
    mocker.patch("kubernetes.config.load_kube_config", return_value=None)

    core_mock = mocker.patch("kubernetes.client.CoreV1Api").return_value
    apps_mock = mocker.patch("kubernetes.client.AppsV1Api").return_value

    # Default stubs to avoid per-test patching
    # List all methods you want default-stubbed
    core_methods = [
        "read_namespace",
        "create_namespace",
        "create_namespaced_pod",
        "delete_namespaced_pod",
        "read_namespaced_pod",
        "create_namespaced_service",
        "delete_namespaced_service",
        "read_namespaced_service",
    ]
    for m in core_methods:
        setattr(core_mock, m, MagicMock())

    apps_methods = [
        "create_namespaced_deployment",
        "delete_namespaced_deployment",
        "read_namespaced_deployment",
    ]
    for m in apps_methods:
        setattr(apps_mock, m, MagicMock())

    return core_mock, apps_mock


@pytest.fixture
def k8s_hub_settings(mocker: MockerFixture) -> MagicMock:
    """Fixture to provide a mocked settings object for KubernetesHubBackend."""
    settings: MagicMock = mocker.MagicMock(spec=core_settings.Settings())
    settings.DEPLOYMENT_MODE = DeploymentMode.KUBERNETES
    settings.K8S_K8S_CONTEXT = "test-context"
    settings.K8S_NAMESPACE = "test-namespace"
    settings.K8S_SELENIUM_GRID_SERVICE_NAME = "test-service-name"
    settings.K8S_MAX_RETRIES = 3
    settings.K8S_RETRY_DELAY_SECONDS = 0
    settings.MAX_BROWSER_INSTANCES = 8
    settings.SE_NODE_MAX_SESSIONS = 5
    settings.BROWSER_CONFIGS = {
        "chrome": BrowserConfig(
            image="selenium/node-chrome:latest",
            resources=ContainerResources(memory="512M", cpu="0.5"),
            port=4444,
        )
    }  # Mock browser configs with full structure
    settings.SELENIUM_HUB_USER = SecretStr("test-user")
    settings.SELENIUM_HUB_PASSWORD = SecretStr("test-password")
    return settings


@pytest.fixture
def k8s_backend(
    mock_k8s_apis: tuple[MagicMock, MagicMock],
    k8s_hub_settings: Settings,
    mocker: MockerFixture,
) -> Generator[KubernetesHubBackend, None, None]:
    """Fixture that yields a KubernetesHubBackend instance with mocked K8s clients."""

    mocker.patch.object(KubernetesHubBackend, "_load_k8s_config", return_value=None)

    core, apps = mock_k8s_apis
    backend = KubernetesHubBackend(k8s_hub_settings)

    backend.k8s_core = core
    backend.k8s_apps = apps

    # Patch docker.from_env everywhere in k8s fixture too, to prevent accidental Docker usage
    mocker.patch("docker.from_env", return_value=mock_docker_client)
    mocker.patch(
        "app.services.selenium_hub.docker_backend.docker.from_env", return_value=mock_docker_client
    )

    yield backend


# ==============================================================================
# INTEGRATION TEST FIXTURES
# ==============================================================================


@pytest.fixture
def selenium_hub_basic_auth_headers() -> BasicAuth:
    """Fixture to provide HTTP Basic Auth for Selenium Hub."""
    settings = get_settings()
    return BasicAuth(
        settings.SELENIUM_HUB_USER.get_secret_value(),
        settings.SELENIUM_HUB_PASSWORD.get_secret_value(),
    )


# ==============================================================================
# E2E TEST FIXTURES
# ==============================================================================


# ==============================================================================
# SHARED TEST FIXTURES
# ==============================================================================


# Client fixture used by Integration and E2E tests
@pytest.fixture(scope="session", params=[DeploymentMode.DOCKER, DeploymentMode.KUBERNETES])
def client(request: FixtureRequest) -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app with dependency override for verify_token."""
    from app.dependencies import verify_token
    from app.main import create_application
    from fastapi.testclient import TestClient

    # HTTP Bearer token setup
    security = HTTPBearer()

    app = create_application()

    # Override settings based on deployment mode
    settings = get_settings()
    settings.DEPLOYMENT_MODE = request.param
    app.dependency_overrides[get_settings] = lambda: settings

    async def verify_token_override(
        credentials: HTTPAuthorizationCredentials = Depends(security),
    ) -> Dict[str, str]:
        if not credentials or not credentials.credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing token",
            )
        return {"sub": "api-user"}

    app.dependency_overrides[verify_token] = verify_token_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}


def reset_selenium_hub_singleton() -> None:
    """Reset the SeleniumHub singleton instance."""
    SeleniumHub._instance = None
    SeleniumHub._initialized = False


@pytest.fixture
def auth_headers() -> Dict[str, str]:
    """Create authentication headers for API requests."""
    return {"Authorization": f"Bearer {get_settings().API_TOKEN.get_secret_value()}"}
