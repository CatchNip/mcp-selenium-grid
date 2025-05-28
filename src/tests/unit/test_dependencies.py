from typing import Any, Dict
from unittest.mock import patch

import pytest
from app.core.settings import settings
from app.dependencies import verify_token
from fastapi import Depends, FastAPI, status
from fastapi.testclient import TestClient

# Create a temporary FastAPI app for testing the dependency
app = FastAPI()


@app.get("/test-auth")
async def read_item(user: Dict[str, str] = Depends(verify_token)) -> Dict[str, Any]:
    """A protected endpoint to test token verification."""
    return {"message": "Access granted", "user": user}


client: TestClient = TestClient(app)


@pytest.mark.unit
def test_verify_token_valid_token() -> None:
    """Test the endpoint with a valid token."""
    # Mock the settings.API_TOKEN
    with patch.object(settings, "API_TOKEN", "valid_token"):
        headers = {"Authorization": "Bearer valid_token"}
        response = client.get("/test-auth", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"message": "Access granted", "user": {"sub": "api-user"}}


@pytest.mark.unit
def test_verify_token_invalid_token() -> None:
    """Test the endpoint with an invalid token."""
    # Mock the settings.API_TOKEN
    with patch.object(settings, "API_TOKEN", "valid_token"):
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/test-auth", headers=headers)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {"detail": "Invalid or missing token"}


@pytest.mark.unit
def test_verify_token_missing_token() -> None:
    """Test the endpoint with no token provided."""
    # Mock the settings.API_TOKEN
    with patch.object(settings, "API_TOKEN", "valid_token"):
        # No Authorization header is provided
        response = client.get("/test-auth")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {"detail": "Not authenticated"}
