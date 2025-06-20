"""Unit tests for SeleniumHub service."""

from typing import Any, AsyncGenerator, Callable, List

import httpx
import pytest
import pytest_asyncio
from _pytest.fixtures import SubRequest
from app.core.models import BrowserConfig, ContainerResources, DeploymentMode
from app.core.settings import Settings
from app.services.selenium_hub import SeleniumHub
from app.services.selenium_hub.docker_backend import DockerHubBackend
from app.services.selenium_hub.k8s_backend import KubernetesHubBackend
from pydantic import SecretStr
from pytest_mock import MockerFixture

from tests.conftest import reset_selenium_hub_singleton

# Define constants for mock browser IDs
MOCK_DOCKER_BROWSER_ID = "mock-docker-browser-id"
MOCK_K8S_BROWSER_ID = "mock-k8s-browser-id"


# Fixtures creator
def generate_selenium_fixture(
    backend_cls: Any, mock_browser_id: str, settings_arg_name: str
) -> Callable[..., AsyncGenerator[SeleniumHub, None]]:
    """
    Generate a fixture for SeleniumHub with a specific backend.

    Args:
        backend_cls: The backend class (DockerHubBackend or KubernetesHubBackend).
        mock_browser_id: The mock browser ID to return from the backend.
        settings_arg_name: The name of the settings fixture to use.

    Returns:
        A fixture that yields a SeleniumHub instance with the specified backend.
    """

    @pytest_asyncio.fixture(scope="function")
    async def _fixture(
        request: SubRequest, mocker: MockerFixture
    ) -> AsyncGenerator[SeleniumHub, None]:
        ensure_hub_running_mock = mocker.AsyncMock(return_value=True)

        async def generate_browsers_id(count: int, *args: Any, **kwargs: Any) -> List[str]:
            if count == 1:
                return [mock_browser_id]
            return [f"{mock_browser_id}-{i}" for i in range(count)]

        create_browsers_mock = mocker.AsyncMock(side_effect=generate_browsers_id)
        delete_browsers_mock = mocker.AsyncMock(return_value=[mock_browser_id])

        mocker.patch.object(backend_cls, "ensure_hub_running", ensure_hub_running_mock)
        mocker.patch.object(backend_cls, "create_browsers", create_browsers_mock)
        mocker.patch.object(backend_cls, "delete_browsers", delete_browsers_mock)

        if backend_cls is KubernetesHubBackend:
            mocker.patch.object(backend_cls, "_load_k8s_config", return_value=None)

        settings = request.getfixturevalue(settings_arg_name)

        reset_selenium_hub_singleton()
        hub = SeleniumHub(settings)
        yield hub
        reset_selenium_hub_singleton()

    return _fixture


# Fixtures
selenium_hub_docker_backend = generate_selenium_fixture(
    DockerHubBackend, MOCK_DOCKER_BROWSER_ID, "docker_hub_settings"
)
selenium_hub_k8s_backend = generate_selenium_fixture(
    KubernetesHubBackend, MOCK_K8S_BROWSER_ID, "k8s_hub_settings"
)


