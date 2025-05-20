"""Test suite for MCP browser endpoints."""

import logging

import docker
import pytest

HTTP_201_CREATED = 201
HTTP_200_OK = 200
HTTP_422_UNPROCESSABLE_ENTITY = 422
EXPECTED_BROWSER_COUNT = 2


@pytest.fixture(autouse=True)
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


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_browsers_endpoint(client, auth_headers):
    """Test browser creation endpoint."""
    response = client.post(
        "/api/v1/browsers",
        json={"count": 2, "browser_type": "chrome"},
        headers=auth_headers,
    )

    assert response.status_code == HTTP_201_CREATED
    data = response.json()
    assert len(data["browser_ids"]) == EXPECTED_BROWSER_COUNT
    assert data["status"] == "created"
    assert "hub_url" in data


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_browsers_validates_count(client, auth_headers):
    """Test browser count validation."""
    response = client.post(
        "/api/v1/browsers",
        json={"count": 0, "browser_type": "chrome"},
        headers=auth_headers,
    )

    assert response.status_code == HTTP_422_UNPROCESSABLE_ENTITY  # Validation error


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_browsers_validates_type(client, auth_headers):
    """Test browser type validation."""
    response = client.post(
        "/api/v1/browsers",
        json={"count": 1, "browser_type": "invalid"},
        headers=auth_headers,
    )

    assert response.status_code == HTTP_422_UNPROCESSABLE_ENTITY  # Validation error


@pytest.mark.asyncio
@pytest.mark.integration
async def test_hub_status_endpoint(client, auth_headers):
    """Test hub status endpoint."""
    response = client.get("/api/v1/browsers/status", headers=auth_headers)

    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["hub_running"] is True
    assert "deployment_mode" in data
