"""Proxy router to securely expose Selenium Hub via FastAPI, supporting both Docker and Kubernetes deployments. All routes require HTTP Basic Auth matching the Selenium Hub configuration."""

import base64
from typing import Annotated
from urllib.parse import urljoin

import httpx
from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBasicCredentials

from app.core.settings import Settings
from app.dependencies import get_settings, verify_basic_auth
from app.logger import logger
from app.services.selenium_hub import SeleniumHub

# Constants
SELENIUM_HUB_PREFIX = "/selenium-hub"
REDIRECT_STATUS_CODES = {
    status.HTTP_301_MOVED_PERMANENTLY,
    status.HTTP_302_FOUND,
    status.HTTP_303_SEE_OTHER,
    status.HTTP_307_TEMPORARY_REDIRECT,
    status.HTTP_308_PERMANENT_REDIRECT,
}
MAX_REDIRECTS = 10
FORWARDED_HEADERS = {
    "user-agent",
    "accept",
    "accept-language",
    "accept-encoding",
    "content-type",
    "connection",
    "cache-control",
}

router = APIRouter(prefix=SELENIUM_HUB_PREFIX, tags=["Selenium Hub"])


# --- Utility Functions ---


def _get_selenium_hub_url(suffix: str = "") -> str:
    """Construct Selenium Hub URL with proper path handling."""
    url: str = urljoin(SeleniumHub().URL, suffix)
    return url


# --- Proxy Logic ---


async def _create_proxy_request(
    request: Request, target_url: str, credentials: HTTPBasicCredentials
) -> httpx.Request:
    """Create authenticated proxy request with filtered headers."""
    headers = {k: v for k, v in request.headers.items() if k.lower() in FORWARDED_HEADERS}

    # Add Selenium Hub authentication
    headers["Authorization"] = (
        "Basic "
        + base64.b64encode(f"{credentials.username}:{credentials.password}".encode()).decode()
    )

    return httpx.Request(
        method=request.method,
        url=target_url,
        headers=headers,
        content=await request.body(),
        params=request.query_params,
    )


async def proxy_selenium_request(
    request: Request,
    selenium_url: str,
    basic_auth: HTTPBasicCredentials,
    follow_redirects: bool = False,
) -> Response:
    """
    Shared proxy logic for Selenium Hub endpoints.
    Handles authentication, header filtering, and redirect following.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            current_url = selenium_url
            redirect_count = 0

            while redirect_count < (MAX_REDIRECTS if follow_redirects else 1):
                proxy_req = await _create_proxy_request(request, current_url, basic_auth)
                resp = await client.send(proxy_req, stream=True, follow_redirects=False)

                logger.debug("Proxied %s %s -> %d", request.method, current_url, resp.status_code)

                # Handle redirects
                if follow_redirects and resp.status_code in REDIRECT_STATUS_CODES:
                    if location := resp.headers.get("location"):
                        current_url = urljoin(current_url, location)
                        redirect_count += 1
                        continue

                # Build final response
                response_headers = {
                    k: v
                    for k, v in resp.headers.items()
                    if k.lower() not in {"content-encoding", "transfer-encoding", "content-length"}
                }

                # Special handling for UI resources
                content_type = resp.headers.get("content-type", "")
                if "text/html" in content_type or "application/json" in content_type:
                    content = await resp.aread()
                else:
                    content = b""
                    async for chunk in resp.aiter_bytes():
                        content += chunk

                return Response(
                    content=content,
                    status_code=resp.status_code,
                    headers=response_headers,
                    media_type=content_type,
                )

            return Response(
                content="Proxy error: Too many redirects",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    except httpx.HTTPError as e:
        logger.error(f"HTTP error proxying to Selenium Hub: {e}")
        return Response(
            content=f"Bad Gateway: {e}",
            status_code=status.HTTP_502_BAD_GATEWAY,
        )
    except Exception:
        logger.exception("Unexpected proxy error")
        return Response(
            content="Internal Server Error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# --- Route Handlers ---


@router.get("/", include_in_schema=False)
async def selenium_hub_root_proxy(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    basic_auth: HTTPBasicCredentials = Depends(verify_basic_auth),
) -> Response:
    """
    Proxy Selenium Hub root (requires Basic Auth).
    Redirects {SELENIUM_HUB_PREFIX}/ to {SELENIUM_HUB_PREFIX}/ui.
    """
    # If the path is exactly {SELENIUM_HUB_PREFIX}/, redirect to {SELENIUM_HUB_PREFIX}/ui
    if request.url.path.rstrip("/") == SELENIUM_HUB_PREFIX:
        return RedirectResponse(url=f"{SELENIUM_HUB_PREFIX}/ui")

    # Otherwise, proxy the request
    selenium_url = _get_selenium_hub_url()
    return await proxy_selenium_request(request, selenium_url, basic_auth, follow_redirects=True)


@router.get(
    "/ui",
    include_in_schema=False,
    response_class=RedirectResponse,
)
async def selenium_hub_ui_redirect() -> RedirectResponse:
    """Redirect {SELENIUM_HUB_PREFIX}/ui to {SELENIUM_HUB_PREFIX}/ui/ for SPA asset resolution."""
    return RedirectResponse(url=f"{SELENIUM_HUB_PREFIX}/ui/")


async def selenium_hub_proxy(
    request: Request,
    path: str,
    settings: Annotated[Settings, Depends(get_settings)],
    basic_auth: HTTPBasicCredentials = Depends(verify_basic_auth),
) -> Response:
    """Proxy all Selenium Hub subpaths (requires Basic Auth)."""
    selenium_url = _get_selenium_hub_url(path)
    return await proxy_selenium_request(request, selenium_url, basic_auth)


# Define routes for selenium_hub_path_proxy - `Avoiding UserWarning: Duplicate Operation ID`
for method in ["GET", "POST", "DELETE"]:
    router.api_route(
        "/{path:path}",
        methods=[method],
        name=f"selenium_hub_{method.lower()}",
        response_class=Response,
    )(selenium_hub_proxy)


# Selenium grid old versions
# @router.api_route(
#     "/ui/{path:path}",
#     methods=["GET", "POST", "DELETE"],
#     response_class=Response,
# )
# async def selenium_hub_ui_proxy(
#     request: Request,
#     settings: Annotated[Settings, Depends(get_settings)],
#     basic_auth: HTTPBasicCredentials = Depends(verify_basic_auth),
#     path: str = "",
# ) -> Response:
#     """Proxy all Selenium Hub UI static assets and API routes (requires Basic Auth)."""
#     selenium_url = _get_selenium_hub_url(f"ui/{path}")
#     return await proxy_selenium_request(request, selenium_url, basic_auth)
