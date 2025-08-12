"""FastAPI app dependencies."""

from functools import lru_cache
from secrets import compare_digest

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBasic,
    HTTPBasicCredentials,
    HTTPBearer,
)

from app.common.logger import logger
from app.core.settings import Settings


@lru_cache()
def get_settings() -> Settings:
    """Returns a cached instance of the application settings."""
    return Settings()


# HTTP Bearer token setup
security = HTTPBearer(auto_error=False)
basic_auth_scheme = HTTPBasic(auto_error=True)


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """
    Verifies the bearer token from the Authorization header.

    Performs constant-time comparison against the configured `API_TOKEN`
    to prevent timing attacks.

    Args:
        credentials: Bearer token extracted by FastAPI from the request.
        settings: Application settings containing the expected token.

    Returns:
        A dict with user identity metadata (e.g., subject claim).

    Raises:
        HTTPException: 401 if the token is invalid or missing.
    """

    # If API_TOKEN is empty, skip auth (allow access)
    if not settings.AUTH_ENABLED:
        logger.critical(
            "API_TOKEN is disabled — skipping token verification, access granted as anonymous".upper()
        )
        return {"sub": "anonymous"}

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authenticated",
        )

    if not compare_digest(settings.API_TOKEN.get_secret_value(), credentials.credentials):
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
    Verifies HTTP Basic credentials using constant-time comparison.

    The username and password are compared against the configured
    `SELENIUM_HUB_USER` and `SELENIUM_HUB_PASSWORD` using
    `secrets.compare_digest` to mitigate timing attacks.

    Args:
        credentials: Parsed Basic Auth credentials from the request.
        settings: Application settings with expected credentials.

    Returns:
        The `HTTPBasicCredentials` object if authentication succeeds.

    Raises:
        HTTPException: 401 with `WWW-Authenticate` header if credentials
                       are missing or invalid.
    """
    if not (credentials and credentials.username and credentials.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Basic"},
        )
    user = settings.selenium_grid.USER.get_secret_value()
    pwd = settings.selenium_grid.PASSWORD.get_secret_value()

    if not (
        compare_digest(user, credentials.username) and compare_digest(pwd, credentials.password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials
