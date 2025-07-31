"""End-to-end tests for Selenium Hub service."""

from urllib.parse import urljoin

import httpx
import pytest
from app.core.settings import Settings
from app.services.selenium_hub import SeleniumHub
from app.services.selenium_hub.models import DeploymentMode


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.parametrize("deployment_mode", [DeploymentMode.DOCKER, DeploymentMode.KUBERNETES])
async def test_check_hub_health(deployment_mode: DeploymentMode) -> None:
    """Test that check_hub_health returns True when the hub is healthy."""

    settings = Settings(DEPLOYMENT_MODE=deployment_mode)

    assert settings.DEPLOYMENT_MODE == deployment_mode

    hub = SeleniumHub(settings)

    # Ensure hub is running and verify it
    assert await hub.ensure_hub_running() is True, "Failed to ensure hub is running"

    # Wait for hub to be healthy
    assert await hub.wait_for_hub_healthy() is True, "Hub failed to become healthy within timeout"

    # Verify hub status endpoint is accessible
    auth = httpx.BasicAuth(
        settings.selenium_grid.USER.get_secret_value(),
        settings.selenium_grid.PASSWORD.get_secret_value(),
    )
    async with httpx.AsyncClient(auth=auth) as client:
        response = await client.get(urljoin(hub.URL, "status"))
        assert response.status_code == httpx.codes.OK, (
            f"Hub status endpoint returned {response.status_code}"
        )

    hub.cleanup()
