from collections.abc import Generator
from typing import Any
from unittest.mock import Mock

import pytest
from app.core.settings import Settings
from app.dependencies import get_settings, verify_token
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from pydantic import SecretStr

app = FastAPI()


@app.get("/test-auth")
async def read_item(user: dict[str, str] = Depends(verify_token)) -> dict[str, Any]:
    return {"user": user}


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def mock_credentials(token: str) -> Mock:
    mock = Mock()
    mock.credentials = token
    return mock


def mock_settings(auth_enabled: bool = True, api_token: str = "valid_token") -> Mock:  # noqa: S107
    mock = Mock()
    mock.AUTH_ENABLED = auth_enabled
    mock_token = Mock()
    mock_token.get_secret_value.return_value = api_token
    mock.API_TOKEN = mock_token
    return mock


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_token_auth_disabled() -> None:
    result = await verify_token(mock_credentials("any"), mock_settings(False))
    assert result == {"sub": "anonymous"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_token_valid() -> None:
    result = await verify_token(mock_credentials("valid_token"), mock_settings())
    assert result == {"sub": "api-user"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_token_invalid() -> None:
    with pytest.raises(HTTPException) as exc:
        await verify_token(mock_credentials("wrong"), mock_settings())
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.unit
def test_endpoint_valid_token(client: TestClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        API_TOKEN=SecretStr("test_token"), AUTH_ENABLED=True
    )
    response = client.get("/test-auth", headers={"Authorization": "Bearer test_token"})
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"user": {"sub": "api-user"}}


@pytest.mark.unit
def test_endpoint_invalid_token(client: TestClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        API_TOKEN=SecretStr("test_token"), AUTH_ENABLED=True
    )
    response = client.get("/test-auth", headers={"Authorization": "Bearer wrong"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"detail": "Invalid or missing token"}


@pytest.mark.unit
def test_endpoint_auth_disabled(client: TestClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        API_TOKEN=SecretStr("any"), AUTH_ENABLED=False
    )
    response = client.get("/test-auth", headers={"Authorization": "Bearer any"})
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"user": {"sub": "anonymous"}}


@pytest.mark.unit
def test_endpoint_no_header(client: TestClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        API_TOKEN=SecretStr("test_token"), AUTH_ENABLED=True
    )
    response = client.get("/test-auth")
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {"detail": "Not authenticated"}