@pytest.fixture(scope="function")
def hub(request: SubRequest) -> AsyncGenerator[SeleniumHub, None]:
    """
    Fixture to use with pytest parametrize to select backend.

    Args:
        request: The pytest request object.

    Returns:
        A SeleniumHub instance with the selected backend.
    """
    fixture_name: str = request.param
    fixture: AsyncGenerator[SeleniumHub, None] = request.getfixturevalue(fixture_name)
    return fixture


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "hub", ["selenium_hub_docker_backend", "selenium_hub_k8s_backend"], indirect=True
)
async def test_ensure_hub_running(hub: SeleniumHub) -> None:
    """
    Test ensure_hub_running with both Docker and K8s backends.

    Args:
        hub: The SeleniumHub instance to test.

    Expected:
        The ensure_hub_running method should return True and be called once.
    """
    result = await hub.ensure_hub_running()
    assert result is True
    hub._manager.backend.ensure_hub_running.assert_called_once()  # type: ignore


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "httpx_side_effect,expected_result",
    [
        (None, True),  # Success: returns 200
        (httpx.RequestError("Connection failed"), False),  # Failure: raises httpx.RequestError
    ],
)
@pytest.mark.parametrize(
    "hub", ["selenium_hub_docker_backend", "selenium_hub_k8s_backend"], indirect=True
)
async def test_check_hub_health(
    hub: SeleniumHub,
    mocker: MockerFixture,
    httpx_side_effect: httpx.RequestError | None,
    expected_result: bool,
) -> None:
    """
    Parametrized test for check_hub_health for both healthy and unhealthy cases.
    """
    mock_client = mocker.AsyncMock()
    if httpx_side_effect is None:
        mock_response = mocker.AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_client.get.return_value = mock_response
    else:
        mock_client.get.side_effect = httpx_side_effect

    # Patch the httpx.AsyncClient context manager correctly
    mock_async_client = mocker.patch("httpx.AsyncClient", autospec=True)
    mock_async_client.return_value.__aenter__.return_value = mock_client

    result = await hub.check_hub_health()
    assert result is expected_result


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "hub,expected_browser_id",
    [
        ("selenium_hub_docker_backend", MOCK_DOCKER_BROWSER_ID),
        ("selenium_hub_k8s_backend", MOCK_K8S_BROWSER_ID),
    ],
    indirect=["hub"],
)
async def test_create_browsers(
    hub: SeleniumHub,
    expected_browser_id: str,
) -> None:
    """
    Test create_browsers with both Docker and K8s backends.

    Args:
        hub: The SeleniumHub instance to test.
        expected_browser_id: The expected browser ID to be returned.

    Expected:
        The create_browsers method should return a list containing the expected browser ID and be called once with the correct arguments.
    """
    result = await hub.create_browsers(browser_type="chrome", count=1)
    assert result[0] == expected_browser_id
    hub._manager.backend.create_browsers.assert_called_once_with(  # type: ignore
        1, "chrome", hub.settings.BROWSER_CONFIGS
    )


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "hub,browser_id",
    [
        ("selenium_hub_docker_backend", MOCK_DOCKER_BROWSER_ID),
        ("selenium_hub_k8s_backend", MOCK_K8S_BROWSER_ID),
    ],
    indirect=["hub"],
)
async def test_delete_browsers(hub: SeleniumHub, browser_id: str) -> None:
    """
    Test delete_browsers with both Docker and K8s backends.

    Args:
        hub: The SeleniumHub instance to test.
        browser_id: The browser ID to delete.

    Expected:
        The delete_browsers method should return a list containing the deleted browser ID and be called once with the correct arguments.
    """
    result = await hub.delete_browsers([browser_id])
    assert result == [browser_id]
    hub._manager.backend.delete_browsers.assert_called_once_with([browser_id])  # type: ignore


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "hub,expected_browser_id",
    [
        ("selenium_hub_docker_backend", MOCK_DOCKER_BROWSER_ID),
        ("selenium_hub_k8s_backend", MOCK_K8S_BROWSER_ID),
    ],
    indirect=["hub"],
)
async def test_create_browser(
    hub: SeleniumHub,
    expected_browser_id: str,
) -> None:
    """
    Test that create_browsers returns correct browser ID for each backend.

    Args:
        hub: The SeleniumHub instance to test.
        expected_browser_id: The expected browser ID to be returned.

    Expected:
        The create_browsers method should return a list containing the expected browser ID.
    """
    browser_ids = await hub.create_browsers(browser_type="chrome", count=1)
    assert isinstance(browser_ids, list)
    assert len(browser_ids) == 1
    assert isinstance(browser_ids[0], str)
    assert browser_ids[0] == expected_browser_id


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "browser_type,count,expected_error,error_message",
    [
        ("invalid", 1, KeyError, "Unsupported browser type: invalid"),
        ("chrome", 0, ValueError, "Browser count must be positive"),
        ("chrome", -1, ValueError, "Browser count must be positive"),
    ],
)
async def test_create_browsers_validates_input(
    selenium_hub_docker_backend: SeleniumHub,
    browser_type: str,
    count: int,
    expected_error: type[Exception],
    error_message: str,
) -> None:
    """
    Test that create_browsers validates browser type and count.

    Args:
        selenium_hub_docker_backend: The SeleniumHub instance to test.
        browser_type: The browser type to test.
        count: The browser count to test.
        expected_error: The expected exception type.
        error_message: The expected error message.

    Expected:
        The create_browsers method should raise the expected exception with the correct error message.
    """
    with pytest.raises(expected_error) as excinfo:
        await selenium_hub_docker_backend.create_browsers(browser_type=browser_type, count=count)
    assert error_message in str(excinfo.value)


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "max_instances,requested_count,should_raise",
    [
        (1, 2, True),
        (2, 2, False),
        (3, 2, False),
        (1, 1, False),
    ],
)
async def test_create_browsers_handles_max_instances(
    selenium_hub_docker_backend: SeleniumHub,
    max_instances: int,
    requested_count: int,
    should_raise: bool,
) -> None:
    """
    Test that create_browsers respects max instances limit.

    Args:
        selenium_hub_docker_backend: The SeleniumHub instance to test.
        max_instances: The maximum number of browser instances allowed.
        requested_count: The number of browser instances to request.
        should_raise: Whether the test should raise an exception.

    Expected:
        If should_raise is True, the create_browsers method should raise a ValueError. Otherwise, it should return a list of browser IDs.
    """
    selenium_hub_docker_backend.settings.MAX_BROWSER_INSTANCES = max_instances
    if should_raise:
        with pytest.raises(ValueError, match="Maximum browser instances exceeded"):
            await selenium_hub_docker_backend.create_browsers(
                browser_type="chrome", count=requested_count
            )
    else:
        result = await selenium_hub_docker_backend.create_browsers(
            browser_type="chrome", count=requested_count
        )
        assert len(result) == requested_count


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_browsers_with_insufficient_resources(
    selenium_hub_docker_backend: SeleniumHub,
    mocker: MockerFixture,
) -> None:
    """
    Test create_browsers with insufficient resources.

    Args:
        selenium_hub_docker_backend: The SeleniumHub instance to test.
        mocker: The pytest mocker fixture.

    Expected:
        The create_browsers method should raise a ValueError with the message 'Insufficient resources'.
    """
    mocker.patch.object(
        selenium_hub_docker_backend._manager.backend,
        "create_browsers",
        side_effect=ValueError("Insufficient resources"),
    )
    with pytest.raises(ValueError, match="Insufficient resources"):
        await selenium_hub_docker_backend.create_browsers(browser_type="chrome", count=1)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_k8s_hub_creates_namespace(selenium_hub_k8s_backend: SeleniumHub) -> None:
    """
    Test that ensure_hub_running creates namespace if it doesn't exist.

    Args:
        selenium_hub_k8s_backend: The SeleniumHub instance to test.

    Expected:
        The ensure_hub_running method should return True and be called once.
    """
    ensure_hub_running_mock: Any = selenium_hub_k8s_backend._manager.backend.ensure_hub_running
    ensure_hub_running_mock.reset_mock()
    result = await selenium_hub_k8s_backend.ensure_hub_running()
    assert result is True
    ensure_hub_running_mock.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_singleton_behavior() -> None:
    """
    Test that SeleniumHub maintains singleton behavior.

    Expected:
        Creating multiple SeleniumHub instances should return the same object, and settings should be preserved from the first initialization.
    """
    reset_selenium_hub_singleton()

    # Create initial settings
    settings = Settings(
        PROJECT_NAME="Test Project",
        VERSION="0.1.0",
        API_V1_STR="/api/v1",
        API_TOKEN=SecretStr("test-token"),
        SELENIUM_HUB_USER=SecretStr("test-user"),
        SELENIUM_HUB_PASSWORD=SecretStr("test-password"),
        MAX_BROWSER_INSTANCES=2,
        SE_NODE_MAX_SESSIONS=1,
        DEPLOYMENT_MODE=DeploymentMode.DOCKER,
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
