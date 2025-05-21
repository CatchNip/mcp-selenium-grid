"""Pytest configuration file."""

import logging
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import docker
import pytest
from app.main import app
from authlib.jose.errors import ExpiredTokenError, InvalidClaimError
from fastapi.testclient import TestClient
from testcontainers.selenium import BrowserWebDriverContainer


# Mock class for Docker client
class MockDockerClient:
    def __init__(self):
        self.containers = MagicMock()
        self.networks = MagicMock()
        self.containers.list.return_value = []
        self.networks.list.return_value = []
        self.api = MagicMock()
        self.api.create_container.return_value = {"Id": "mock-container-id"}
        self.api.create_network.return_value = {"Id": "mock-network-id"}


# Mock class for Kubernetes client
class MockK8sClient:
    def __init__(self):
        self.CoreV1Api = MagicMock
        self.AppsV1Api = MagicMock


def pytest_configure(config):
    """Configure pytest."""
    # No deprecated asyncio_default_fixture_loop_scope config
    # No-op


# ==============================================================================
# UNIT TEST FIXTURES
# ==============================================================================


@pytest.fixture
def mock_docker_client():
    """Mock Docker client."""
    with patch("docker.from_env") as mock:
        mock.return_value = MockDockerClient()
        yield mock


@pytest.fixture
def mock_k8s_client():
    """Mock Kubernetes client."""
    with patch("kubernetes.client.CoreV1Api") as core_mock:
        with patch("kubernetes.client.AppsV1Api") as apps_mock:
            core_mock.return_value = MagicMock()
            apps_mock.return_value = MagicMock()
            yield (core_mock, apps_mock)


@pytest.fixture
def mock_jwt():
    """Mock JWT functionality."""
    with patch("app.auth.oauth.jwt") as mock:
        # Create a mock for the Claims object
        mock_claims = MagicMock()
        mock_claims.validate.return_value = None

        # Make it dict-like to be returned properly
        test_claims = {
            "sub": "test-agent",
            "iss": "https://test-auth.example.com",
            "aud": "test-audience",
            "scope": "browser:create browser:status",
        }

        # Initialize the mock as a dict-like object
        mock_claims.update(test_claims)
        mock_claims.__getitem__.side_effect = test_claims.__getitem__
        mock_claims.__iter__.side_effect = test_claims.__iter__
        mock_claims.items.side_effect = test_claims.items
        mock_claims.keys.side_effect = test_claims.keys
        mock_claims.values.side_effect = test_claims.values

        # Set the mock decode method to return the mock Claims
        mock.decode.return_value = mock_claims

        # Define custom exception classes
        mock.InvalidClaimError = InvalidClaimError
        mock.ExpiredTokenError = ExpiredTokenError

        yield mock


# ==============================================================================
# INTEGRATION TEST FIXTURES
# ==============================================================================


# Async mock for verify_token
async def mock_verify_token_func():
    """Mock async function for token verification."""
    return {
        "sub": "test-agent",
        "scope": "browser:create browser:status",
    }


@pytest.fixture
def mock_verify_token():
    """Mock the token verification."""
    # Create AsyncMock that returns properly structured dict
    mock = AsyncMock()
    mock.return_value = {
        "sub": "test-agent",
        "scope": "browser:create browser:status",
    }

    with patch("app.auth.oauth.verify_token", mock):
        yield mock


@pytest.fixture
def mock_selenium_hub():
    """Mock the Selenium Hub."""
    hub_mock = MagicMock()

    # Create browsers method should return string IDs (not MagicMock objects)
    async def mock_create_browsers(*args, **kwargs):
        return ["browser-1", "browser-2"]

    hub_mock.create_browsers = mock_create_browsers
    hub_mock.ensure_hub_running = AsyncMock(return_value=True)

    # Mock other methods that might be called
    hub_mock.get_browser_status = AsyncMock(return_value={"status": "ready"})
    hub_mock.get_browser_health = AsyncMock(return_value={"cpu_usage": 10, "memory_usage": 200})
    hub_mock.delete_browser = AsyncMock(return_value=True)

    with patch("app.api.browsers.SeleniumHub", return_value=hub_mock):
        with patch("app.services.selenium_hub.SeleniumHub", return_value=hub_mock):
            yield hub_mock


# ==============================================================================
# E2E TEST FIXTURES
# ==============================================================================


@pytest.fixture
def e2e_client():
    """Create a test client for E2E tests with no dependency overrides."""

    # For E2E tests, we don't override dependencies - we test with real components
    return TestClient(app)


@pytest.fixture(scope="session")
def e2e_auth_headers():
    """Return static auth headers for E2E tests (no Hydra/OAuth required)."""
    from app.core.settings import settings

    return {"Authorization": f"Bearer {settings.API_TOKEN}"}


# ==============================================================================
# SHARED TEST FIXTURES
# ==============================================================================


@pytest.fixture(scope="session")
def client():
    """Create a test client for the FastAPI app with dependency override for verify_token."""
    from app.dependencies import verify_token
    from fastapi.testclient import TestClient

    async def always_valid_token(token: Optional[str] = None):
        return {"sub": "test-agent"}

    app.dependency_overrides[verify_token] = always_valid_token
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Create authentication headers for API requests."""
    from app.core.settings import settings

    return {"Authorization": f"Bearer {settings.API_TOKEN}"}


@pytest.fixture(scope="session")
def selenium_container():
    """Spin up a Selenium container for E2E tests."""
    from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

    with BrowserWebDriverContainer(DesiredCapabilities.CHROME) as container:
        container.with_exposed_ports(4444)
        yield container


@pytest.fixture
def cleanup_docker_browsers():
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
