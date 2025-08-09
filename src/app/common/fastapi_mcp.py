from fastapi.requests import Request
from fastapi.responses import Response
from fastapi_mcp.transport.http import FastApiHttpSessionManager

from .logger import logger


async def handle_fastapi_request(
    name: str,
    request: Request,
    target_path: str,
    method: str,
    session_manager: FastApiHttpSessionManager,
) -> Response:
    scope = dict(request.scope)
    scope["path"] = target_path
    scope["raw_path"] = target_path.encode("utf-8")
    scope["query_string"] = request.scope.get("query_string", b"")
    scope["method"] = method

    new_request = Request(scope, request.receive)

    logger.debug(f"Proxying internally to {name} at {target_path}")
    response: Response = await session_manager.handle_fastapi_request(new_request)
    return response
