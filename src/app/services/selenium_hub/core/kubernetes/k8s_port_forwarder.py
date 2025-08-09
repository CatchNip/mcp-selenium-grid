import asyncio
import logging
from pathlib import Path
from subprocess import PIPE, STDOUT, Popen
from tempfile import gettempdir
from threading import Thread
from typing import Awaitable, Callable

from ...common.logger import logger
from ...common.pidfile import PidFile, is_process_running_with_cmdline, terminate_pid


class PortForwardManager:
    service_name: str
    namespace: str
    local_port: int
    remote_port: int
    check_health: Callable[..., Awaitable[bool]]
    kubeconfig: str
    context: str
    max_retries: int
    health_timeout: int
    process: Popen[str] | None
    pidfile: PidFile

    def __init__(  # noqa: PLR0913 # Consider refactoring to use a config object or dataclass if more are added.
        self,
        service_name: str,
        namespace: str,
        local_port: int,
        remote_port: int,
        check_health: Callable[..., Awaitable[bool]],
        kubeconfig: str = "",
        context: str = "",
        max_retries: int = 5,
        health_timeout: int = 30,
        pid_dir: Path | None = None,
    ) -> None:
        self.service_name = service_name
        self.namespace = namespace
        self.local_port = local_port
        self.remote_port = remote_port
        self.kubeconfig = kubeconfig
        self.context = context
        self.check_health = check_health
        self.max_retries = max_retries
        self.health_timeout = health_timeout

        self.process = None

        pid_dir = pid_dir or Path(gettempdir())
        self.pidfile = PidFile(pid_dir / f"{service_name}-{local_port}.pid")

    @staticmethod
    def _start_logger_thread(process: Popen[str]) -> None:
        def log_message(level: int, line: str) -> None:
            logger.log(level, f"kubectl port-forward: {line.strip()}")

        # Drain stdout in a thread to avoid blocking
        def log_output() -> None:
            if process.stdout:
                for line in process.stdout:
                    log_message(logging.INFO, line)
            if process.stderr:
                for line in process.stderr:
                    log_message(logging.ERROR, line)

        Thread(target=log_output, daemon=True).start()

    def _build_cmd_args(self) -> list[str]:
        cmd_args = [
            "kubectl",
            "port-forward",
            f"service/{self.service_name}",
            f"{self.local_port}:{self.remote_port}",
            "-n",
            self.namespace,
        ]
        if self.kubeconfig:
            cmd_args.extend(["--kubeconfig", self.kubeconfig])
        if self.context:
            cmd_args.extend(["--context", self.context])

        return cmd_args

    def _kubectl_port_foward(self) -> Popen[str]:
        cmd = self._build_cmd_args()
        logger.info(f"Executing: {' '.join(cmd)}")

        # Start subprocess with live stdout capturing
        process = Popen(  # noqa: S603
            cmd,
            stdout=PIPE,
            stderr=STDOUT,
            text=True,
            bufsize=1,
            shell=False,
        )

        self._start_logger_thread(process)

        return process

    def _is_existing_port_forward_alive(self) -> bool:
        if not self.pidfile.exists_and_alive():
            return False

        pid = self.pidfile.read()
        if pid is None:
            return False

        is_running = is_process_running_with_cmdline(pid, self._build_cmd_args())
        if not is_running:
            logger.warning(
                f"PID {pid} exists but process does not match expected command line. "
                "It may be stale or from another context."
            )
            terminate_pid(pid)
            self.pidfile.remove()

        return is_running

    def _start_port_forward(self) -> Popen[str] | None:
        if self._is_existing_port_forward_alive():
            logger.info(
                f"Port-forward for {self.service_name} on port {self.local_port} already running."
            )
            return None

        try:
            process = self._kubectl_port_foward()
            # Write PID
            self.pidfile.write(process.pid)
            logger.info(f"Started kubectl port-forward process (PID: {process.pid})")

        except FileNotFoundError:
            logger.error("kubectl not found! Please install and add to PATH.")
        except Exception as e:
            logger.error(f"Error starting kubectl port-forward: {e}")
        else:
            return process
        return None

    async def start(self) -> bool:
        if self._is_existing_port_forward_alive():
            if await self.check_health():
                logger.info("Port-forward already running and healthy.")
                return True
            else:
                logger.warning(
                    "Existing port-forward is running but health check failed, cleaning up."
                )
                self.stop()

        for attempt in range(1, self.max_retries + 1):
            logger.info(f"Attempt {attempt} to start port-forward...")

            self.process = self._start_port_forward()
            if not self.process:
                await asyncio.sleep(2)
                continue

            await asyncio.sleep(2)
            try:
                is_alive = self.process.poll() is None
                exit_code = self.process.returncode
                logger.debug(f"Process returned: {is_alive}, exit_code: {exit_code}")
            except Exception as exc:
                logger.error(f"Error checking is_alive(): {exc}")
                is_alive = False
                exit_code = None
            if not is_alive:
                logger.error(
                    "kubectl port-forward exited immediately. exit_code: %r (type %s)",
                    exit_code,
                    type(exit_code).__name__ if exit_code is not None else "NoneType",
                )
                self.pidfile.remove()
                self.process = None
                await asyncio.sleep(2)
                continue

            logger.info("Process still alive, checking health.")
            if await self.check_health():
                logger.info("Port-forward started and health check passed.")
                return True

            logger.warning("Health check failed, stopping port-forward and retrying.")
            self.stop()
            await asyncio.sleep(2)

        logger.error("Failed to start port-forward after retries.")
        return False

    def stop(self) -> None:
        if self.process:
            logger.info("Terminating port-forward process...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
            self.process = None

        pid = self.pidfile.read()
        if pid is not None:
            terminate_pid(pid)
        self.pidfile.remove()
        logger.info("Port-forward stopped.")
