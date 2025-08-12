"""End-to-end tests for browser workflows using real infrastructure."""

import pytest
from app.routers.browsers.models import BrowserResponseStatus
from fastapi import status
from fastapi.testclient import TestClient
from httpx import Response
from pytest import FixtureRequest


def create_browsers(
    client: TestClient, auth_headers: dict[str, str], count: int = 1, browser_type: str = "chrome"
) -> Response:
    response = client.post(
        "/api/v1/browsers/create",
        json={"browser_type": browser_type, "count": count},
        headers=auth_headers,
    )
    return response


def delete_browsers(
    client: TestClient, auth_headers: dict[str, str], browsers_ids: list[str]
) -> Response:
    response = client.post(
        "/api/v1/browsers/delete",
        json={"browsers_ids": browsers_ids},
        headers=auth_headers,
    )
    return response


@pytest.mark.e2e
def test_complete_browser_lifecycle(
    client: TestClient, auth_headers: dict[str, str], request: FixtureRequest
) -> None:
    """Test complete browser lifecycle."""
    # 1. Create a browser instance
    create_response = create_browsers(client, auth_headers, count=2)
    assert create_response.status_code == status.HTTP_201_CREATED
    response_data = create_response.json()
    assert "browsers" in response_data
    assert isinstance(response_data["browsers"], list)
    assert "hub_url" in response_data
    assert response_data["status"] == BrowserResponseStatus.CREATED

    created_browsers_ids_list = [b["id"] for b in response_data["browsers"]]

    try:
        # 2. Check hub stats to verify browser is registered
        stats_response = client.get("/stats", headers=auth_headers)
        assert stats_response.status_code == status.HTTP_200_OK
        stats_data = stats_response.json()
        assert stats_data["hub_running"] is True
        assert stats_data["hub_healthy"] is True
        assert "deployment_mode" in stats_data
        # Get the value of the 'client' fixture's current parameter (DeploymentMode)
        current_mode = request.node.callspec.params["client"]
        assert stats_data["deployment_mode"] == current_mode.value
        assert isinstance(stats_data["browsers"], dict)
        stats_browsers_ids = [key for key in stats_data["browsers"].keys()]
        # Check if all created browsers are in stats (stats might contain more from previous runs)
        for browser_id in created_browsers_ids_list:
            assert browser_id in stats_browsers_ids

    finally:
        # 3. Clean up - delete the browser
        delete_response = delete_browsers(client, auth_headers, created_browsers_ids_list)
        assert delete_response.status_code == status.HTTP_200_OK
        delete_data = delete_response.json()
        assert delete_data["status"] == BrowserResponseStatus.DELETED
        assert sorted(created_browsers_ids_list) == sorted(delete_data["browsers_ids"])
        assert (
            delete_data["message"]
            == f"{len(created_browsers_ids_list)} browser(s) deleted successfully."
        )


@pytest.mark.e2e
@pytest.mark.parametrize(
    "browser_type,expected_status",
    [
        (1, status.HTTP_422_UNPROCESSABLE_ENTITY),  # Invalid browser type
        ("", status.HTTP_422_UNPROCESSABLE_ENTITY),  # Empty browser type
        ("opera", status.HTTP_422_UNPROCESSABLE_ENTITY),  # Unsupported browser
    ],
)
def test_error_handling(
    client: TestClient, auth_headers: dict[str, str], browser_type: str, expected_status: int
) -> None:
    """Test API error handling for browser creation."""
    response = create_browsers(client, auth_headers, browser_type=browser_type)
    assert response.status_code == expected_status, (
        f"Expected {expected_status} but got {response.status_code}"
    )
