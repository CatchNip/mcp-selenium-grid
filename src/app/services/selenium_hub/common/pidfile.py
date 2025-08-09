from pathlib import Path
from typing import Iterable

from psutil import AccessDenied, NoSuchProcess, Process, TimeoutExpired

from .logger import logger


class PidFile:
    def __init__(self, path: Path) -> None:
        self.path = path
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory {self.path.parent} successfully.")
        except PermissionError:
            logger.error(f"Permission denied: Cannot create directory {self.path.parent}")
            raise
        except OSError as e:
            logger.error(f"OS error while creating directory {self.path.parent}: {e}")
            raise

    def exists_and_alive(self) -> bool:
        pid = self.read()
        if pid is None:
            return False
        alive = self._pid_alive(pid)
        logger.debug(f"PID file {self.path} exists and process {pid} alive: {alive}")
        return alive

    def read(self) -> int | None:
        if not self.path.exists():
            logger.debug(f"PID file {self.path} does not exist.")
            return None
        try:
            content = self.path.read_text().strip()
            if not content:
                logger.debug(f"PID file {self.path} is empty.")
                return None
            return int(content)
        except ValueError as e:
            logger.debug(f"Invalid PID in {self.path}: {e}")
            self.remove()
            return None
        except Exception as e:
            # Only log unexpected I/O issues at higher level
            logger.warning(f"Unexpected error reading PID file {self.path}: {e}")
            self.remove()
            return None

    def write(self, pid: int) -> None:
        try:
            self.path.write_text(str(pid))
            logger.debug(f"Wrote PID {pid} to {self.path}")
        except Exception as e:
            # This one should be ERROR — we expect this to work
            logger.error(f"Failed to write PID {pid} to {self.path}: {e}")

    def remove(self) -> None:
        try:
            if self.path.exists():
                self.path.unlink()
                logger.debug(f"Removed PID file {self.path}")
            else:
                logger.debug(f"PID file {self.path} already removed.")
        except Exception as e:
            # Rare, but possible (e.g. permission change)
            logger.warning(f"Failed to remove PID file {self.path}: {e}")

    def _pid_alive(self, pid: int) -> bool:
        try:
            Process(pid)
            return True
        except NoSuchProcess:
            return False


def is_process_running_with_cmdline(pid: int, expected_cmd_parts: Iterable[str]) -> bool:
    """
    Check if a process with `pid` is running and its command line contains all expected substrings.

    Args:
        pid: Process ID to check.
        expected_cmd_parts: Iterable of strings expected to appear somewhere in the process cmdline.

    Returns:
        True if the process exists and all expected substrings are found in its cmdline, False otherwise.
    """
    try:
        proc = Process(pid)
        cmdline = " ".join(proc.cmdline())
        for part in expected_cmd_parts:
            if part not in cmdline:
                logger.debug(f"Cmdline check failed: '{part}' not in '{cmdline}'")
                return False
        logger.debug(f"Process PID {pid} cmdline contains all expected parts.")
        return True
    except (NoSuchProcess, AccessDenied) as e:
        logger.warning(f"Cannot access process PID {pid}: {e}")
        return False


def terminate_pid(pid: int) -> None:
    """Attempt to terminate (and possibly kill) a process by PID."""
    try:
        proc = Process(pid)
        logger.info(f"Attempting to terminate process PID {pid}...")
        proc.terminate()
        proc.wait(timeout=5)
        logger.info(f"Terminated process PID {pid}.")
    except (NoSuchProcess, AccessDenied) as e:
        logger.warning(f"Could not terminate process PID {pid}: {e}")
    except TimeoutExpired:
        logger.warning(f"Process PID {pid} did not terminate in time, killing...")
        try:
            proc.kill()
        except Exception as e:
            logger.error(f"Failed to kill process PID {pid}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error terminating PID {pid}: {e}")
