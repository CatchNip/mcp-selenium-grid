import asyncio
import logging
from subprocess import PIPE, Popen
from threading import Thread
from typing import Awaitable, Callable, Optional, TextIO


class PortForwardManager:
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
        self.process: Optional[Popen[str]] = None

    def _stream_reader(self, stream: TextIO, log_func: Callable[[str], None], prefix: str) -> None:
        try:
            for line in iter(stream.readline, ""):
                if line:
                    log_func(f"{prefix}: {line.strip()}")
        except Exception as e:
            logging.warning(f"Exception in port-forward stream reader: {e}")

    def _start_port_forward(self) -> Optional[Popen[str]]:
        cmd = [
            "kubectl",
            "port-forward",
            f"service/{self.service_name}",
            f"{self.local_port}:{self.remote_port}",
            "-n",
            self.namespace,
        ]
        if self.kubeconfig:
            cmd.extend(["--kubeconfig", self.kubeconfig])
        if self.context:
            cmd.extend(["--context", self.context])
        try:
            process = Popen(cmd, stdout=PIPE, stderr=PIPE, text=True, bufsize=1)  # noqa: S603
            logging.info("Started kubectl service port-forward.")
            if process.stdout is not None:
                Thread(
                    target=self._stream_reader,
                    args=(process.stdout, logging.info, "kubectl port-forward stdout"),
                    daemon=True,
                ).start()
            if process.stderr is not None:
                Thread(
                    target=self._stream_reader,
                    args=(process.stderr, logging.error, "kubectl port-forward stderr"),
                    daemon=True,
                ).start()
            return process
        except FileNotFoundError:
            logging.error("kubectl not found! Please ensure kubectl is installed and in your PATH.")
            return None
        except Exception as e:
            logging.error(f"Unexpected error starting kubectl port-forward: {e}")
            return None

    async def start(self) -> bool:
        for attempt in range(1, self.max_retries + 1):
            logging.info(f"Attempt {attempt} to start port-forward and health check...")
            self.process = self._start_port_forward()
            if not self.process:
                await asyncio.sleep(2)
                continue
            await asyncio.sleep(2)  # Give port-forward a moment to start
            if self.process.poll() is not None:
                out, err = self.process.communicate(timeout=2)
                if out:
                    logging.info(f"kubectl port-forward stdout (early exit): {out.strip()}")
                if err:
                    logging.error(f"kubectl port-forward process exited early: {err.strip()}")
                self.process = None
                await asyncio.sleep(2)
                continue
            if await self.check_health():
                logging.info("Port-forward and health check succeeded.")
                return True
            # Health check failed, kill process and retry
            if self.process:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except Exception:
                    self.process.kill()
                self.process = None
            await asyncio.sleep(2)
        logging.error("Failed to start port-forward and connect to service after retries.")
        return False

    def stop(self) -> None:
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
            self.process = None
