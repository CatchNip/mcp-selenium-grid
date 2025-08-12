from os import listdir, path
from socket import AF_INET, SOCK_STREAM, socket, timeout
from subprocess import PIPE, Popen, run
from tempfile import TemporaryDirectory
from time import sleep

import pytest
from app.core.settings import Settings
from httpx import Client, codes

from tests.conftest import create_cmd_fixture

uv_path = create_cmd_fixture("uv")
uvx_path = create_cmd_fixture("uvx")


def is_port_open(host: str, port: int) -> bool:
    with socket(AF_INET, SOCK_STREAM) as sock:
        sock.settimeout(1)
        try:
            sock.connect((host, port))
            return True
        except (ConnectionRefusedError, timeout):
            return False


@pytest.mark.integration
@pytest.mark.timeout(70)
def test_uvx_with_built_package(uv_path: str, uvx_path: str, auth_headers: dict[str, str]) -> None:
    HOST = "127.0.0.1"
    PORT = 7777

    settings = Settings()

    with TemporaryDirectory() as temp_build_dir:
        # Step 1: Build the package
        run(  # noqa: S603
            [uv_path, "build", "--out-dir", temp_build_dir],
            shell=False,
            check=True,
        )

        # Step 2: Locate the built wheel file
        wheel_files = [f for f in listdir(temp_build_dir) if f.endswith(".whl")]
        print(f"Wheel files found: {wheel_files}")
        assert wheel_files, "No wheel file found after uv build"
        wheel_path = path.join(temp_build_dir, wheel_files[0])

        # Step 3: Run uvx with the built package
        proc = Popen(  # noqa: S603
            [
                uvx_path,
                "--from",
                f"file://{wheel_path}",
                settings.PACKAGE_NAME,
                "server",
                "run",
                "--host",
                HOST,
                "--port",
                str(PORT),
            ],
            shell=False,
            stdout=PIPE,
            stderr=PIPE,
            text=True,
        )

        try:
            # Wait for server to start listening on port 7777
            timeout_seconds = 60
            for _ in range(timeout_seconds):
                if is_port_open(HOST, PORT):
                    break
                sleep(1)
            else:
                proc.terminate()
                proc.wait(timeout=5)
                pytest.fail(f"Server {HOST} did not start listening on port {PORT} within timeout.")

            # Step 4: Test server HTTP response with httpx
            with Client() as client:
                response = client.get(f"http://{HOST}:{PORT}/health", headers=auth_headers)
                assert response.status_code == codes.OK  # HTTP 200
        finally:
            proc.terminate()
            proc.wait(timeout=5)

        stdout, stderr = proc.communicate()
        print("uvx stdout:", stdout)
        print("uvx stderr:", stderr)
