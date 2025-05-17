"""End-to-end tests simulating an AI Agent using the MCP Server."""

import pytest
from .test_browser_workflow import create_browser, HTTP_201_CREATED, HTTP_200_OK


@pytest.mark.e2e
def test_browser_lifecycle(client, auth_headers, selenium_container):
    # Create browser
    response = create_browser(client, auth_headers)
    assert response.status_code == HTTP_201_CREATED
    browser_id = response.json()["browser_ids"][0]

    # Check status
    status_response = client.get(f"/api/v1/browsers/{browser_id}/status", headers=auth_headers)
    assert status_response.status_code == HTTP_200_OK

    # Check health
    health_response = client.get(f"/api/v1/browsers/{browser_id}/health", headers=auth_headers)
    assert health_response.status_code == HTTP_200_OK

    # Delete browser
    delete_response = client.delete(f"/api/v1/browsers/{browser_id}", headers=auth_headers)
    assert delete_response.status_code == HTTP_200_OK


@pytest.mark.parametrize("browser_type", ["invalid", "firefox"])
def test_error_handling(client, auth_headers, browser_type, selenium_container):
    response = create_browser(client, auth_headers, browser_type=browser_type)
    assert response.status_code in (400, 422)
