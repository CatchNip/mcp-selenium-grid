from typing import Annotated, Any, Dict

import pytest
from app.core.settings import Settings
from app.dependencies import get_settings, security, verify_token
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from pydantic import SecretStr

# Create a temporary FastAPI app for testing the dependency
app = FastAPI()


@app.get("/test-auth")
async def read_item(
    settings: Annotated[Settings, Depends(get_settings)],
    user: Dict[str, str] = Depends(verify_token),
) -> Dict[str, Any]:
    """A protected endpoint to test token verification."""
    return {"message": "Access granted", "user": user}


def get_settings_override_valid() -> Settings:
    return Settings(API_TOKEN=SecretStr("valid_token"))


def get_settings_override_invalid() -> Settings:
    return Settings(API_TOKEN=SecretStr("valid_token"))


def get_settings_override_missing() -> Settings:
    return Settings(API_TOKEN=SecretStr("any_token"))


async def verify_token_override(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, str]:
    if credentials.credentials != "valid_token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token",
        )
    return {"sub": "api-user"}


@pytest.mark.unit
def test_verify_token_valid_token() -> None:
    """Test the endpoint with a valid token."""
    app.dependency_overrides[verify_token] = verify_token_override
    client = TestClient(app)
    headers = {"Authorization": "Bearer valid_token"}
    response = client.get("/test-auth", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"message": "Access granted", "user": {"sub": "api-user"}}
    app.dependency_overrides = {}


@pytest.mark.unit
def test_verify_token_invalid_token() -> None:
    """Test the endpoint with an invalid token."""
    app.dependency_overrides[verify_token] = verify_token_override
    client = TestClient(app)
    headers = {"Authorization": "Bearer invalid_token"}
    response = client.get("/test-auth", headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"detail": "Invalid or missing token"}
    app.dependency_overrides = {}


@pytest.mark.unit
def test_verify_token_missing_token() -> None:
    """Test the endpoint with no token provided."""
    app.dependency_overrides[verify_token] = verify_token_override
    client = TestClient(app)
    response = client.get("/test-auth")
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {"detail": "Not authenticated"}
    app.dependency_overrides = {}
