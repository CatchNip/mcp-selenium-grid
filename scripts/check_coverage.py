#!/usr/bin/env python3
"""
Coverage check with thresholds, html or rich output.
"""

import os
import sys
from io import StringIO
from typing import Optional

from coverage import Coverage
from rich.console import Console
from rich.table import Table
from typer import Option, Typer

console = Console()


def get_coverage() -> float:
    files = [f for f in os.listdir(".") if f.startswith(".coverage.")]
    if files:
        console.print(f"🔄 Combining {len(files)} coverage files...")
        Coverage().combine()
    if not os.path.exists(".coverage"):
        console.print("[red]❌ No coverage data found[/red]")
        sys.exit(1)
    cov = Coverage()
    cov.load()
    return cov.report(file=StringIO())


def html_summary(cov_pct: float, min_cov: float, margin: float) -> str:
    allowed = min_cov - margin
    msg = (
        f"❌ Coverage too low! Below allowed minimum ({allowed:.1f}%) 🚨"
        if cov_pct < allowed
        else "⚠️ Coverage below threshold but within margin."
        if cov_pct < min_cov
        else "✅ Coverage meets the threshold. 🎉"
    )
    return f"""\
            <div style="font-family: Arial, sans-serif; padding:10px; border:1px solid #ddd; border-radius:6px;">
            <h3>🧪 Coverage Check Summary 📊</h3>
            <table style="border-collapse: collapse; width: 100%; text-align: left;">
            <thead><tr><th style="border-bottom: 2px solid #ccc; padding:6px;">📈 Metric</th><th style="border-bottom: 2px solid #ccc; padding:6px; padding-left:3em;">📊 Value</th></tr></thead>
            <tbody>
            <tr><td style="padding:6px;">✅ Total Coverage</td><td style="padding:6px; padding-left:3em;">{cov_pct:.1f}%</td></tr>
            <tr><td style="padding:6px;">🎯 Min Required</td><td style="padding:6px; padding-left:3em;">{min_cov:.1f}%</td></tr>
            <tr><td style="padding:6px;">⚠️ Allowed Margin</td><td style="padding:6px; padding-left:3em;">{margin:.1f}%</td></tr>
            </tbody></table>
            <p><strong>{msg}</strong></p>
            </div>"""


def rich_summary(cov_pct: float, min_cov: float, margin: float) -> int:
    allowed = min_cov - margin
    table = Table(title="🧪 Coverage Check Summary 📊", title_style="bold magenta")
    table.add_column("📈 Metric", style="cyan", no_wrap=True)
    table.add_column("📊 Value", style="green", justify="right")
    table.add_row("✅ Total Coverage", f"{cov_pct:.1f}%")
    table.add_row("🎯 Min Required", f"{min_cov:.1f}%")
    table.add_row("⚠️ Allowed Margin", f"{margin:.1f}%")
    console.print(table)
    if cov_pct < allowed:
        console.print(
            f"[bold red]❌ Coverage too low! Below allowed minimum ({allowed:.1f}%) 🚨[/bold red]"
        )
        return 1
    elif cov_pct < min_cov:
        console.print("[bold yellow]⚠️ Coverage below threshold but within margin.[/bold yellow]")
    else:
        console.print("[bold green]✅ Coverage meets the threshold. 🎉[/bold green]")
    return 0


def create_application() -> Typer:
    app = Typer()

    @app.command()
    def check(
        format: Optional[str] = Option(
            "rich", "--format", "-f", help="Output format (rich or html)"
        ),
    ) -> None:
        cov_pct = get_coverage()
        min_cov = float(os.getenv("MIN_COVERAGE", "70"))
        margin = float(os.getenv("COVERAGE_TOLERANCE_MARGIN", "5"))

        if format == "html":
            print(html_summary(cov_pct, min_cov, margin))
            sys.exit(1 if cov_pct < min_cov - margin else 0)
        else:
            sys.exit(rich_summary(cov_pct, min_cov, margin))

    return app


app = create_application()

if __name__ == "__main__":
    app()
