"""Coverage status evaluation and reporting."""

from dataclasses import dataclass
from typing import NamedTuple

from .settings import CoverageThresholds


@dataclass(frozen=True)
class Status:
    """Immutable coverage status report."""

    message: str
    color: str
    emoji: str
    exit_code: int


class FileStatus(NamedTuple):
    """Simple file status indicator."""

    emoji: str
    color: str


def evaluate_coverage(coverage_percentage: float, thresholds: CoverageThresholds) -> Status:
    """Determine coverage status based on thresholds."""
    if coverage_percentage >= thresholds.minimum:
        return _success_status()

    if coverage_percentage >= thresholds.failure_limit:
        return _warning_status(thresholds)

    return _failure_status(thresholds)


def evaluate_file_coverage(
    coverage_percentage: float, thresholds: CoverageThresholds
) -> FileStatus:
    """Determine individual file coverage status."""
    if coverage_percentage >= thresholds.minimum:
        return FileStatus("✅", "green")

    if coverage_percentage >= thresholds.failure_limit:
        return FileStatus("⚠️", "yellow")

    return FileStatus("❌", "red")


def _success_status() -> Status:
    """Create successful coverage status."""
    return Status(
        message="✅ Coverage meets the threshold. 🎉", color="green", emoji="✅", exit_code=0
    )


def _warning_status(thresholds: CoverageThresholds) -> Status:
    """Create warning coverage status."""
    return Status(
        message="⚠️ Coverage below threshold but within margin.",
        color="yellow",
        emoji="⚠️",
        exit_code=0,
    )


def _failure_status(thresholds: CoverageThresholds) -> Status:
    """Create failure coverage status."""
    message = f"❌ Coverage too low! Below allowed minimum ({thresholds.failure_limit:.1f}%) 🚨"
    return Status(message=message, color="red", emoji="❌", exit_code=1)
