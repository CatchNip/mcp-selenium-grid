import os
import subprocess
import time

import pytest
from app.main import app as fastapi_app
from fastmcp import Client, FastMCP

SIGINT_EXIT_CODE = 130


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tool_discovery_with_fastmcp_in_memory() -> None:
    server = FastMCP.from_fastapi(fastapi_app)

    async with Client(server) as client:
        # Prefer ping; if not available, try describe
        if hasattr(client, "ping"):
            await client.ping()
        elif hasattr(client, "describe"):
            description = await client.describe()
            assert await server.get_tools() == description.tools


def _run_stdio_once(
    uv_path: str,
    env: dict[str, str] | None = None,
    timeout: float = 20.0,
) -> subprocess.CompletedProcess[str]:
    command: list[str] = [
        uv_path,
        "run",
        "mcp-selenium-grid",
        "server",
        "run",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--stdio",
    ]

    proc = subprocess.Popen(  # noqa: S603
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, **(env or {})},
    )

    # Allow server to boot
    time.sleep(2.0)

    # Simulate client disconnect by sending EOF via communicate(input="")
    try:
        stdout, stderr = proc.communicate(input="", timeout=timeout)
    except subprocess.TimeoutExpired:
        # Ensure it shuts down in time
        proc.terminate()
        try:
            stdout, stderr = proc.communicate(input="", timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate(input="")

    return subprocess.CompletedProcess(command, proc.returncode or 0, stdout, stderr)


@pytest.mark.integration
def test_stdio_connect_disconnect_allows_clean_shutdown_and_restart(uv_path: str) -> None:
    # First run: should start and then exit cleanly on stdin close
    first = _run_stdio_once(uv_path)
    assert first.returncode in {0, SIGINT_EXIT_CODE}

    # Second run: should also start and exit cleanly on stdin close
    second = _run_stdio_once(uv_path)
    assert second.returncode in {0, SIGINT_EXIT_CODE}

    # Helpful debugging on failure
    if first.returncode not in (0, SIGINT_EXIT_CODE) or second.returncode not in (
        0,
        SIGINT_EXIT_CODE,
    ):
        raise AssertionError(
            f"Unexpected return codes: first={first.returncode}, second={second.returncode}\n"
            f"First stderr:\n{first.stderr}\n---\nSecond stderr:\n{second.stderr}"
        )
