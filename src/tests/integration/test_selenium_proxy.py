"""Integration tests for Selenium Hub proxy."""

import pytest
from app.routers.selenium_proxy import SELENIUM_HUB_PREFIX
from fastapi import status
from httpx import BasicAuth
from starlette.testclient import TestClient


@pytest.mark.integration
@pytest.mark.parametrize(
    "endpoint", [f"{SELENIUM_HUB_PREFIX}/status", f"{SELENIUM_HUB_PREFIX}/wd/hub/status"]
)
def test_proxy_requires_auth(client: TestClient, endpoint: str) -> None:
    """
    Test that the proxy requires authentication and returns 401 if not provided.

    Args:
        client: The FastAPI TestClient instance.

    Expected:
        A request to {SELENIUM_HUB_PREFIX}/status without authentication should return a 401 Unauthorized status code.
    """
    response = client.get(endpoint)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.integration
@pytest.mark.parametrize(
    "endpoint", [f"{SELENIUM_HUB_PREFIX}/status", f"{SELENIUM_HUB_PREFIX}/wd/hub/status"]
)
def test_proxy_forwards_request(
    client: TestClient, selenium_hub_basic_auth_headers: BasicAuth, endpoint: str
) -> None:
    """
    Test that the proxy forwards requests with valid HTTP Basic Auth and returns 200.

    Args:
        client: The FastAPI TestClient instance.
        selenium_hub_basic_auth_headers: The HTTP Basic Auth headers for authentication.
        endpoint: The endpoint to test.

    Expected:
        A request to the specified endpoint with valid authentication should return a 200 OK status code.
    """
    response = client.get(endpoint, auth=selenium_hub_basic_auth_headers)
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.integration
def test_selenium_hub_ui_flow(
    client: TestClient, selenium_hub_basic_auth_headers: BasicAuth
) -> None:
    """
    Test the full UI flow: verify HTML response from {SELENIUM_HUB_PREFIX}/ui and its assets.

    Args:
        selenium_hub_basic_auth_headers: The HTTP Basic Auth headers for authentication.

    Expected:
        A request to {SELENIUM_HUB_PREFIX}/ui should return a 200 OK status code with a text/html content type.
        The HTML should contain references to static assets that can be loaded.
    """
    # Test UI response
    response = client.get(f"{SELENIUM_HUB_PREFIX}/ui", auth=selenium_hub_basic_auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert "text/html" in response.headers["content-type"]
    assert "Selenium Grid" in response.text

    # Test UI assets
    response = client.get(
        f"{SELENIUM_HUB_PREFIX}/ui/static/js/main.d25b7c1c.js", auth=selenium_hub_basic_auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
