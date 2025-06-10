"""Integration tests for health check endpoint."""

from typing import Dict

import pytest
from app.core.models import DeploymentMode
from app.models import HealthStatus
from fastapi import status
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_health_check_endpoint(client: TestClient, auth_headers: Dict[str, str]) -> None:
    """Test health check endpoint returns correct status and deployment mode."""
    response = client.get("/health", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "status" in data
    assert "deployment_mode" in data

    # Verify status is one of the valid enum values
    assert data["status"] in [status.value for status in HealthStatus]

    # Verify deployment mode is one of the valid enum values
    assert data["deployment_mode"] in [mode.value for mode in DeploymentMode]


@pytest.mark.integration
def test_health_check_requires_auth(client: TestClient) -> None:
    """Test health check endpoint requires authentication."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.integration
def test_hub_stats_endpoint(client: TestClient, auth_headers: Dict[str, str]) -> None:
    """Test the hub stats endpoint."""
    response = client.get("/stats", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "hub_running" in data
    assert "hub_healthy" in data
    assert "deployment_mode" in data
    assert data["deployment_mode"] in [mode.value for mode in DeploymentMode]
    assert "max_instances" in data
    assert "browsers" in data
    assert isinstance(data["browsers"], list)
