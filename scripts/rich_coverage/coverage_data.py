"""Coverage data processing and analysis."""

from json import loads
from os import close, listdir, path, remove
from tempfile import mkstemp
from typing import Any

from coverage import Coverage
from rich.console import Console
from typer import Exit


def load_coverage() -> Coverage:
    """Load coverage data from available sources."""
    _combine_partial_reports()
    _validate_coverage_exists()

    coverage = Coverage()
    coverage.load()
    return coverage


def extract_report_data(coverage: Coverage) -> dict[str, Any]:
    """Extract structured report data from coverage object."""
    file_descriptor, temp_path = mkstemp(suffix=".json")

    try:
        coverage.json_report(outfile=temp_path)
        return _read_json_report(temp_path)
    finally:
        _cleanup_temp_file(file_descriptor, temp_path)


def get_total_coverage(report_data: dict[str, Any]) -> float:
    """Extract total coverage percentage from report data."""
    return float(report_data["totals"]["percent_covered"])


def _combine_partial_reports() -> None:
    """Combine partial coverage reports if they exist."""
    if any(f.startswith(".coverage.") for f in listdir(".")):
        Console().print("🔄 Combining coverage files...")
        Coverage().combine()


def _validate_coverage_exists() -> None:
    """Ensure coverage data file exists."""
    if not path.exists(".coverage"):
        Console().print("[red]❌ No coverage data found.[/red]")
        raise Exit(code=1)


def _read_json_report(file_path: str) -> dict[str, Any]:
    """Read and parse JSON coverage report."""
    with open(file_path, "r") as file:
        content = file.read()
        if not content:
            return _empty_report_structure()
        json_report: dict[str, Any] = loads(content)
        return json_report


def _empty_report_structure() -> dict[str, Any]:
    """Return empty report structure for edge cases."""
    return {
        "files": {},
        "totals": {"percent_covered": 0.0, "num_statements": 0, "missing_lines": 0},
    }


def _cleanup_temp_file(file_descriptor: int, file_path: str) -> None:
    """Safely remove temporary file and close descriptor."""
    try:
        close(file_descriptor)
        remove(file_path)
    except OSError:
        pass
