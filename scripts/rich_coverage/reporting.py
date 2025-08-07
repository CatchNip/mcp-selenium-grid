"""Coverage report generation and display."""

from io import StringIO
from os import getenv
from textwrap import dedent
from typing import Any

from coverage import Coverage
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text

from .settings import CoverageThresholds
from .status import Status, evaluate_file_coverage

IN_GITHUB_ACTIONS = getenv("GITHUB_ACTIONS", "false").lower() == "true"


def display_rich_report(
    report_data: dict[str, Any], thresholds: CoverageThresholds, status: Status
) -> None:
    """Display comprehensive coverage report in terminal."""
    console = Console()

    _show_file_details(console, report_data, thresholds)
    _show_summary(console, report_data, thresholds)
    _show_final_status(console, status)


def display_html_report(
    coverage: Coverage, thresholds: CoverageThresholds, status: Status, total_coverage: float
) -> None:
    """Display HTML coverage report."""
    console = Console()

    _show_text_report(console, coverage, output_format="markdown")
    _show_html_summary(console, total_coverage, thresholds, status)


def _show_file_details(
    console: Console, report_data: dict[str, Any], thresholds: CoverageThresholds
) -> None:
    """Display per-file coverage details."""
    table = Table(title=":bar_chart: Coverage Report", show_lines=True)
    table.add_column("Name", style="bold cyan")
    table.add_column("Stmts", style="dim", justify="right")
    table.add_column("Miss", style="dim", justify="right")
    table.add_column("Cover", style="bold", justify="right")
    table.add_column("Status", justify="center")

    for filename, file_data in report_data.get("files", {}).items():
        summary = file_data["summary"]
        percentage = summary["percent_covered"]
        file_status = evaluate_file_coverage(percentage, thresholds)

        table.add_row(
            filename,
            str(summary["num_statements"]),
            str(summary["missing_lines"]),
            Text(f"{percentage:.0f}%", style=file_status.color),
            file_status.emoji,
        )

    console.print(table)


def _show_summary(
    console: Console, report_data: dict[str, Any], thresholds: CoverageThresholds
) -> None:
    """Display coverage summary information."""
    table = Table(title="🧪 Coverage Check Summary 📊", title_style="bold magenta")
    table.add_column("📈 Metric", style="cyan")
    table.add_column("📊 Value", style="green", justify="right")

    total_coverage = report_data["totals"]["percent_covered"]
    table.add_row("✅ Total Coverage", f"{total_coverage:.1f}%")
    table.add_row("🎯 Min Required", f"{thresholds.minimum:.1f}%")
    table.add_row("⚠️ Allowed Margin", f"{thresholds.tolerance:.1f}%")

    console.print(table)


def _show_final_status(console: Console, status: Status) -> None:
    """Display final coverage status message."""
    console.print(f"[bold {status.color}]{status.message}[/bold {status.color}]")


def _show_text_report(console: Console, coverage: Coverage, output_format: str = "") -> None:
    """Display standard text coverage report."""
    report_buffer = StringIO()
    coverage.report(file=report_buffer, output_format=output_format)
    content = report_buffer.getvalue()

    if IN_GITHUB_ACTIONS:
        print(content)
    else:
        markdown = Markdown(content)
        console.print(markdown)


def _show_html_summary(
    console: Console, total_coverage: float, thresholds: CoverageThresholds, status: Status
) -> None:
    """Display HTML summary of coverage results."""
    html = dedent(f"""\
        <div style="font-family: Arial, sans-serif; padding:10px; border:1px solid #ddd; border-radius:6px;">
        <h3>🧪 Coverage Check Summary 📊</h3>
        <table style="border-collapse: collapse; width: 100%; text-align: left;">
        <thead><tr><th style="border-bottom: 2px solid #ccc; padding:6px;">📈 Metric</th><th style="border-bottom: 2px solid #ccc; padding:6px; padding-left:3em;">📊 Value</th></tr></thead>
        <tbody>
        <tr><td style="padding:6px;">✅ Total Coverage</td><td style="padding:6px; padding-left:3em;">{total_coverage:.1f}%</td></tr>
        <tr><td style="padding:6px;">🎯 Min Required</td><td style="padding:6px; padding-left:3em;">{thresholds.minimum:.1f}%</td></tr>
        <tr><td style="padding:6px;">⚠️ Allowed Margin</td><td style="padding:6px; padding-left:3em;">{thresholds.tolerance:.1f}%</td></tr>
        </tbody></table>
        <p><strong>{status.message}</strong></p>
        </div>""")
    console.print(html)
