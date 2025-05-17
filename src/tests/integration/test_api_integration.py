"""Integration tests for API endpoints with their dependencies."""

import pytest

HTTP_201_CREATED = 201
HTTP_200_OK = 200
HTTP_422_UNPROCESSABLE_ENTITY = 422


@pytest.mark.integration
def test_create_browsers_endpoint(client, auth_headers):
    response = client.post(
        "/api/v1/browsers",
        json={"browser_type": "chrome", "count": 1},
        headers=auth_headers,
    )
    if response.status_code == HTTP_422_UNPROCESSABLE_ENTITY:
        print("Validation error:", response.json())
    assert response.status_code == HTTP_201_CREATED
    data = response.json()
    assert "browser_ids" in data
    assert "status" in data
    assert data["status"] == "created"


@pytest.mark.integration
def test_hub_status_endpoint(client, auth_headers):
    response = client.get("/api/v1/browsers/status", headers=auth_headers)
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert "hub_running" in data
    assert "deployment_mode" in data
