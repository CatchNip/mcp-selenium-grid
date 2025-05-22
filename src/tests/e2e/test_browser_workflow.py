"""End-to-end tests for browser workflows using real infrastructure."""

import time

import pytest

# from testcontainers.selenium import SeleniumContainer

HTTP_201_CREATED = 201
HTTP_200_OK = 200


def create_browser(client, auth_headers, count=1, browser_type="chrome"):
    response = client.post(
        "/api/v1/browsers",
        json={"browser_type": browser_type, "count": count},
        headers=auth_headers,
    )
    return response


@pytest.mark.e2e
def test_complete_browser_lifecycle(client, auth_headers):
    # 1. Create a browser instance
    create_response = create_browser(client, auth_headers)
    assert create_response.status_code == HTTP_201_CREATED
    browser_id = create_response.json()["browser_ids"][0]

    try:
        # 2. Wait for browser to be ready and check status
        ready = False
        for _ in range(5):
            status_response = client.get(
                f"/api/v1/browsers/{browser_id}/status", headers=auth_headers
            )
            if status_response.status_code == HTTP_200_OK:
                status_data = status_response.json()
                if status_data.get("status") == "ready":
                    ready = True
                    break
            time.sleep(2)
        assert ready, "Browser did not become ready within timeout"

        # 3. Check health metrics
        health_response = client.get(f"/api/v1/browsers/{browser_id}/health", headers=auth_headers)
        assert health_response.status_code == HTTP_200_OK
        health_data = health_response.json()
        assert "cpu_usage" in health_data
        assert "memory_usage" in health_data
    finally:
        # 4. Clean up - delete the browser
        delete_response = client.delete(f"/api/v1/browsers/{browser_id}", headers=auth_headers)
        assert delete_response.status_code == HTTP_200_OK
        assert delete_response.json()["success"] is True


def test_hub_operation(client, auth_headers):
    response = client.get("/api/v1/browsers/status", headers=auth_headers)
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["hub_running"] is True


@pytest.mark.e2e
@pytest.mark.parametrize("browser_type", ["invalid", "firefox"])
def test_error_handling(client, auth_headers, browser_type):
    """Test API error handling for browser creation."""
    response = create_browser(client, auth_headers, browser_type=browser_type)
    assert response.status_code in (400, 422)
