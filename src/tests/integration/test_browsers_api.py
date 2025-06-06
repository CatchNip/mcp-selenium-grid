"""Test suite for MCP browser endpoints."""

from typing import Dict

import pytest
from app.services.selenium_hub import SeleniumHub
from fastapi import status
from fastapi.testclient import TestClient


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.usefixtures("cleanup_docker_browsers")
async def test_create_browsers_endpoint(
    client: TestClient, auth_headers: Dict[str, str], selenium_hub: SeleniumHub
) -> None:
    """Test browser creation endpoint."""
    BROWSER_COUNT = 2

    response = client.post(
        "/api/v1/browsers/create",
        json={"count": BROWSER_COUNT, "browser_type": "chrome"},
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert len(data["browsers"]) == BROWSER_COUNT
    assert data["status"] == "created"
    assert "hub_url" in data

    # Check that browser instances are present and have required fields
    for browser in data["browsers"]:
        assert "id" in browser
        assert browser["type"] == "chrome"
        assert "resources" in browser


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.usefixtures("cleanup_docker_browsers")
async def test_create_browsers_validates_count(
    client: TestClient, auth_headers: Dict[str, str], selenium_hub: SeleniumHub
) -> None:
    """Test browser count validation."""
    response = client.post(
        "/api/v1/browsers/create",
        json={"count": 0, "browser_type": "chrome"},
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY  # Validation error


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.usefixtures("cleanup_docker_browsers")
async def test_create_browsers_validates_type(
    client: TestClient, auth_headers: Dict[str, str], selenium_hub: SeleniumHub
) -> None:
    """Test browser type validation."""
    response = client.post(
        "/api/v1/browsers/create",
        json={"count": 1, "browser_type": "invalid"},
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY  # Validation error


@pytest.mark.asyncio
@pytest.mark.integration
async def test_hub_status_endpoint(
    client: TestClient, auth_headers: Dict[str, str], selenium_hub: SeleniumHub
) -> None:
    """Test hub status endpoint."""

    BROWSERS_COUNT = 2

    # Create browsers to populate state
    client.post(
        "/api/v1/browsers/create",
        json={"count": BROWSERS_COUNT, "browser_type": "chrome"},
        headers=auth_headers,
    )
    response = client.get("/api/v1/browsers/status", headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["hub_running"] is True
    assert "deployment_mode" in data
    assert "browsers" in data
    assert isinstance(data["browsers"], list)
    assert len(data["browsers"]) >= BROWSERS_COUNT
    for browser in data["browsers"]:
        assert "id" in browser
        assert browser["type"] == "chrome"
        assert "resources" in browser
