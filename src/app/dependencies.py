"""Token authentication for MCP Server."""

from functools import lru_cache
from typing import Dict

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBasic,
    HTTPBasicCredentials,
    HTTPBearer,
)

from app.core.settings import Settings


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# HTTP Bearer token setup
security = HTTPBearer()
basic_auth_scheme = HTTPBasic(auto_error=True)


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    settings: Settings = Depends(get_settings),
) -> Dict[str, str]:
    """Verify API token and return user information."""
    if credentials.credentials != settings.API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token",
        )
    return {"sub": "api-user"}


def verify_basic_auth(
    credentials: HTTPBasicCredentials = Depends(basic_auth_scheme),
    settings: Settings = Depends(get_settings),
) -> HTTPBasicCredentials:
    """
    Verifies HTTP Basic credentials against settings (from config.yaml).
    Returns credentials if valid, else raises HTTP 401 with WWW-Authenticate header.
    """
    if not credentials or not credentials.username or not credentials.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Basic"},
        )
    user = settings.SELENIUM_HUB_USER
    pwd = settings.SELENIUM_HUB_PASSWORD

    if credentials.username != user or credentials.password != pwd:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials
