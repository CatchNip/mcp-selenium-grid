"""Test suite for MCP browser endpoints."""

from typing import Any, Dict

import pytest
from app.routers.browsers.models import BrowserResponseStatus
from fastapi import status
from fastapi.testclient import TestClient


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_browsers_requires_auth(client: TestClient) -> None:
    """Test create browsers endpoint requires authentication."""
    response = client.post(
        "/api/v1/browsers/create",
        json={"count": 1, "browser_type": "chrome"},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


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
    assert data["status"] == BrowserResponseStatus.CREATED
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


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_browsers_requires_auth(client: TestClient) -> None:
    """Test delete browsers endpoint requires authentication."""
    response = client.post(
        "/api/v1/browsers/delete",
        json={"browsers_ids": ["browser-id"]},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_browsers_endpoint(client: TestClient, auth_headers: Dict[str, str]) -> None:
    """Test browser deletion endpoint for successfully deleting browsers."""
    # 1. Create a browser to get an ID
    create_response = client.post(
        "/api/v1/browsers/create",
        json={"count": 1, "browser_type": "chrome"},
        headers=auth_headers,
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    created_data = create_response.json()
    assert len(created_data["browsers"]) > 0
    browser_id_to_delete = created_data["browsers"][0]["id"]

    # 2. Delete the browser
    delete_response = client.post(
        "/api/v1/browsers/delete",
        json={"browsers_ids": [browser_id_to_delete]},
        headers=auth_headers,
    )

    assert delete_response.status_code == status.HTTP_200_OK
    delete_data = delete_response.json()
    assert delete_data["browsers_ids"] == [browser_id_to_delete]
    assert delete_data["status"] == BrowserResponseStatus.DELETED
    assert delete_data["message"] == "1 browser(s) deleted successfully."


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_browsers_non_existent_id(
    client: TestClient, auth_headers: Dict[str, str]
) -> None:
    """Test deleting a browser with a non-existent ID."""
    non_existent_id = "non-existent-browser-id-12345"
    delete_response = client.post(
        "/api/v1/browsers/delete",
        json={"browsers_ids": [non_existent_id]},
        headers=auth_headers,
    )

    assert delete_response.status_code == status.HTTP_404_NOT_FOUND
    error_data = delete_response.json()
    assert "detail" in error_data
    assert error_data["detail"] == f"No browsers found to delete in the list: {[non_existent_id]}"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_browsers_empty_list_of_ids(
    client: TestClient, auth_headers: Dict[str, str]
) -> None:
    """Test deleting browsers with an empty list of IDs."""
    delete_response = client.post(
        "/api/v1/browsers/delete", json={"browsers_ids": []}, headers=auth_headers
    )

    assert delete_response.status_code == status.HTTP_200_OK
    delete_data = delete_response.json()
    assert delete_data["browsers_ids"] == []
    assert delete_data["status"] == BrowserResponseStatus.UNCHANGED
    assert delete_data["message"] == "No Browsers to delete."


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_browsers_mixed_existent_and_non_existent_ids(
    client: TestClient, auth_headers: Dict[str, str]
) -> None:
    """Test deleting browsers with a mix of existent and non-existent IDs."""
    # 1. Create a browser to get an ID
    create_response = client.post(
        "/api/v1/browsers/create",
        json={"count": 1, "browser_type": "chrome"},
        headers=auth_headers,
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    created_data = create_response.json()
    existent_id = created_data["browsers"][0]["id"]
    non_existent_id = "non-existent-browser-id-99999"
    ids_to_delete = [existent_id, non_existent_id]

    # 2. Delete the browsers
    delete_response = client.post(
        "/api/v1/browsers/delete",
        json={"browsers_ids": ids_to_delete},
        headers=auth_headers,
    )

    assert delete_response.status_code == status.HTTP_200_OK
    delete_data = delete_response.json()
    assert delete_data["browsers_ids"] == [existent_id]
    assert delete_data["status"] == BrowserResponseStatus.DELETED
    assert delete_data["message"] == "1 browser(s) deleted successfully. 1 browser(s) not found."


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize(
    "invalid_payload",
    [
        ({"browsers_ids": "not-a-list"}),  # Invalid type
        ({"browsers_ids": [123, "valid-id"]}),  # List with non-string element
        ({}),  # Missing 'browsers_ids' field
    ],
)
async def test_delete_browsers_invalid_input_payload(
    client: TestClient, auth_headers: Dict[str, str], invalid_payload: Dict[Any, Any]
) -> None:
    """Test delete browsers endpoint with various invalid input payloads."""
    response = client.post("/api/v1/browsers/delete", json=invalid_payload, headers=auth_headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
