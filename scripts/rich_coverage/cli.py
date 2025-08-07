"""Command-line interface for coverage checking."""

from enum import Enum

from typer import Exit, Option, Typer

from .coverage_data import extract_report_data, get_total_coverage, load_coverage
from .reporting import display_html_report, display_rich_report
from .settings import load_thresholds
from .status import evaluate_coverage


class OutputFormat(str, Enum):
    """Supported output formats."""

    RICH = "rich"
    HTML = "html"


def create_application() -> Typer:
    """Create the CLI application."""
    app = Typer(help="Beautiful code coverage reporting tool.")

    def run_coverage_check(format: OutputFormat) -> None:
        """Execute the coverage checking workflow."""
        thresholds = load_thresholds()
        coverage = load_coverage()
        report_data = extract_report_data(coverage)
        total_coverage = get_total_coverage(report_data)
        status = evaluate_coverage(total_coverage, thresholds)

        if format == OutputFormat.HTML:
            display_html_report(coverage, thresholds, status, total_coverage)
        else:
            display_rich_report(report_data, thresholds, status)

        raise Exit(code=status.exit_code)

    @app.command()
    def check(
        format: OutputFormat = Option(
            OutputFormat.RICH,
            "--format",
            "-f",
            help="Output format.",
            case_sensitive=False,
        ),
    ) -> None:
        """Check code coverage against configured thresholds."""
        run_coverage_check(format)

    return app


rich_coverage_cli = create_application()
