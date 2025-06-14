"""End-to-end tests for Selenium Hub service."""

from urllib.parse import urljoin

import httpx
import pytest
from app.core.models import DeploymentMode
from app.core.settings import Settings
from app.services.selenium_hub.selenium_hub import SeleniumHub


@pytest.mark.e2e
@pytest.fixture(scope="session", params=[DeploymentMode.DOCKER, DeploymentMode.KUBERNETES])
async def test_check_hub_health(request: pytest.FixtureRequest) -> None:
    """Test that check_hub_health returns True when the hub is healthy."""

    settings = Settings(DEPLOYMENT_MODE=request.param)
    hub = SeleniumHub(settings)

    # Ensure hub is running and verify it
    assert await hub.ensure_hub_running() is True, "Failed to ensure hub is running"

    # Wait for hub to be healthy
    assert await hub.wait_for_hub_healthy() is True, "Hub failed to become healthy within timeout"

    # Verify hub status endpoint is accessible
    auth = httpx.BasicAuth(
        settings.SELENIUM_HUB_USER.get_secret_value(),
        settings.SELENIUM_HUB_PASSWORD.get_secret_value(),
    )
    async with httpx.AsyncClient(auth=auth) as client:
        response = await client.get(urljoin(hub.URL, "status"))
        assert response.status_code == httpx.codes.OK, (
            f"Hub status endpoint returned {response.status_code}"
        )
