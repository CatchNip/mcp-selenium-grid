"""Test suite for MCP browser endpoints."""

from typing import Dict

import pytest
from fastapi import status
from fastapi.testclient import TestClient


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_browsers_endpoint(client: TestClient, auth_headers: Dict[str, str]) -> None:
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
async def test_create_browsers_validates_count(
    client: TestClient, auth_headers: Dict[str, str]
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
async def test_create_browsers_validates_type(
    client: TestClient, auth_headers: Dict[str, str]
) -> None:
    """Test browser type validation."""
    response = client.post(
        "/api/v1/browsers/create",
        json={"count": 1, "browser_type": "invalid"},
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY  # Validation error
