"""End-to-end tests for browser workflows using real infrastructure."""

from typing import Dict

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from httpx import Response


def create_browser(
    client: TestClient, auth_headers: Dict[str, str], count: int = 1, browser_type: str = "chrome"
) -> Response:
    response = client.post(
        "/api/v1/browsers/create",
        json={"browser_type": browser_type, "count": count},
        headers=auth_headers,
    )
    return response


@pytest.mark.e2e
def test_complete_browser_lifecycle(client: TestClient, auth_headers: Dict[str, str]) -> None:
    # 1. Create a browser instance
    create_response = create_browser(client, auth_headers)
    assert create_response.status_code == status.HTTP_201_CREATED
    response_data = create_response.json()
    assert "browsers" in response_data
    assert "hub_url" in response_data
    browser_id = response_data["browsers"][0]["id"]

    try:
        # 2. Check hub stats to verify browser is registered
        stats_response = client.get("/stats", headers=auth_headers)
        assert stats_response.status_code == status.HTTP_200_OK
        stats_data = stats_response.json()
        assert stats_data["hub_running"] is True
        assert stats_data["hub_healthy"] is True
        assert any(browser["id"] == browser_id for browser in stats_data["browsers"])

    finally:
        # 3. Clean up - delete the browser
        delete_response = client.delete(f"/api/v1/browsers/{browser_id}", headers=auth_headers)
        assert delete_response.status_code == status.HTTP_200_OK
        delete_data = delete_response.json()
        assert delete_data["success"] is True
        assert "message" in delete_data


@pytest.mark.e2e
@pytest.mark.parametrize(
    "browser_type,expected_status",
    [
        ("invalid_browser", status.HTTP_422_UNPROCESSABLE_ENTITY),  # Invalid browser type
        ("", status.HTTP_422_UNPROCESSABLE_ENTITY),  # Empty browser type
        ("opera", status.HTTP_422_UNPROCESSABLE_ENTITY),  # Unsupported browser
    ],
)
def test_error_handling(
    client: TestClient, auth_headers: Dict[str, str], browser_type: str, expected_status: int
) -> None:
    """Test API error handling for browser creation."""
    response = create_browser(client, auth_headers, browser_type=browser_type)
    assert response.status_code == expected_status, (
        f"Expected {expected_status} but got {response.status_code}"
    )
