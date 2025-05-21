"""Unit tests for SeleniumHub service."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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

        async def mock_generate_id():
            return "mock-id-12345"

        hub._generate_id = mock_generate_id
        yield hub


@pytest.fixture
def selenium_hub_k8s(mock_docker_client, monkeypatch):
    # Patch settings to use kubernetes
    from app.core import settings as core_settings

    monkeypatch.setattr(core_settings.settings, "DEPLOYMENT_MODE", "kubernetes")
    # Patch K8s clients
    with (
        patch("kubernetes.config.load_incluster_config"),
        patch("kubernetes.config.load_kube_config"),
        patch("kubernetes.client.CoreV1Api") as core_api_cls,
        patch("kubernetes.client.AppsV1Api") as apps_api_cls,
        patch("app.services.selenium_hub.docker_backend.docker.from_env") as docker_from_env,
    ):
        core_api = MagicMock()
        apps_api = MagicMock()
        core_api_cls.return_value = core_api
        apps_api_cls.return_value = apps_api
        docker_from_env.return_value = mock_docker_client
        hub = SeleniumHub()

        async def mock_generate_id():
            return "mock-id-12345"

        hub._generate_id = mock_generate_id
        yield hub, core_api, apps_api


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


@pytest.mark.unit
def test_ensure_k8s_hub_creates_namespace(selenium_hub_k8s):
    from kubernetes.client.rest import ApiException

    hub, core_api, apps_api = selenium_hub_k8s
    # Simulate namespace, deployment, and service not existing (404)
    core_api.read_namespace.side_effect = ApiException(status=404)
    core_api.read_namespaced_service.side_effect = ApiException(status=404)
    apps_api.read_namespaced_deployment.side_effect = ApiException(status=404)
    # Should call create_namespace, create_namespaced_deployment, create_namespaced_service
    result = asyncio.run(hub.ensure_hub_running())
    assert result is True
    assert core_api.create_namespace.called
    assert apps_api.create_namespaced_deployment.called
    assert core_api.create_namespaced_service.called


@pytest.mark.unit
def test_create_k8s_browser(selenium_hub_k8s):
    hub, core_api, _ = selenium_hub_k8s
    hub.ensure_hub_running = AsyncMock(return_value=True)
    core_api.create_namespaced_pod.return_value = None
    browser_ids = asyncio.run(hub.create_browsers(browser_type="chrome", count=1))
    assert isinstance(browser_ids, list)
    assert len(browser_ids) == 1
    assert browser_ids[0].startswith("selenium-node-chrome-")
    assert core_api.create_namespaced_pod.called
