import base64
from typing import Any

import pytest
from app.core.settings import settings
from fastapi import status
from fastapi.testclient import TestClient


class MockAsyncResponse:
    def __init__(self, status_code: int, body: bytes) -> None:
        self.status_code = status_code
        self.headers = {"content-type": "application/json"}
        self._body = body

    async def aread(self) -> bytes:
        return self._body


class MockAsyncClient:
    def __init__(self, status_code: int, body: bytes) -> None:
        self._status_code = status_code
        self._body = body

    async def __aenter__(self: "MockAsyncClient") -> "MockAsyncClient":
        return self

    async def __aexit__(self: "MockAsyncClient", exc_type: object, exc: object, tb: object) -> None:
        pass

    def build_request(self: "MockAsyncClient", *a: Any, **k: Any) -> None:
        return None

    async def send(self: "MockAsyncClient", *a: Any, **k: Any) -> MockAsyncResponse:
        return MockAsyncResponse(self._status_code, self._body)


@pytest.mark.integration
def test_proxy_requires_auth(client: TestClient, monkeypatch: Any) -> None:
    monkeypatch.setattr(
        "httpx.AsyncClient",
        lambda *a, **k: MockAsyncClient(403, b'{"detail": "Not authenticated"}'),
    )
    response = client.get("/selenium-hub/status")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.integration
def test_proxy_forwards_request(client: TestClient, monkeypatch: Any) -> None:
    """Test proxy forwards request with valid HTTP Basic Auth."""
    monkeypatch.setattr(
        "httpx.AsyncClient",
        lambda *a, **k: MockAsyncClient(200, b'{"value": "ok"}'),
    )
    basic_token = base64.b64encode(
        f"{settings.SELENIUM_HUB_USER}:{settings.SELENIUM_HUB_PASSWORD}".encode()
    ).decode()
    headers = {"Authorization": f"Basic {basic_token}"}
    response = client.get("/selenium-hub/status", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"value": "ok"}


@pytest.mark.integration
def test_proxy_accepts_http_basic(client: TestClient, monkeypatch: Any) -> None:
    """Test proxy accepts HTTP Basic Auth and uses it for upstream auth."""
    monkeypatch.setattr(
        "httpx.AsyncClient",
        lambda *a, **k: MockAsyncClient(200, b'{"value": "ok-basic"}'),
    )
    import base64

    basic_token = base64.b64encode(b"user:CHANGE_ME").decode()
    headers = {"Authorization": f"Basic {basic_token}"}
    response = client.get("/selenium-hub/status", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"value": "ok-basic"}
