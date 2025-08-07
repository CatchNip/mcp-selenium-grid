"""Coverage threshold settings."""

from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class CoverageThresholds:
    """Immutable coverage threshold configuration."""

    minimum: float
    tolerance: float

    @property
    def failure_limit(self) -> float:
        """Calculate the minimum acceptable coverage."""
        return self.minimum - self.tolerance


def load_thresholds() -> CoverageThresholds:
    """Load coverage thresholds from environment or use defaults."""
    minimum = float(getenv("MIN_COVERAGE", "70"))
    tolerance = float(getenv("COVERAGE_TOLERANCE_MARGIN", "5"))
    return CoverageThresholds(minimum, tolerance)
