"""End-to-end tests for Selenium Hub service."""

from urllib.parse import urljoin

import httpx
import pytest
from app.core.settings import Settings
from app.services.selenium_hub.selenium_hub import SeleniumHub


@pytest.mark.e2e
async def test_check_hub_health() -> None:
    """Test that check_hub_health returns True when the hub is healthy."""
    settings = Settings()
    hub = SeleniumHub(settings)

    # Ensure hub is running and verify it
    assert await hub.ensure_hub_running() is True, "Failed to ensure hub is running"

    # Wait for hub to be healthy
    assert await hub.wait_for_hub_healthy() is True, "Hub failed to become healthy within timeout"

    # Verify hub status endpoint is accessible
    auth = httpx.BasicAuth(settings.SELENIUM_HUB_USER, settings.SELENIUM_HUB_PASSWORD)
    async with httpx.AsyncClient(auth=auth) as client:
        response = await client.get(urljoin(settings.SELENIUM_HUB_BASE_URL_DYNAMIC, "status"))
        assert response.status_code == httpx.codes.OK, (
            f"Hub status endpoint returned {response.status_code}"
        )
